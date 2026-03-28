"""Production scorer: ModernBERT + Rubric GAM inference.

Usage:
    from inference.scorer import NLWebScorer
    scorer = NLWebScorer("checkpoints/modernbert_large_pure/best_model.pt",
                         "checkpoints/rubric_gam/additive/best_rubric_gam.pt")
    results = scorer.score(query="tent", items=[{"name": "...", "schema_json": "..."}])
    # Each result: {"score": 85, "rubric_scores": {"bert": 0.8, "relevance": 0.9, ...}}
"""

import json
from pathlib import Path

import torch
from transformers import AutoTokenizer

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from models.modernbert_scorer import ModernBERTScorer
from models.rubric_gam import RubricGAM, RUBRIC_GROUPS, GROUP_NAMES
from data.prepare_data import compute_rubric_features, _extract_readable_text


class NLWebScorer:
    """End-to-end scorer: ModernBERT (pure text) + Rubric GAM."""

    def __init__(self, bert_checkpoint: str, gam_checkpoint: str,
                 device: str = None, max_length: int = 1024):
        self.device = torch.device(
            device or ("cuda" if torch.cuda.is_available()
                       else "mps" if torch.backends.mps.is_available()
                       else "cpu"))
        self.max_length = max_length

        # Load BERT model (pure text mode)
        bert_state = torch.load(bert_checkpoint, map_location=self.device,
                                weights_only=False)
        bert_config = bert_state["config"]
        model_name = bert_config.get("model_name", "answerdotai/ModernBERT-large")
        pure_text = bert_config.get("pure_text", True)

        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.bert_model = ModernBERTScorer(
            model_name=model_name,
            use_rubric_features=not pure_text,
        ).to(self.device)
        self.bert_model.load_state_dict(bert_state["model_state_dict"])
        self.bert_model.eval()

        # Load Rubric GAM
        gam_state = torch.load(gam_checkpoint, map_location=self.device,
                               weights_only=False)
        gam_config = gam_state["config"]
        self.norm_stats = gam_state["norm_stats"]

        self.gam_model = RubricGAM(
            bert_dim=gam_state.get("bert_dim", 1024),
            bert_proj_dim=gam_config.get("bert_proj_dim", 64),
            bert_hidden=gam_config.get("bert_hidden", [128, 64, 32]),
            rubric_hidden=gam_config.get("rubric_hidden", [64, 32]),
            activation=gam_config.get("activation", "relu"),
            dropout=gam_config.get("dropout", 0.1),
            mode=gam_state.get("mode", "additive"),
            interaction_hidden=gam_config.get("interaction_hidden", [16]),
        ).to(self.device)
        self.gam_model.load_state_dict(gam_state["model_state_dict"])
        self.gam_model.eval()

    def _build_item_text(self, query: str, item: dict) -> str:
        schema_json = item.get("schema_json", "")
        name = item.get("name", "")
        description = _extract_readable_text(schema_json, name)
        if len(description) > 4000:
            description = description[:4000]
        return f"{query} [SEP] {description}"

    def _normalize_group(self, group_name: str, values: list[float]) -> torch.Tensor:
        """Normalize a group's features using saved stats."""
        group_stats = self.norm_stats.get(group_name, [])
        normed = []
        for col, val in enumerate(values):
            if col < len(group_stats):
                s = group_stats[col]
                normed.append((val - s["mean"]) / s["std"])
            else:
                normed.append(val)
        return normed

    def _compute_rubric_features(self, query: str, items: list[dict]) -> dict[str, torch.Tensor]:
        """Compute and normalize rubric features for a batch of items."""
        grouped = {name: [] for name in GROUP_NAMES}

        for item in items:
            name = item.get("name", "")
            schema_json = item.get("schema_json", "")
            rubric = compute_rubric_features(query, name, schema_json)

            for group_name, feature_names in RUBRIC_GROUPS.items():
                raw = [rubric.get(f, 0.0) for f in feature_names]
                normed = self._normalize_group(group_name, raw)
                grouped[group_name].append(normed)

        return {name: torch.tensor(vals, dtype=torch.float32, device=self.device)
                for name, vals in grouped.items()}

    @torch.no_grad()
    def score(self, query: str, items: list[dict],
              return_rubric_scores: bool = False) -> list[dict]:
        """Score a batch of items against a query.

        Args:
            query: User search query
            items: List of dicts with 'name' and optionally 'schema_json'
            return_rubric_scores: Include per-rubric-group scores

        Returns:
            List of dicts with 'score' (0-100 int) and optionally 'rubric_scores'
        """
        if not items:
            return []

        # Tokenize and get BERT [CLS] embeddings
        texts = [self._build_item_text(query, item) for item in items]
        encodings = self.tokenizer(
            texts, max_length=self.max_length, padding=True,
            truncation=True, return_tensors="pt"
        ).to(self.device)

        embeddings = self.bert_model.get_embeddings(
            encodings["input_ids"], encodings["attention_mask"])

        # Compute rubric features
        rubric_features = self._compute_rubric_features(query, items)

        # GAM forward
        scores_tensor, contributions = self.gam_model(
            embeddings, rubric_features, return_contributions=True)

        # Convert to 0-100 integer scores
        scores_100 = (scores_tensor.squeeze(-1) * 100).clamp(0, 100).cpu()

        results = []
        for i in range(len(items)):
            result = {"score": int(scores_100[i].round().item())}
            if return_rubric_scores:
                result["rubric_scores"] = {
                    k: round(torch.sigmoid(v[i]).item(), 3)
                    for k, v in contributions.items()
                    if k != "gate_weights"
                }
                if "gate_weights" in contributions:
                    result["gate_weights"] = {
                        GROUP_NAMES[j]: round(contributions["gate_weights"][i, j].item(), 3)
                        for j in range(len(GROUP_NAMES))
                    }
            results.append(result)

        return results

    @torch.no_grad()
    def score_single(self, query: str, item: dict) -> int:
        """Score a single item. Returns 0-100 integer."""
        results = self.score(query, [item])
        return results[0]["score"]
