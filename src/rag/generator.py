"""
Generator — LLM call #2 in the RAG pipeline.
Takes retrieved notes + query plan, returns a generated answer string.
"""

import os
from typing import Dict, List, Optional

from src.logger import logger
from src.rag.analyzer import QueryPlan

_NOTE_TRUNCATE = 400  # chars per note in the prompt context

_INTENT_INSTRUCTIONS = {
    "factual": "Answer in 1-2 sentences. Cite which note the answer came from (e.g. 'In your note from [date]...'). If the notes don't contain a clear answer, say so honestly.",
    "qa":      "Answer in a short paragraph. Reference the notes where relevant.",
    "pattern": "Summarize the pattern or trend you see across these notes in a paragraph. Be specific — mention dates or categories where they reveal something meaningful.",
}

_SYSTEM = "You are a personal assistant answering questions from a user's private notes. Be concise and specific. Never invent information not present in the notes."


def _format_notes(notes: List[Dict]) -> str:
    lines = []
    for i, note in enumerate(notes, 1):
        content = (note.get("content") or "").strip()
        if len(content) > _NOTE_TRUNCATE:
            content = content[:_NOTE_TRUNCATE] + "..."
        date = (note.get("created_at") or "")[:10]
        category = note.get("category") or "uncategorized"
        note_type = note.get("content_type") or "text"
        lines.append(f"[{i}] {date} | {category} | {note_type}\n{content}")
    return "\n---\n".join(lines)


def _build_prompt(query: str, plan: QueryPlan, notes: List[Dict]) -> str:
    category_hint = ""
    if plan.category_filter and plan.intent != "browse":
        category_hint = f"\nThe user was asking about their {plan.category_filter} notes — weight those accordingly.\n"

    instruction = _INTENT_INSTRUCTIONS.get(plan.intent, _INTENT_INSTRUCTIONS["qa"])
    notes_text = _format_notes(notes)

    return (
        f"User's question: {query}\n"
        f"{category_hint}\n"
        f"Notes ({len(notes)} retrieved):\n---\n{notes_text}\n---\n\n"
        f"{instruction}"
    )


def _plain_fallback(notes: List[Dict]) -> str:
    """Used when all LLM providers fail — format notes as a readable list."""
    lines = ["Here are the most relevant notes I found:\n"]
    for note in notes:
        date = (note.get("created_at") or "")[:10]
        content = (note.get("content") or "").strip()
        if len(content) > _NOTE_TRUNCATE:
            content = content[:_NOTE_TRUNCATE] + "..."
        lines.append(f"• {date}: {content}")
    return "\n".join(lines)


def _with_openai(prompt: str) -> str:
    from openai import OpenAI
    response = OpenAI().chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": prompt},
        ],
        max_tokens=300,
        temperature=0.3,
    )
    return response.choices[0].message.content.strip()


def _with_anthropic(prompt: str) -> str:
    from anthropic import Anthropic
    response = Anthropic().messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


def generate(query: str, plan: QueryPlan, notes: List[Dict]) -> str:
    """
    Generate an answer from retrieved notes.
    Returns a plain string — the UI handles fallback disclaimers separately.
    """
    if not notes:
        return "I couldn't find any relevant notes for that query."

    prompt = _build_prompt(query, plan, notes)

    if os.environ.get("OPENAI_API_KEY"):
        try:
            answer = _with_openai(prompt)
            logger.info("Answer generated via OpenAI (intent=%s, notes=%d)", plan.intent, len(notes))
            return answer
        except Exception as e:
            logger.warning("OpenAI generation failed: %s", e)

    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            answer = _with_anthropic(prompt)
            logger.info("Answer generated via Anthropic (intent=%s, notes=%d)", plan.intent, len(notes))
            return answer
        except Exception as e:
            logger.warning("Anthropic generation failed: %s", e)

    logger.warning("All generation providers failed, returning plain note list")
    return _plain_fallback(notes)
