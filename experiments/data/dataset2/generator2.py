"""
Generate synthetic notes + eval queries from templates2.yaml.

Parallel to generator.py (which stays pointed at templates.yaml / dataset1) —
templates2's ask-aware schema (query_hints_search / query_hints_ask with intent,
expected_time_filter, expected_category_filter, expected_note_ids) doesn't fit
generator.py's flat query_hints format, so this is its own script rather than a
branch inside the original. Same pattern as ragas_generate.py / ragas_testset/generate.py
existing alongside generator.py for a different eval strategy.

Outputs:
  notes2.jsonl     — one note per line: {id, type, category, language, days_ago, text}
  eval_set2.jsonl  — one query row per line:
    search rows: {note_id, query, target_system: "search", expected_note_ids}
    ask rows:    {note_id, query, target_system: "ask", intent, expected_time_filter,
                  expected_category_filter, expected_note_ids}

Resume-safe: skips notes whose id already appears in notes2.jsonl.
"""

import json
import os
import yaml
from pathlib import Path
from openai import OpenAI

DIR = Path(__file__).parent
TEMPLATES_FILE = DIR / "templates2.yaml"
NOTES_FILE = DIR / "notes2.jsonl"
EVAL_FILE = DIR / "eval_set2.jsonl"

SYSTEM_PROMPT = """You generate realistic personal notes for a second-brain app.

The person is a developer in their late 20s-early 30s, building a personal knowledge app for
their own use. Their attention jumps between topics, thoughts arrive in fragments, and they
often start something and don't finish it in one sitting. Notes are raw and personal — run-on
sentences, self-interruptions, no polish.

Voice notes sound like talking to yourself mid-thought. Text notes are direct, sometimes just
fragments. Both feel like they were captured in 30 seconds to avoid losing the thought.

Return ONLY valid JSON in this exact shape:
{
  "text": "<the note text>",
  "search_queries": ["<rephrased search-style query 1>", "<rephrased search-style query 2>"],
  "ask_queries": ["<rephrased ask-style query 1>", "<rephrased ask-style query 2>"]
}

search_queries must have exactly as many entries, in the same order, as the search-style hints
given — short, keyword-like, how someone would type into a search box.

ask_queries must have exactly as many entries, in the same order, as the ask-style hints given —
rephrase naturally but preserve what's actually being asked; these are full natural questions,
not keywords."""


def build_prompt(template: dict) -> str:
    lines = [
        f"Generate a {template['type']} note in {template['language']}.",
        f"Category: {template['category']}",
        f"Target length: {template['word_range'][0]}–{template['word_range'][1]} words",
        "",
        f"Scenario: {template['scenario'].strip()}",
        "",
        f"Style: {template['style_notes'].strip()}",
    ]
    if template["type"] == "voice":
        lines += [
            "",
            "This is a raw Whisper speech-to-text transcript — no cleanup or repunctuation step. "
            "Whisper adds basic sentence punctuation on its own (periods, commas, question marks). "
            "It never produces emoji — do not include any.",
            "",
            "Match this register exactly (real examples of the tone to hit):",
            '  - "today\'s been kind of a rough one, don\'t really know why, just felt off since '
            'this morning, tired I guess, or maybe just annoyed, didn\'t really do much"',
            '  - "okay need to remember to call the dentist tomorrow before noon because they '
            'close early on fridays, also need to cancel that subscription thing before it renews"',
            '  - "so today was weird, spent most of it just doing nothing basically then like the '
            'last hour before dinner I got through like three things I\'d been putting off, don\'t '
            'really know why it happens like that but it does"',
            '  - "wasn\'t expecting to feel this stressed just from being at the store, too many '
            'people, too loud, needed to step outside for a sec, don\'t really know why it hit me '
            'that hard today"',
        ]
    lines += [
        "",
        "Search-style query hints (short, keyword-like — use as inspiration, rephrase naturally):",
    ]
    for hint in template.get("query_hints_search", []):
        lines.append(f"  - {hint}")
    lines += [
        "",
        "Ask-style query hints (natural full questions — rephrase naturally, keep the same underlying question):",
    ]
    for hint in template.get("query_hints_ask", []):
        lines.append(f"  - {hint['text']}")
    return "\n".join(lines)


def load_existing_ids() -> set[str]:
    if not NOTES_FILE.exists():
        return set()
    ids = set()
    with open(NOTES_FILE) as f:
        for line in f:
            line = line.strip()
            if line:
                ids.add(json.loads(line)["id"])
    return ids


def flatten_templates(data: dict) -> list[dict]:
    templates = []
    for group in data.values():
        if isinstance(group, list):
            templates.extend(group)
    return templates


def generate_note(client: OpenAI, model: str, template: dict) -> dict:
    response = client.chat.completions.create(
        model=model,
        temperature=0.6,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_prompt(template)},
        ],
    )
    return json.loads(response.choices[0].message.content)


def main():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")

    use_ollama = os.getenv("USE_OLLAMA", "false").lower() == "true"
    if use_ollama:
        client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
        model = os.getenv("OLLAMA_MODEL", "llama3.2")
    else:
        client = OpenAI(api_key=api_key)
        model = "gpt-4o-mini"
    print(f"Backend: {'Ollama' if use_ollama else 'OpenAI'} — model: {model}")

    with open(TEMPLATES_FILE) as f:
        data = yaml.safe_load(f)

    templates = flatten_templates(data)
    existing_ids = load_existing_ids()
    skipped = len(existing_ids)
    if skipped:
        print(f"Resuming — skipping {skipped} already generated notes")

    with open(NOTES_FILE, "a", buffering=1) as notes_f, open(EVAL_FILE, "a", buffering=1) as eval_f:
        for i, template in enumerate(templates):
            tid = template["id"]

            if tid in existing_ids:
                continue

            print(f"[{i+1}/{len(templates)}] {tid} ...", end=" ", flush=True)

            try:
                result = generate_note(client, model, template)
            except Exception as e:
                print(f"ERROR: {e}")
                continue

            note = {
                "id": tid,
                "type": template["type"],
                "category": template["category"],
                "language": template["language"],
                "days_ago": template["days_ago"],
                "text": result["text"],
            }
            notes_f.write(json.dumps(note, ensure_ascii=False) + "\n")

            for query in result.get("search_queries", []):
                eval_entry = {
                    "note_id": tid,
                    "query": query,
                    "target_system": "search",
                    "expected_note_ids": [tid],
                }
                eval_f.write(json.dumps(eval_entry, ensure_ascii=False) + "\n")

            ask_hints = template.get("query_hints_ask", [])
            for hint, query in zip(ask_hints, result.get("ask_queries", [])):
                eval_entry = {
                    "note_id": tid,
                    "query": query,
                    "target_system": "ask",
                    "intent": hint["intent"],
                    "expected_time_filter": hint.get("expected_time_filter"),
                    "expected_category_filter": hint.get("expected_category_filter"),
                    "expected_note_ids": hint.get("expected_note_ids", [tid]),
                }
                eval_f.write(json.dumps(eval_entry, ensure_ascii=False) + "\n")

            print("done")

    total = sum(1 for _ in open(NOTES_FILE))
    print(f"\nDone. {total} notes in notes2.jsonl")


if __name__ == "__main__":
    main()
