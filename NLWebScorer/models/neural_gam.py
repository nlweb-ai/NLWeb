"""Neural Generalized Additive Model (Neural GAM) for interpretable scoring.

Architecture (following Neural Additive Models, Agarwal et al. 2021):
    score = Σ f_i(x_i)

Each f_i is a small MLP that operates on a single feature (or feature group).
This gives interpretability: you can plot each f_i to see how each feature
contributes to the final score.

Feature groups:
    1. BERT [CLS] embedding (768-d) → compressed via a learned projection
    2. query_length (scalar)
    3. item_name_length (scalar)
    4. query_item_word_overlap (scalar)
    5. schema_type (categorical → embedding)
    6. difficulty (scalar)
"""

import torch
import torch.nn as nn


class FeatureSubnet(nn.Module):
    """Small MLP for a single feature's shape function f_i(x_i)."""

    def __init__(self, input_dim: int, hidden_units: list[int],
                 activation: str = "relu", dropout: float = 0.1):
        super().__init__()
        layers = []
        in_dim = input_dim
        act_fn = {"relu": nn.ReLU, "gelu": nn.GELU, "elu": nn.ELU}[activation]

        for h in hidden_units:
            layers.extend([nn.Linear(in_dim, h), act_fn(), nn.Dropout(dropout)])
            in_dim = h

        layers.append(nn.Linear(in_dim, 1))  # Single output contribution
        self.net = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """x: (batch, input_dim) → (batch, 1)"""
        return self.net(x)


class NeuralGAM(nn.Module):
    """Neural GAM: score = sigmoid(bias + Σ f_i(x_i))

    Combines BERT embeddings with handcrafted features in an
    interpretable additive structure.
    """

    def __init__(self, bert_dim: int = 768, bert_proj_dim: int = 64,
                 num_schema_types: int = 20, schema_embed_dim: int = 8,
                 subnet_hidden: list[int] = None,
                 subnet_activation: str = "relu",
                 subnet_dropout: float = 0.1):
        super().__init__()

        if subnet_hidden is None:
            subnet_hidden = [128, 64, 32]

        # Project BERT [CLS] to lower dim before the subnet
        self.bert_proj = nn.Linear(bert_dim, bert_proj_dim)

        # Schema type embedding
        self.schema_embed = nn.Embedding(num_schema_types + 1, schema_embed_dim)

        # Per-feature subnets: f_i(x_i)
        self.f_bert = FeatureSubnet(bert_proj_dim, subnet_hidden,
                                    subnet_activation, subnet_dropout)
        self.f_query_length = FeatureSubnet(1, subnet_hidden,
                                            subnet_activation, subnet_dropout)
        self.f_item_name_length = FeatureSubnet(1, subnet_hidden,
                                                subnet_activation, subnet_dropout)
        self.f_word_overlap = FeatureSubnet(1, subnet_hidden,
                                            subnet_activation, subnet_dropout)
        self.f_schema_type = FeatureSubnet(schema_embed_dim, subnet_hidden,
                                           subnet_activation, subnet_dropout)
        self.f_difficulty = FeatureSubnet(1, subnet_hidden,
                                          subnet_activation, subnet_dropout)

        self.bias = nn.Parameter(torch.zeros(1))

        self._subnet_names = [
            "bert_embedding", "query_length", "item_name_length",
            "word_overlap", "schema_type", "difficulty"
        ]

    def forward(self, bert_embedding: torch.Tensor,
                query_length: torch.Tensor,
                item_name_length: torch.Tensor,
                word_overlap: torch.Tensor,
                schema_type_idx: torch.Tensor,
                difficulty: torch.Tensor,
                return_contributions: bool = False):
        """Forward pass.

        All scalar features: (batch,) or (batch, 1)
        bert_embedding: (batch, bert_dim)
        schema_type_idx: (batch,) long tensor

        Returns:
            scores: (batch, 1) in [0, 1]
            contributions: dict of (batch, 1) per feature (if requested)
        """
        # Ensure scalar features are (batch, 1)
        query_length = query_length.unsqueeze(-1) if query_length.dim() == 1 else query_length
        item_name_length = item_name_length.unsqueeze(-1) if item_name_length.dim() == 1 else item_name_length
        word_overlap = word_overlap.unsqueeze(-1) if word_overlap.dim() == 1 else word_overlap
        difficulty = difficulty.unsqueeze(-1) if difficulty.dim() == 1 else difficulty

        # Compute each feature's contribution
        bert_proj = self.bert_proj(bert_embedding)
        schema_emb = self.schema_embed(schema_type_idx)

        contributions = {
            "bert_embedding": self.f_bert(bert_proj),
            "query_length": self.f_query_length(query_length),
            "item_name_length": self.f_item_name_length(item_name_length),
            "word_overlap": self.f_word_overlap(word_overlap),
            "schema_type": self.f_schema_type(schema_emb),
            "difficulty": self.f_difficulty(difficulty),
        }

        # Additive combination
        logit = self.bias
        for c in contributions.values():
            logit = logit + c

        scores = torch.sigmoid(logit)

        if return_contributions:
            return scores, contributions
        return scores

    def get_feature_names(self) -> list[str]:
        return list(self._subnet_names)


class GAMDataset(torch.utils.data.Dataset):
    """Dataset for Neural GAM training.

    Expects pre-computed BERT embeddings + handcrafted features.
    """

    def __init__(self, bert_embeddings: torch.Tensor, features: dict,
                 scores: torch.Tensor):
        """
        Args:
            bert_embeddings: (N, bert_dim)
            features: dict with keys matching GAM feature names, each (N,)
            scores: (N,) target scores in [0, 1]
        """
        self.bert_embeddings = bert_embeddings
        self.features = features
        self.scores = scores

    def __len__(self):
        return len(self.scores)

    def __getitem__(self, idx):
        return {
            "bert_embedding": self.bert_embeddings[idx],
            "query_length": self.features["query_length"][idx],
            "item_name_length": self.features["item_name_length"][idx],
            "word_overlap": self.features["word_overlap"][idx],
            "schema_type_idx": self.features["schema_type_idx"][idx],
            "difficulty": self.features["difficulty"][idx],
            "score": self.scores[idx],
        }
