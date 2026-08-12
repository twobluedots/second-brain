"""
Generator — LLM call #2 in the RAG pipeline.
Takes retrieved notes + query plan, returns a generated answer string.
"""

import os
from typing import Dict, List, Optional

from config import ANTHROPIC_MODEL, OPENAI_MODEL
from src.logger import logger
from src.rag.analyzer import QueryPlan

_INTENT_INSTRUCTIONS = {
    "factual": "Answer in 1-2 sentences. Cite which note the answer came from (e.g. 'In your note from [date]...'). If the notes don't contain a clear answer, say so honestly.",
    "qa":      "Answer in a short paragraph. Reference the notes where relevant.",
    "pattern": "Summarize the pattern or trend you see across these notes in a paragraph. Be specific — mention dates or categories where they reveal something meaningful.",
}

_SYSTEM = "You are a personal assistant answering questions from a user's private notes. Be concise and specific. Never invent information not present in the notes."


def format_note(note: Dict) -> str:
    """Formats a single note as '{date} | {category} | {content_type}\\n{content}'.

    Single source of truth for "what does the model see for one note" — used
    both for the generation prompt below and for eval context strings
    (experiments/ask_eval), so the two can't drift apart (see docs/bugs.md,
    2026-08-12: eval was checking faithfulness against context text that was
    missing the date the generator actually had).
    """
    content = (note.get("content") or "").strip()
    date = (note.get("created_at") or "")[:16]
    category = note.get("category") or "uncategorized"
    note_type = note.get("content_type") or "text"
    return f"{date} | {category} | {note_type}\n{content}"


def _format_notes(notes: List[Dict]) -> str:
    lines = [f"[{i}] {format_note(note)}" for i, note in enumerate(notes, 1)]
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
        date = (note.get("created_at") or "")[:16]
        content = (note.get("content") or "").strip()
        lines.append(f"• {date}: {content}")
    return "\n".join(lines)


def _with_openai(prompt: str) -> str:
    from openai import OpenAI
    response = OpenAI().chat.completions.create(
        model=OPENAI_MODEL,
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
        model=ANTHROPIC_MODEL,
        max_tokens=300,
        system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


def generate(query: str, plan: QueryPlan, notes: List[Dict]) -> tuple[str, Optional[str]]:
    """
    Generate an answer from retrieved notes.
    Returns (answer, model) — model is None when no LLM produced the answer
    (empty retrieval or plain fallback). The UI handles fallback disclaimers separately.
    """
    if not notes:
        return "I couldn't find any relevant notes for that query.", None

    prompt = _build_prompt(query, plan, notes)

    if os.environ.get("OPENAI_API_KEY"):
        try:
            answer = _with_openai(prompt)
            logger.info("Answer generated via OpenAI (intent=%s, notes=%d)", plan.intent, len(notes))
            return answer, f"openai:{OPENAI_MODEL}"
        except Exception as e:
            logger.warning("OpenAI generation failed: %s", e)

    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            answer = _with_anthropic(prompt)
            logger.info("Answer generated via Anthropic (intent=%s, notes=%d)", plan.intent, len(notes))
            return answer, f"anthropic:{ANTHROPIC_MODEL}"
        except Exception as e:
            logger.warning("Anthropic generation failed: %s", e)

    logger.warning("All generation providers failed, returning plain note list")
    return _plain_fallback(notes), None
