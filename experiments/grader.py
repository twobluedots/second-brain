"""
Grades retrieval results against ground truth.

Metrics:
  recall    — was the expected note found anywhere in the results? (1.0 or 0.0)
  precision — was the expected note ranked first? (1/rank if found, else 0.0)
"""


def grade(retrieved_ids: list[str], expected_note_id: str) -> dict:
    if expected_note_id in retrieved_ids:
        rank = retrieved_ids.index(expected_note_id) + 1
        return {"recall": 1.0, "precision": 1 / rank}
    return {"recall": 0.0, "precision": 0.0}
