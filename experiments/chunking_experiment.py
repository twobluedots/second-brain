"""
Compare semantic chunking strategies on real notes — a standalone learning
experiment, not wired into runner.py/the retrieval eval. Judged visually, not
scored: this is about seeing how the 4 methods disagree on real (mostly
voice-transcribed) notes, not measuring recall/MRR.

Input:  experiments/data/real/chunking_input.jsonl (hand-editable — swap in
        different notes any time; see NoteService/Storage for the source DB)
Output: experiments/artifacts/results/chunking/<timestamp>.md

Usage:
  python experiments/chunking_experiment.py            # all notes in the input file
  python experiments/chunking_experiment.py --limit 1   # cheap smoke test before a full run
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from experiments.pipeline.chunk import chunk_breakpoint, chunk_clustering, chunk_late, chunk_llm_boundary
from experiments.pipeline.embed import embed_minilm, embed_openai

ROOT = Path(__file__).parent
INPUT_PATH = ROOT / "data/real/chunking_input.jsonl"
REPORT_DIR = ROOT / "artifacts/results/chunking"

# (label, runner) — runner takes note text, returns a ChunkResult
METHODS = [
    ("breakpoint / minilm", lambda text: chunk_breakpoint(text, embed_minilm)),
    ("breakpoint / openai", lambda text: chunk_breakpoint(text, embed_openai)),
    ("clustering / minilm", lambda text: chunk_clustering(text, embed_minilm)),
    ("clustering / openai", lambda text: chunk_clustering(text, embed_openai)),
    # ("llm_boundary / anthropic", ...) — skipped, no ANTHROPIC_API_KEY set in this environment
    ("llm_boundary / openai", lambda text: chunk_llm_boundary(text, provider="openai")),
    ("late / minilm", lambda text: chunk_late(text)),
]


def load_notes(input_path: Path, limit: int = None) -> list[dict]:
    notes = [json.loads(line) for line in open(input_path) if line.strip()]
    return notes[:limit] if limit else notes


def run(notes: list[dict]) -> tuple[str, float]:
    lines = [f"# Chunking experiment — {datetime.now(timezone.utc).isoformat()}", ""]
    total_cost = 0.0

    for note in notes:
        lines.append(f"## {note['id']}  (type={note['type']}, category={note['category']}, len={len(note['text'])})")
        lines.append("")
        lines.append("**Original:**")
        lines.append(f"> {note['text']}")
        lines.append("")

        for label, runner in METHODS:
            print(f"  {note['id']} :: {label}")
            try:
                result = runner(note["text"])
            except Exception as e:
                lines.append(f"### {label} — FAILED: {e}")
                lines.append("")
                continue

            run_cost = sum(u.cost_usd for u in result.usage)
            total_cost += run_cost

            lines.append(f"### {label}  ({len(result.chunks)} chunks{f', ${run_cost:.5f}' if run_cost else ''})")
            for i, chunk in enumerate(result.chunks, 1):
                lines.append(f"{i}. {chunk}")
            lines.append("")

        lines.append("---")
        lines.append("")

    lines.append(f"**Total cost: ${total_cost:.5f}**")
    return "\n".join(lines), total_cost


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Only process the first N notes (cheap smoke test)")
    parser.add_argument("--input", type=Path, default=INPUT_PATH, help="Path to a chunking-input JSONL file")
    parser.add_argument("--tag", type=str, default="", help="Suffix for the output report filename, e.g. 'punctuated'")
    args = parser.parse_args()

    notes = load_notes(args.input, args.limit)
    print(f"Running {len(METHODS)} methods on {len(notes)} note(s)  [input: {args.input.name}]...\n")

    report, total_cost = run(notes)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = f"_{args.tag}" if args.tag else ""
    out_path = REPORT_DIR / f"{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}{suffix}.md"
    out_path.write_text(report)

    print(f"\nWrote {out_path}")
    print(f"Total cost: ${total_cost:.5f}")


if __name__ == "__main__":
    main()
