"""
Generate synthetic notes + eval queries from templates.yaml.

Outputs:
  notes.jsonl     — one note per line: {id, type, category, language, text}
  eval_set.jsonl  — one query pair per line: {note_id, query, expected_note_id}

Resume-safe: skips notes whose id already appears in notes.jsonl.
"""

import json
import os
import yaml
from pathlib import Path
from openai import OpenAI

DIR = Path(__file__).parent
TEMPLATES_FILE = DIR / "templates.yaml"
NOTES_FILE = DIR / "notes.jsonl"
EVAL_FILE = DIR / "eval_set.jsonl"

SYSTEM_PROMPT = """You generate realistic personal notes for a second-brain app used by someone with ADHD.

The person is a developer in their late 20s-early 30s, bilingual (English + Turkish), building a personal knowledge app.
Their notes are raw and personal — fragments, run-on sentences, self-interruptions, no polish.

Voice notes sound like talking to yourself mid-thought. Text notes are direct, sometimes just fragments.
Both feel like they were captured in 30 seconds to avoid losing the thought.

Return ONLY valid JSON in this exact shape:
{
  "text": "<the note text>",
  "queries": ["<natural search query 1>", "<natural search query 2>"]
}

The queries should be how someone would actually search for this note months later —
natural language, short, specific to what's in the note."""


def build_prompt(template: dict) -> str:
    lines = [
        f"Generate a {template['type']} note in {template['language']}.",
        f"Category: {template['category']}",
        f"Target length: {template['word_range'][0]}–{template['word_range'][1]} words",
        "",
        f"Scenario: {template['scenario'].strip()}",
        "",
        f"Style: {template['style_notes'].strip()}",
        "",
        "Query hints (use these as inspiration, rephrase naturally):",
    ]
    for hint in template.get("query_hints", []):
        lines.append(f"  - {hint}")
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


def generate_note(client: OpenAI, template: dict) -> dict:
    response = client.chat.completions.create(
        model=os.getenv("OLLAMA_MODEL", "llama3.2") if os.getenv("USE_OLLAMA", "false").lower() == "true" else "gpt-4o-mini",
        temperature=0.9,
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

    # Switch to ollama=True to use local Llama instead of OpenAI
    use_ollama = os.getenv("USE_OLLAMA", "false").lower() == "true"
    if use_ollama:
        client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
    else:
        client = OpenAI(api_key=api_key)

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
                result = generate_note(client, template)
            except Exception as e:
                print(f"ERROR: {e}")
                continue

            note = {
                "id": tid,
                "type": template["type"],
                "category": template["category"],
                "language": template["language"],
                "text": result["text"],
            }
            notes_f.write(json.dumps(note, ensure_ascii=False) + "\n")

            for query in result.get("queries", []):
                eval_entry = {
                    "note_id": tid,
                    "query": query,
                    "expected_note_id": tid,
                }
                eval_f.write(json.dumps(eval_entry, ensure_ascii=False) + "\n")

            print("done")

    total = sum(1 for _ in open(NOTES_FILE))
    print(f"\nDone. {total} notes in notes.jsonl")


if __name__ == "__main__":
    main()
