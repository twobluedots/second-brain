"""
Query analyzer — LLM call #1 in the RAG pipeline.
Takes raw user query, returns a structured QueryPlan for retrieval and generation.
"""

import json
import os
from dataclasses import dataclass
from typing import Optional

from config import ANTHROPIC_MODEL, DEFAULT_CATEGORIES, OPENAI_MODEL
from src.logger import logger


@dataclass
class QueryPlan:
    intent: str                     # "browse" | "factual" | "qa" | "pattern"
    time_filter: Optional[str]      # None | "today" | "this_week" | "this_month"
    category_filter: Optional[str]  # None | one of DEFAULT_CATEGORIES
    content_type: Optional[str]     # None | "voice" | "image" | "text"
    k: int                          # notes to retrieve (0 = unused for browse)
    model: Optional[str] = None     # which LLM produced this plan; None = default fallback


_DEFAULT_PLAN = QueryPlan(intent="qa", time_filter=None, category_filter=None, content_type=None, k=8)

_SYSTEM = "You are a query analyzer for a personal note-taking app. Return only valid JSON."

_PROMPT = """Extract search parameters from this query. Return JSON only.

{{
  "intent": "browse | factual | qa | pattern",
  "time_filter": null | "today" | "this_week" | "this_month",
  "category_filter": null | "task" | "mood" | "journal" | "learning" | "reference" | "insight" | "achievement",
  "content_type": null | "voice" | "image" | "text",
  "k": 5
}}

Intent rules:
- browse: wants a list of notes ("show me", "list", "find all", time or type filter only)
- factual: looking for a specific stored fact ("where did I put", specific named item like a manual, address, recipe)
- qa: open question needing synthesis from multiple notes ("what have I been", "how do I", "why")
- pattern: aggregation over time ("lately", "this month", "how has my mood been", "what keeps coming up")

k values: factual=5, qa=8, pattern=20, browse=0

Query: {query}"""


def _parse(raw: str) -> Optional[QueryPlan]:
    try:
        data = json.loads(raw.strip())
        intent = data.get("intent", "qa")
        if intent not in ("browse", "factual", "qa", "pattern"):
            intent = "qa"
        category = data.get("category_filter")
        if category and category not in DEFAULT_CATEGORIES:
            category = None
        content_type = data.get("content_type")
        if content_type and content_type not in ("voice", "image", "text"):
            content_type = None
        time_filter = data.get("time_filter")
        if time_filter and time_filter not in ("today", "this_week", "this_month"):
            time_filter = None
        k = data.get("k", 8)
        if not isinstance(k, int) or k <= 0:
            k = 8
        return QueryPlan(
            intent=intent,
            time_filter=time_filter,
            category_filter=category,
            content_type=content_type,
            k=k,
        )
    except Exception:
        return None


def _with_openai(query: str) -> Optional[QueryPlan]:
    from openai import OpenAI
    response = OpenAI().chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": _PROMPT.format(query=query)},
        ],
        response_format={"type": "json_object"},
        max_tokens=100,
        temperature=0,
    )
    return _parse(response.choices[0].message.content)


def _with_anthropic(query: str) -> Optional[QueryPlan]:
    from anthropic import Anthropic
    response = Anthropic().messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=100,
        system=_SYSTEM,
        messages=[{"role": "user", "content": _PROMPT.format(query=query)}],
    )
    return _parse(response.content[0].text)


def analyze_query(query: str) -> QueryPlan:
    """
    Analyze a user query and return a structured QueryPlan.
    Tries OpenAI → Anthropic → plain default (qa, k=8).
    """
    if os.environ.get("OPENAI_API_KEY"):
        try:
            plan = _with_openai(query)
            if plan:
                plan.model = f"openai:{OPENAI_MODEL}"
                logger.info("Query analyzed via OpenAI: intent=%s k=%d", plan.intent, plan.k)
                return plan
        except Exception as e:
            logger.warning("OpenAI query analysis failed: %s", e)

    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            plan = _with_anthropic(query)
            if plan:
                plan.model = f"anthropic:{ANTHROPIC_MODEL}"
                logger.info("Query analyzed via Anthropic: intent=%s k=%d", plan.intent, plan.k)
                return plan
        except Exception as e:
            logger.warning("Anthropic query analysis failed: %s", e)

    logger.warning("All query analysis providers failed, using default plan")
    return _DEFAULT_PLAN
