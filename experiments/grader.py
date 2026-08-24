"""
Grades retrieval results against ground truth.

Metrics:
  recall          — was the expected note found anywhere in the results? (1.0 or 0.0; None for ambiguous)
  mrr             — Mean Reciprocal Rank: 1/rank if found, else 0.0; None for ambiguous rows
  llm_judge_score — fraction of top-3 notes judged relevant; only set for ambiguous rows

grade_retrieval_multi() is the dataset2 counterpart of grade() for rows with
a list of valid ground-truth ids (e.g. "pattern"-intent rows where several
notes are all correct answers) instead of a single expected_note_id.

grade_generation() scores a generated answer with the same reference-free
RAGAS metrics as experiments/ask_eval/grader.py (context_relevance,
context_utilization, faithfulness, answer_relevancy) — duplicated rather
than imported so the two eval tracks (live-Storage ask_eval vs
ground-truth-based dataset2) stay independently evolvable, per the split
rationale in docs/eval-ask-grader.md. Same run(answer)/grade(answer) split
as retrieve()/grade() — build_generation_scorers()+grade_generation() never
call the generator; the caller runs it and passes the result in.
"""

import asyncio
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


def grade_retrieval_multi(retrieved_ids: list[str], expected_note_ids: list[str]) -> dict:
    """recall/mrr against a list of equally-valid ground-truth ids.

    recall = 1.0 if any expected id was retrieved, else 0.0.
    mrr    = 1/rank of the best-ranked matching id, else 0.0.
    """
    ranks = [retrieved_ids.index(rid) + 1 for rid in expected_note_ids if rid in retrieved_ids]
    if not ranks:
        return {"recall": 0.0, "mrr": 0.0}
    return {"recall": 1.0, "mrr": 1 / min(ranks)}


def grade_intent(
    actual_intent: str,
    actual_time_filter: str | None,
    actual_category_filter: str | None,
    expected_intent: str,
    expected_time_filter: str | None,
    expected_category_filter: str | None,
) -> dict:
    """Compare an already-produced QueryPlan's fields against dataset2's
    ask-row ground truth. Pure comparison — the caller runs the (pluggable,
    config["analyzer"]-selected) classifier via pipeline.intent.analyze()
    and passes its output in here, same split as retrieve()/grade().

    Only meaningful for target_system=="ask" rows — the analyzer is the
    Ask pipeline's classifier; the Search page never calls it in production,
    so there's no real code path to grade for "search" rows.
    """
    return {
        "intent_match": 1 if actual_intent == expected_intent else 0,
        "time_filter_match": 1 if actual_time_filter == expected_time_filter else 0,
        "category_filter_match": 1 if actual_category_filter == expected_category_filter else 0,
    }


GENERATION_METRICS = ["context_relevance", "context_utilization", "faithfulness", "answer_relevancy"]


def build_generation_scorers() -> dict:
    """Build the RAGAS scorer instances once per run (judge/embedding client
    setup is not free) — reused across every row's grade_generation() call."""
    from openai import AsyncOpenAI
    from ragas.embeddings import OpenAIEmbeddings
    from ragas.llms import llm_factory
    from ragas.metrics.collections import AnswerRelevancy, ContextRelevance, ContextUtilization, Faithfulness

    client = AsyncOpenAI()
    llm = llm_factory("gpt-4o-mini", client=client, max_tokens=4096)
    embeddings = OpenAIEmbeddings(client=client, model="text-embedding-3-small")
    return {
        "context_relevance": ContextRelevance(llm=llm),
        "context_utilization": ContextUtilization(llm=llm),
        "faithfulness": Faithfulness(llm=llm),
        "answer_relevancy": AnswerRelevancy(llm=llm, embeddings=embeddings),
    }


async def _grade_generation_async(
    question: str, response: str, contexts: list[str], metrics: list[str], scorers: dict
) -> dict:
    result = {m: None for m in GENERATION_METRICS}

    if "context_relevance" in metrics:
        try:
            r = await scorers["context_relevance"].ascore(user_input=question, retrieved_contexts=contexts)
            result["context_relevance"] = r.value
        except Exception as e:
            print(f"  [warn] context_relevance failed for {question!r}: {e}")

    # The other three all judge the response — nothing to judge when there's
    # no response (empty retrieval), so skip them rather than let RAGAS error.
    if not response:
        return result

    for name in ("context_utilization", "faithfulness"):
        if name in metrics:
            try:
                r = await scorers[name].ascore(user_input=question, response=response, retrieved_contexts=contexts)
                result[name] = r.value
            except Exception as e:
                print(f"  [warn] {name} failed for {question!r}: {e}")

    if "answer_relevancy" in metrics:
        try:
            r = await scorers["answer_relevancy"].ascore(user_input=question, response=response)
            result["answer_relevancy"] = r.value
        except Exception as e:
            print(f"  [warn] answer_relevancy failed for {question!r}: {e}")

    return result


def grade_generation(
    question: str, response: str, contexts: list[str], metrics: list[str], scorers: dict
) -> dict:
    """Score an already-generated answer. Pure scoring — the caller runs the
    generator (src.rag.generator.generate(), via pipeline.generation) and
    passes its output in here, same split as retrieve()/grade()."""
    return asyncio.run(_grade_generation_async(question, response, contexts, metrics, scorers))
