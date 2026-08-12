"""
Grades cached ask() pipeline records with RAGAS context metrics.

Loads a records file written by the collector, scores each record's
retrieved contexts for relevance and utilization, prints per-record and
average scores, and saves everything to experiments/artifacts/ask_eval/scores.
Rerunnable — a rerun costs judge calls only, never live ask() calls.

Usage:
  python -m experiments.ask_eval.grader
"""

import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from openai import AsyncOpenAI
from ragas.embeddings import OpenAIEmbeddings
from ragas.llms import llm_factory
from ragas.metrics.collections import (
    AnswerRelevancy,
    ContextRelevance,
    ContextUtilization,
    Faithfulness,
)
from ragas.metrics.result import MetricResult

from experiments.ask_eval.collector import RECORDS_DIR
from src.rag.generator import format_note

SCORES_DIR = Path(__file__).parent.parent / "artifacts/ask_eval/scores"
JUDGE_MODEL = "gpt-4o-mini"
EMBEDDING_MODEL = "text-embedding-3-small"


class FaithfulnessWithDecomposition(Faithfulness):
    """Faithfulness that also surfaces the atomic claims and per-claim NLI verdicts.

    ragas's Faithfulness.ascore() computes these internally (statement
    generation, then NLI verdict per statement) but only returns the
    collapsed ratio. We reuse those same private steps so we don't pay for
    extra LLM calls. Returned directly (not stashed on self) since one
    scorer instance is shared across concurrent record scoring.
    """

    async def ascore_with_decomposition(
        self, user_input: str, response: str, retrieved_contexts: list[str]
    ) -> tuple[MetricResult, list[dict]]:
        statements = await self._create_statements(user_input, response)
        if not statements:
            return MetricResult(value=float("nan")), []

        context_str = "\n".join(retrieved_contexts)
        verdicts = await self._create_verdicts(statements, context_str)
        decomposition = [
            {"statement": s.statement, "verdict": s.verdict, "reason": s.reason} for s in verdicts.statements
        ]

        score = self._compute_score(verdicts)
        return MetricResult(value=float(score)), decomposition


_RUN_ID_RE = re.compile(r"run_(\d{8}T\d{6})\.jsonl$")


def _latest_records_path() -> Path:
    candidates = [p for p in RECORDS_DIR.glob("run_*.jsonl") if _RUN_ID_RE.search(p.name)]
    if not candidates:
        raise FileNotFoundError(f"No run_<timestamp>.jsonl files found in {RECORDS_DIR}")
    return max(candidates, key=lambda p: _RUN_ID_RE.search(p.name).group(1))


def _load_records(records_path: Path) -> list[dict]:
    if not records_path.exists():
        raise FileNotFoundError(f"Records file not found: {records_path}")
    with open(records_path) as f:
        records = [json.loads(line) for line in f if line.strip()]
    if not records:
        raise ValueError(f"Records file is empty: {records_path}")
    return records


def _average(values: list[float | None]) -> float | None:
    scored = [v for v in values if v is not None]
    return sum(scored) / len(scored) if scored else None


def _fmt(value: float | None) -> str:
    return f"{value:.2f}" if value is not None else "n/a"


async def _run_scorer(semaphore: asyncio.Semaphore, name: str, question: str, coro) -> float | None:
    async with semaphore:
        try:
            result = await coro
            return result.value
        except Exception as e:
            print(f"  [warn] {name} failed for {question!r}: {e}")
            return None


async def _run_faithfulness_scorer(
    semaphore: asyncio.Semaphore, question: str, coro
) -> tuple[float | None, list[dict]]:
    async with semaphore:
        try:
            result, decomposition = await coro
            return result.value, decomposition
        except Exception as e:
            print(f"  [warn] faithfulness failed for {question!r}: {e}")
            return None, []


async def _score_record(
    record: dict,
    relevance_scorer,
    utilization_scorer,
    faithfulness_scorer,
    answer_relevancy_scorer,
    semaphore: asyncio.Semaphore,
) -> dict:
    question = record["user_input"]
    contexts = [format_note(c) for c in record["retrieved_contexts"]]
    response = record.get("response") or ""

    relevance_task = _run_scorer(
        semaphore, "context_relevance", question,
        relevance_scorer.ascore(user_input=question, retrieved_contexts=contexts),
    )

    # These three all judge the response — nothing to judge when there's no
    # response, so skip them rather than let RAGAS error.
    if not response:
        relevance_score = await relevance_task
        utilization_score = faithfulness_score = answer_relevancy_score = None
        faithfulness_decomposition = []
    else:
        utilization_task = _run_scorer(
            semaphore, "context_utilization", question,
            utilization_scorer.ascore(user_input=question, response=response, retrieved_contexts=contexts),
        )
        faithfulness_task = _run_faithfulness_scorer(
            semaphore, question,
            faithfulness_scorer.ascore_with_decomposition(
                user_input=question, response=response, retrieved_contexts=contexts
            ),
        )
        answer_relevancy_task = _run_scorer(
            semaphore, "answer_relevancy", question,
            answer_relevancy_scorer.ascore(user_input=question, response=response),
        )
        (
            relevance_score,
            utilization_score,
            (faithfulness_score, faithfulness_decomposition),
            answer_relevancy_score,
        ) = await asyncio.gather(relevance_task, utilization_task, faithfulness_task, answer_relevancy_task)

    return {
        "user_input": question,
        "response": response,
        "context_relevance": relevance_score,
        "context_utilization": utilization_score,
        "faithfulness": faithfulness_score,
        "faithfulness_decomposition": faithfulness_decomposition,
        "answer_relevancy": answer_relevancy_score,
        "retrieved_contexts": contexts,
    }


async def grade(records_path: Path | None = None) -> None:
    if records_path is None:
        records_path = _latest_records_path()
    records = _load_records(records_path)

    client = AsyncOpenAI()
    llm = llm_factory(JUDGE_MODEL, client=client, max_tokens=4096)
    embeddings = OpenAIEmbeddings(client=client, model=EMBEDDING_MODEL)
    relevance_scorer = ContextRelevance(llm=llm)
    utilization_scorer = ContextUtilization(llm=llm)
    faithfulness_scorer = FaithfulnessWithDecomposition(llm=llm)
    answer_relevancy_scorer = AnswerRelevancy(llm=llm, embeddings=embeddings)

    semaphore = asyncio.Semaphore(5)
    results = await asyncio.gather(*[
        _score_record(
            record, relevance_scorer, utilization_scorer, faithfulness_scorer, answer_relevancy_scorer, semaphore
        )
        for record in records
    ])

    for r in results:
        print(
            f"relevance={_fmt(r['context_relevance'])}  "
            f"utilization={_fmt(r['context_utilization'])}  "
            f"faithfulness={_fmt(r['faithfulness'])}  "
            f"answer_relevancy={_fmt(r['answer_relevancy'])}  "
            f"{r['user_input']}"
        )

    avg_relevance = _average([r["context_relevance"] for r in results])
    avg_utilization = _average([r["context_utilization"] for r in results])
    avg_faithfulness = _average([r["faithfulness"] for r in results])
    avg_answer_relevancy = _average([r["answer_relevancy"] for r in results])
    print(
        f"\nAVERAGE  relevance={_fmt(avg_relevance)}  utilization={_fmt(avg_utilization)}  "
        f"faithfulness={_fmt(avg_faithfulness)}  answer_relevancy={_fmt(avg_answer_relevancy)}"
    )

    SCORES_DIR.mkdir(parents=True, exist_ok=True)
    graded_at = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    scores_path = SCORES_DIR / f"{records_path.stem}__graded_{graded_at}.json"
    scores_path.write_text(json.dumps({
        "records_path": str(records_path),
        "results": results,
        "aggregate": {
            "context_relevance": avg_relevance,
            "context_utilization": avg_utilization,
            "faithfulness": avg_faithfulness,
            "answer_relevancy": avg_answer_relevancy,
        },
    }, indent=2))
    print(f"Saved to: {scores_path}")


if __name__ == "__main__":
    asyncio.run(grade())
