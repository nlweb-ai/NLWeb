"""Clean prepared NLWebScorer training data.

Fixes three issues found by analyze_noise.py:
1. Removes empty items where item_text == "query [SEP] []" (retrieval failures)
2. Deduplicates exact-duplicate entries within the same (site, query) group,
   keeping a single entry with the median score across duplicates.
3. Resolves near-duplicate conflicts: within the same query, items with >70%
   word overlap but >0.2 score difference create conflicting gradients.
   Keeps only the higher-scored item from each conflicting pair.

Usage:
    # Preview what would change (dry run):
    python -m data.clean_data --data-dir data/prepared_hard --dry-run

    # Clean in-place:
    python -m data.clean_data --data-dir data/prepared_hard

    # Clean to a new directory:
    python -m data.clean_data --data-dir data/prepared_hard --output-dir data/prepared_hard_clean
"""

import argparse
import json
import re
import statistics
from collections import defaultdict
from pathlib import Path


def _text_overlap(text_a, text_b):
    """Jaccard similarity between two texts (word-level)."""
    words_a = set(re.findall(r'\w+', text_a.lower()))
    words_b = set(re.findall(r'\w+', text_b.lower()))
    if not words_a or not words_b:
        return 0.0
    return len(words_a & words_b) / len(words_a | words_b)


def load_jsonl(path):
    with open(path) as f:
        return [json.loads(line) for line in f]


def write_jsonl(data, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for item in data:
            f.write(json.dumps(item) + "\n")


def clean_split(examples, split_name, verbose=True):
    """Clean a single data split. Returns cleaned examples and stats."""
    n_before = len(examples)

    # Step 1: Remove empty items (retrieval failures)
    empty_removed = 0
    cleaned = []
    for ex in examples:
        if ex["item_text"] == ex["query"] + " [SEP] []":
            empty_removed += 1
        else:
            cleaned.append(ex)

    # Step 2: Deduplicate exact-duplicate entries within same (site, query)
    # Group by (site, query)
    query_groups = defaultdict(list)
    for ex in cleaned:
        query_groups[(ex["site"], ex["query"])].append(ex)

    deduped = []
    dups_removed = 0
    dups_merged = 0

    for (site, query), items in query_groups.items():
        # Group by item_text within this query
        text_groups = defaultdict(list)
        for ex in items:
            text_groups[ex["item_text"]].append(ex)

        for item_text, group in text_groups.items():
            if len(group) == 1:
                deduped.append(group[0])
                continue

            # Multiple entries with identical text — check if scores differ
            scores = [ex["score"] for ex in group]
            if max(scores) - min(scores) < 0.01:
                # All scores identical — just keep one
                deduped.append(group[0])
                dups_removed += len(group) - 1
            else:
                # Scores differ — merge: keep one entry with median score
                median_score = statistics.median(scores)
                merged = dict(group[0])  # copy first entry
                merged["score"] = median_score
                deduped.append(merged)
                dups_merged += len(group) - 1
                dups_removed += len(group) - 1

    # Step 3: Remove near-duplicate conflicts within same query
    # Items with >70% word overlap but >0.2 score diff create conflicting
    # gradients — the model sees nearly identical text but different targets.
    # Keep the higher-scored item from each conflicting pair.
    query_groups2 = defaultdict(list)
    for ex in deduped:
        query_groups2[(ex["site"], ex["query"])].append(ex)

    near_dup_removed = 0
    final = []

    for (site, query), items in query_groups2.items():
        if len(items) < 2:
            final.extend(items)
            continue

        # Mark items to remove (greedy: remove lower-scored item in conflict)
        remove = set()
        for i in range(len(items)):
            if i in remove:
                continue
            for j in range(i + 1, len(items)):
                if j in remove:
                    continue
                score_diff = abs(items[i]["score"] - items[j]["score"])
                if score_diff < 0.2:
                    continue
                overlap = _text_overlap(items[i]["item_text"], items[j]["item_text"])
                if overlap > 0.7:
                    # Remove the lower-scored item
                    if items[i]["score"] < items[j]["score"]:
                        remove.add(i)
                    else:
                        remove.add(j)

        for i, ex in enumerate(items):
            if i not in remove:
                final.append(ex)
            else:
                near_dup_removed += 1

    n_after = len(final)

    stats = {
        "split": split_name,
        "before": n_before,
        "empty_removed": empty_removed,
        "dups_removed": dups_removed,
        "dups_merged": dups_merged,
        "near_dup_removed": near_dup_removed,
        "after": n_after,
    }

    if verbose:
        print(f"\n  {split_name}:")
        print(f"    Before: {n_before}")
        if empty_removed > 0:
            print(f"    Empty items removed: {empty_removed}")
        if dups_merged > 0:
            print(f"    Duplicate groups merged (median score): {dups_merged} "
                  f"entries collapsed")
        if dups_removed > 0 and dups_merged == 0:
            print(f"    Exact duplicates removed: {dups_removed}")
        if near_dup_removed > 0:
            print(f"    Near-duplicate conflicts resolved: {near_dup_removed} "
                  f"lower-scored items removed")
        print(f"    After: {n_after} ({n_before - n_after} removed)")

    return final, stats


def main():
    parser = argparse.ArgumentParser(description="Clean prepared training data")
    parser.add_argument("--data-dir", type=str, default="data/prepared_hard",
                        help="Directory with prepared JSONL files")
    parser.add_argument("--output-dir", type=str, default=None,
                        help="Output directory (default: overwrite in-place)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Only report what would change, don't write")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    data_dir = project_root / args.data_dir
    output_dir = project_root / args.output_dir if args.output_dir else data_dir

    print(f"Cleaning data in {data_dir}")
    if args.dry_run:
        print("  (DRY RUN — no files will be written)")

    splits = ["train", "val", "test"]
    if (data_dir / "holdout_eval.jsonl").exists():
        splits.append("holdout_eval")

    all_stats = []
    for split in splits:
        path = data_dir / f"{split}.jsonl"
        if not path.exists():
            print(f"  Skipping {split} (file not found)")
            continue

        examples = load_jsonl(path)
        cleaned, stats = clean_split(examples, split)
        all_stats.append(stats)

        if not args.dry_run and stats["before"] != stats["after"]:
            out_path = output_dir / f"{split}.jsonl"
            write_jsonl(cleaned, out_path)
            print(f"    Written to {out_path}")

    # Summary
    total_before = sum(s["before"] for s in all_stats)
    total_after = sum(s["after"] for s in all_stats)
    total_empty = sum(s["empty_removed"] for s in all_stats)
    total_merged = sum(s["dups_merged"] for s in all_stats)
    total_near_dup = sum(s["near_dup_removed"] for s in all_stats)

    print(f"\n{'='*50}")
    print(f"SUMMARY")
    print(f"{'='*50}")
    print(f"  Total before: {total_before}")
    print(f"  Empty items removed: {total_empty}")
    print(f"  Duplicates merged (median): {total_merged} entries collapsed")
    print(f"  Near-dup conflicts resolved: {total_near_dup} lower-scored removed")
    print(f"  Total after: {total_after} ({total_before - total_after} removed, "
          f"{100*(total_before - total_after)/total_before:.1f}%)")

    if args.dry_run:
        print(f"\n  Run without --dry-run to apply changes.")


if __name__ == "__main__":
    main()
