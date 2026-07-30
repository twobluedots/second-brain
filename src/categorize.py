import json
import os
from functools import lru_cache

from config import CATEGORY_DESCRIPTIONS, DEFAULT_CATEGORIES, OLLAMA_MODEL
from src.logger import logger


def _build_prompt(text: str, description: str = None) -> str:
    category_list = "\n".join(
        f"- {name}: {desc}" for name, desc in CATEGORY_DESCRIPTIONS.items()
    )
    note_section = ""
    if description and description.strip():
        note_section += f"User context: {description.strip()}\n"
    note_section += f"Note: {text.strip()}"
    return (
        f"Categorize this personal note into exactly one category.\n"
        f'Return JSON only: {{"category": "<name>"}}\n\n'
        f"Categories:\n{category_list}\n\n"
        f"{note_section}"
    )


def _parse(raw: str) -> str:
    try:
        category = json.loads(raw.strip()).get("category", "")
        return category if category in DEFAULT_CATEGORIES else "journal"
    except Exception:
        return "journal"


def _with_openai(prompt: str) -> str:
    from openai import OpenAI
    response = OpenAI().chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        max_tokens=30,
        temperature=0,
    )
    return _parse(response.choices[0].message.content)


def _with_anthropic(prompt: str) -> str:
    from anthropic import Anthropic
    response = Anthropic().messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=30,
        system="You are a note categorizer. Return only valid JSON.",
        messages=[{"role": "user", "content": prompt}],
    )
    return _parse(response.content[0].text)


def _with_ollama(prompt: str) -> str:
    import ollama
    response = ollama.chat(
        model=OLLAMA_MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    return _parse(response["message"]["content"])


@lru_cache(maxsize=256)
def categorize(text: str, description: str = None) -> str:
    """Returns the single best category. Tries OpenAI → Anthropic → Ollama → 'journal'."""
    if not text or not text.strip():
        return "journal"
    prompt = _build_prompt(text, description)
    if os.environ.get("OPENAI_API_KEY"):
        try:
            result = _with_openai(prompt)
            logger.info("Categorized via OpenAI: %s", result)
            return result
        except Exception as e:
            logger.warning("OpenAI categorization failed, trying Anthropic: %s", e)
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            result = _with_anthropic(prompt)
            logger.info("Categorized via Anthropic: %s", result)
            return result
        except Exception as e:
            logger.warning("Anthropic categorization failed, trying Ollama: %s", e)
    try:
        result = _with_ollama(prompt)
        logger.info("Categorized via Ollama: %s", result)
        return result
    except Exception as e:
        logger.warning("Ollama categorization failed, defaulting to journal: %s", e)
    logger.warning("All categorization providers failed, defaulting to 'journal'")
    return "journal"
