"""
Grades retrieval results against ground truth.

Metrics:
  recall          — was the expected note found anywhere in the results? (1.0 or 0.0; None for ambiguous)
  mrr             — Mean Reciprocal Rank: 1/rank if found, else 0.0; None for ambiguous rows
  llm_judge_score — fraction of top-3 notes judged relevant; only set for ambiguous rows
"""

import json


def _llm_judge(query: str, top3_texts: list[str]) -> float:
    """Score each of the top-3 notes as 0 or 1; return relevant_count / len."""
    numbered = "\n\n".join(f"Note {i + 1}: {t}" for i, t in enumerate(top3_texts))
    n = len(top3_texts)
    prompt = (
        f"Query: {query}\n\n"
        f"Rate each note as 0 (not relevant) or 1 (relevant) to the query.\n"
        f'Return JSON only: {{"scores": [array of {n} values, each 0 or 1]}}\n\n'
        f"{numbered}"
    )
    try:
        from openai import OpenAI
        response = OpenAI().chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a relevance judge. Return only valid JSON."},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            max_tokens=30,
            temperature=0,
        )
        data = json.loads(response.choices[0].message.content)
        scores = data.get("scores", [])
        if not scores:
            return 0.0
        return sum(scores) / len(scores)
    except Exception:
        return 0.0


def grade(
    retrieved_ids: list[str],
    expected_note_id: str,
    *,
    query: str = None,
    ambiguous: bool = False,
    note_texts: dict = None,
) -> dict:
    if ambiguous:
        top3 = retrieved_ids[:3]
        texts = [note_texts[rid] for rid in top3 if note_texts and rid in note_texts]
        score = _llm_judge(query, texts) if query and texts else 0.0
        return {"recall": None, "mrr": None, "llm_judge_score": score}

    if expected_note_id in retrieved_ids:
        rank = retrieved_ids.index(expected_note_id) + 1
        return {"recall": 1.0, "mrr": 1 / rank, "llm_judge_score": None}
    return {"recall": 0.0, "mrr": 0.0, "llm_judge_score": None}
