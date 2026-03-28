"""Rubric-based Neural GAM for interpretable scoring.

Architecture (following Neural Additive Models, Agarwal et al. 2021):
    score = sigmoid(bias + f_bert(proj(cls)) + Σ f_group(rubric_features))

Each rubric group gets its own FeatureSubnet, giving interpretable
per-category contributions. Three variants supported:

  - additive: Pure NAM. score = sigmoid(bias + Σ f_i(x_i))
  - gated:    Query-conditioned weighting of rubric groups.
              gate = softmax(g(bert_proj))
              score = sigmoid(bias + f_bert + Σ gate_i * f_group_i)
  - interaction: Additive + small MLP on group contributions.
              score = sigmoid(bias + Σ f_i + h(concat(contributions)))

Rubric groups (from 16 SCALAR_FEATURES):
    Relevance (4):    query_term_coverage, title_query_overlap,
                      exact_query_match, query_item_word_overlap
    Type Match (1):   type_match
    Completeness (5): description_length, schema_field_count,
                      has_rating, has_price, has_image
    Quality (3):      has_date, content_word_count, has_author
    Specificity (3):  query_word_count, name_word_count, difficulty
"""

import torch
import torch.nn as nn

from models.neural_gam import FeatureSubnet


# Rubric feature groups — order within each group matches SCALAR_FEATURES
RUBRIC_GROUPS = {
    "relevance": [
        "query_term_coverage", "title_query_overlap",
        "exact_query_match", "query_item_word_overlap",
    ],
    "type_match": [
        "type_match",
    ],
    "completeness": [
        "description_length", "schema_field_count",
        "has_rating", "has_price", "has_image",
    ],
    "quality": [
        "has_date", "content_word_count", "has_author",
    ],
    "specificity": [
        "query_word_count", "name_word_count", "difficulty",
    ],
}

# Flat list of all rubric feature names in group order
ALL_RUBRIC_FEATURES = [f for group in RUBRIC_GROUPS.values() for f in group]

GROUP_NAMES = list(RUBRIC_GROUPS.keys())


class RubricGAM(nn.Module):
    """Rubric-based Neural GAM with BERT embeddings.

    score = sigmoid(bias + f_bert(proj(cls)) + Σ f_group(rubric_features))

    Supports additive, gated, and interaction modes.
    """

    def __init__(self, bert_dim: int = 1024, bert_proj_dim: int = 64,
                 bert_hidden: list[int] = None,
                 rubric_hidden: list[int] = None,
                 activation: str = "relu", dropout: float = 0.1,
                 mode: str = "additive",
                 interaction_hidden: list[int] = None):
        super().__init__()

        if bert_hidden is None:
            bert_hidden = [128, 64, 32]
        if rubric_hidden is None:
            rubric_hidden = [64, 32]
        if interaction_hidden is None:
            interaction_hidden = [16]

        self.mode = mode
        self.num_groups = len(RUBRIC_GROUPS)

        # BERT [CLS] projection + subnet
        self.bert_proj = nn.Linear(bert_dim, bert_proj_dim)
        self.f_bert = FeatureSubnet(bert_proj_dim, bert_hidden, activation, dropout)

        # Per-group rubric subnets
        self.group_subnets = nn.ModuleDict()
        for name, features in RUBRIC_GROUPS.items():
            self.group_subnets[name] = FeatureSubnet(
                len(features), rubric_hidden, activation, dropout)

        # Bias
        self.bias = nn.Parameter(torch.zeros(1))

        # Gated mode: query-conditioned gate network
        if mode == "gated":
            self.gate_net = nn.Sequential(
                nn.Linear(bert_proj_dim, 32),
                nn.ReLU(),
                nn.Linear(32, self.num_groups),
            )

        # Interaction mode: small MLP on contributions
        if mode == "interaction":
            n_contributions = 1 + self.num_groups  # bert + rubric groups
            layers = []
            in_dim = n_contributions
            for h in interaction_hidden:
                layers.extend([nn.Linear(in_dim, h), nn.ReLU(), nn.Dropout(dropout)])
                in_dim = h
            layers.append(nn.Linear(in_dim, 1))
            self.interaction_net = nn.Sequential(*layers)

    def forward(self, bert_embedding: torch.Tensor,
                rubric_features: dict[str, torch.Tensor],
                return_contributions: bool = False):
        """Forward pass.

        Args:
            bert_embedding: (batch, bert_dim) — [CLS] embeddings
            rubric_features: dict mapping group name → (batch, group_size) tensor
            return_contributions: if True, also return per-group contributions

        Returns:
            scores: (batch, 1) in [0, 1]
            contributions: dict of (batch, 1) per group (if return_contributions)
        """
        # BERT subnet
        bert_proj = self.bert_proj(bert_embedding)
        bert_contribution = self.f_bert(bert_proj)

        # Rubric group subnets
        group_contributions = {}
        for name in GROUP_NAMES:
            group_contributions[name] = self.group_subnets[name](rubric_features[name])

        # Combine based on mode
        if self.mode == "gated":
            # Query-conditioned gating
            gate_logits = self.gate_net(bert_proj)  # (batch, num_groups)
            gate_weights = torch.softmax(gate_logits, dim=-1)  # (batch, num_groups)

            logit = self.bias + bert_contribution
            for i, name in enumerate(GROUP_NAMES):
                logit = logit + gate_weights[:, i:i+1] * group_contributions[name]

        elif self.mode == "interaction":
            # Additive + interaction MLP
            logit = self.bias + bert_contribution
            for name in GROUP_NAMES:
                logit = logit + group_contributions[name]

            # Interaction term
            all_contribs = torch.cat(
                [bert_contribution] + [group_contributions[n] for n in GROUP_NAMES],
                dim=-1)  # (batch, 1+num_groups)
            interaction = self.interaction_net(all_contribs)
            logit = logit + interaction

        else:  # additive
            logit = self.bias + bert_contribution
            for name in GROUP_NAMES:
                logit = logit + group_contributions[name]

        scores = torch.sigmoid(logit)

        if return_contributions:
            contributions = {"bert": bert_contribution}
            contributions.update(group_contributions)
            if self.mode == "gated":
                contributions["gate_weights"] = gate_weights
            return scores, contributions
        return scores

    def get_rubric_scores(self, bert_embedding: torch.Tensor,
                          rubric_features: dict[str, torch.Tensor]) -> dict[str, torch.Tensor]:
        """Get per-rubric-group scores (sigmoid of each contribution).

        Returns dict mapping group name → (batch,) scores in [0, 1].
        """
        with torch.no_grad():
            _, contributions = self.forward(
                bert_embedding, rubric_features, return_contributions=True)
        return {k: torch.sigmoid(v).squeeze(-1)
                for k, v in contributions.items() if k != "gate_weights"}

    def get_feature_names(self) -> list[str]:
        return ["bert"] + GROUP_NAMES


class RubricGAMDataset(torch.utils.data.Dataset):
    """Dataset for RubricGAM training.

    Expects pre-computed BERT embeddings + rubric features grouped by category.
    """

    def __init__(self, bert_embeddings: torch.Tensor,
                 rubric_features: dict[str, torch.Tensor],
                 scores: torch.Tensor,
                 query_ids: torch.Tensor = None):
        self.bert_embeddings = bert_embeddings
        self.rubric_features = rubric_features
        self.scores = scores
        self.query_ids = query_ids

    def __len__(self):
        return len(self.scores)

    def __getitem__(self, idx):
        item = {
            "bert_embedding": self.bert_embeddings[idx],
            "score": self.scores[idx],
        }
        for group_name, features in self.rubric_features.items():
            item[f"rubric_{group_name}"] = features[idx]
        if self.query_ids is not None:
            item["query_id"] = self.query_ids[idx]
        return item
