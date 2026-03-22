"""ModernBERT-based relevance scorer with integrated rubric features.

Fine-tunes ModernBERT on (query, item_description) pairs to predict
GPT-4.1 relevance scores (0-1). Concatenates [CLS] embedding with
rubric features (type match, query coverage, completeness, quality)
before the regression head — end-to-end training.

Rubric features mirror what GPT-4.1 evaluates:
  - Relevance: query_term_coverage, title_query_overlap, exact_query_match, word_overlap
  - Type match: schema_type embedding, type_match score
  - Completeness: description_length, schema_field_count, has_rating, has_price, has_image
  - Quality: has_date, content_word_count, has_author
  - Specificity: query_word_count, name_word_count, difficulty
"""

import torch
import torch.nn as nn
from transformers import AutoModel, AutoTokenizer


# Scalar rubric features (order matters — must match ScorerDataset)
SCALAR_FEATURES = [
    "query_term_coverage",
    "title_query_overlap",
    "exact_query_match",
    "query_item_word_overlap",
    "type_match",
    "description_length",
    "schema_field_count",
    "has_rating",
    "has_price",
    "has_image",
    "has_date",
    "content_word_count",
    "has_author",
    "query_word_count",
    "name_word_count",
    "difficulty",
]


class ModernBERTScorer(nn.Module):
    """ModernBERT with optional rubric features and a regression head.

    Architecture (use_rubric_features=True):
        ModernBERT encoder → [CLS] (hidden_size)
        + schema_type → Embedding(N, 8)
        + 16 scalar rubric features
        → concat → Linear(hidden+8+16, 256) → ReLU → Dropout → Linear(256, 1) → Sigmoid

    Architecture (use_rubric_features=False, pure-text mode):
        ModernBERT encoder → [CLS] (hidden_size)
        → Linear(hidden, 256) → ReLU → Dropout → Linear(256, 1) → Sigmoid
    """

    def __init__(self, model_name: str = "answerdotai/ModernBERT-base",
                 dropout: float = 0.1,
                 num_schema_types: int = 30,
                 schema_embed_dim: int = 8,
                 use_rubric_features: bool = True):
        super().__init__()
        self.encoder = AutoModel.from_pretrained(model_name)
        hidden_size = self.encoder.config.hidden_size
        self.use_rubric_features = use_rubric_features

        if use_rubric_features:
            self.schema_embed = nn.Embedding(num_schema_types + 1, schema_embed_dim)
            num_scalar = len(SCALAR_FEATURES)
            feat_dim = hidden_size + schema_embed_dim + num_scalar
        else:
            self.schema_embed = None
            feat_dim = hidden_size

        self.regression_head = nn.Sequential(
            nn.Linear(feat_dim, 256),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(256, 1),
            nn.Sigmoid(),
        )

    def forward(self, input_ids: torch.Tensor, attention_mask: torch.Tensor,
                schema_type_idx: torch.Tensor = None,
                rubric_features: torch.Tensor = None,
                return_embeddings: bool = False):
        """Forward pass.

        Args:
            input_ids: (batch, seq_len)
            attention_mask: (batch, seq_len)
            schema_type_idx: (batch,) long — schema type indices
            rubric_features: (batch, num_scalar_features) float — all scalar features
            return_embeddings: return [CLS] embeddings too

        Returns:
            scores: (batch, 1) in [0, 1]
            embeddings: (batch, hidden_size) if return_embeddings
        """
        outputs = self.encoder(input_ids=input_ids, attention_mask=attention_mask)
        cls_embedding = outputs.last_hidden_state[:, 0, :]

        parts = [cls_embedding]

        if self.use_rubric_features:
            if schema_type_idx is not None and self.schema_embed is not None:
                parts.append(self.schema_embed(schema_type_idx))
            if rubric_features is not None:
                parts.append(rubric_features)

        combined = torch.cat(parts, dim=-1)
        scores = self.regression_head(combined)

        if return_embeddings:
            return scores, cls_embedding
        return scores

    def get_embeddings(self, input_ids: torch.Tensor,
                       attention_mask: torch.Tensor) -> torch.Tensor:
        """Extract [CLS] embeddings without the regression head."""
        with torch.no_grad():
            outputs = self.encoder(input_ids=input_ids, attention_mask=attention_mask)
        return outputs.last_hidden_state[:, 0, :]


class ScorerDataset(torch.utils.data.Dataset):
    """Dataset for ModernBERT scorer training with rubric features."""

    def __init__(self, examples: list[dict], tokenizer: AutoTokenizer,
                 max_length: int = 512, schema_mapping: dict = None):
        self.examples = examples
        self.tokenizer = tokenizer
        self.max_length = max_length
        self.schema_mapping = schema_mapping or {}

        # Assign integer query IDs for ranking loss
        queries = sorted(set(ex["query"] for ex in examples))
        self.query_to_id = {q: i for i, q in enumerate(queries)}
        self.query_ids = [self.query_to_id[ex["query"]] for ex in examples]

        # Build query group index: query_id → [example indices]
        self.query_groups = {}
        for idx, qid in enumerate(self.query_ids):
            self.query_groups.setdefault(qid, []).append(idx)

    def __len__(self):
        return len(self.examples)

    def __getitem__(self, idx):
        ex = self.examples[idx]
        encoding = self.tokenizer(
            ex["item_text"],
            max_length=self.max_length,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )

        schema_type = ex.get("schema_type", "Unknown")
        if isinstance(schema_type, list):
            schema_type = schema_type[0] if schema_type else "Unknown"

        # Build rubric feature vector in consistent order
        rubric_values = [ex.get(k, 0.0) for k in SCALAR_FEATURES]

        return {
            "input_ids": encoding["input_ids"].squeeze(0),
            "attention_mask": encoding["attention_mask"].squeeze(0),
            "score": torch.tensor(ex["score"], dtype=torch.float32),
            "schema_type_idx": torch.tensor(
                self.schema_mapping.get(schema_type, len(self.schema_mapping)),
                dtype=torch.long),
            "rubric_features": torch.tensor(rubric_values, dtype=torch.float32),
            "query_id": torch.tensor(self.query_ids[idx], dtype=torch.long),
        }
