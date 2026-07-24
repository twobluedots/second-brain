"""
Analyzes real notes to inform synthetic dataset generation for RAG experiments.
Outputs a report covering: length distributions, category patterns, topic indicators,
topic shift signals, and language style — the things that matter for mimicking real notes.

Run: python experiments/analyze_notes.py
"""

import sqlite3
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

DB_PATH = Path("data/database/entries.db")

TOPIC_KEYWORDS = {
    "project/coding": ["app", "bug", "code", "feature", "build", "streamlit", "database", "api", "error", "fix", "deploy", "test"],
    "mood/feelings": ["feel", "feeling", "felt", "tired", "anxious", "happy", "sad", "overwhelmed", "excited", "frustrated", "bad day", "good day"],
    "productivity/adhd": ["focus", "distracted", "motivation", "procrastinat", "stuck", "momentum", "friction", "habit", "routine", "task"],
    "learning": ["learned", "realized", "understand", "reading", "book", "concept", "interesting", "discovery"],
    "relationships": ["husband", "friend", "talked", "conversation", "together"],
    "practical/reference": ["buy", "remember", "drawer", "put", "find", "need to", "don't forget"],
    "self_reflection": ["think", "realize", "notice", "pattern", "insight", "remind", "wonder"],
    "future_plans": ["will", "going to", "plan", "next week", "next month", "want to", "goal"],
}

TOPIC_SHIFT_SIGNALS = [
    r"\balso\b", r"\band (also|another|one more)\b", r"\boh (and|also|by the way)\b",
    r"\bby the way\b", r"\banyway\b", r"\bon another note\b", r"\bspeaking of\b",
    r"\bone more thing\b", r"\bseparately\b", r"\bunrelated\b",
]


def load_entries(db_path: Path) -> list[dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, content, content_type, category, LENGTH(content) as char_len, created_at "
        "FROM entries WHERE deleted_at IS NULL AND content IS NOT NULL AND LENGTH(content) > 5"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def word_count(text: str) -> int:
    return len(text.split())


def sentence_count(text: str) -> int:
    return max(1, len(re.split(r'[.!?]+', text.strip())))


def detect_topic_shifts(text: str) -> list[str]:
    found = []
    for pattern in TOPIC_SHIFT_SIGNALS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        found.extend(matches)
    return found


def score_topics(text: str) -> dict[str, int]:
    text_lower = text.lower()
    scores = {}
    for topic, keywords in TOPIC_KEYWORDS.items():
        count = sum(text_lower.count(kw) for kw in keywords)
        if count > 0:
            scores[topic] = count
    return dict(sorted(scores.items(), key=lambda x: -x[1]))


def analyze(entries: list[dict]) -> dict:
    by_type = defaultdict(list)
    for e in entries:
        by_type[e["content_type"]].append(e)

    report = {}

    for ctype, items in by_type.items():
        lengths_chars = [e["char_len"] for e in items]
        lengths_words = [word_count(e["content"]) for e in items]

        category_dist = Counter(e["category"] for e in items)

        # Topic shift analysis
        shift_counts = [len(detect_topic_shifts(e["content"])) for e in items]
        multi_topic = [e for e, s in zip(items, shift_counts) if s >= 2]

        # Topic keyword analysis
        all_topic_scores = defaultdict(int)
        for e in items:
            for topic, count in score_topics(e["content"]).items():
                all_topic_scores[topic] += count

        # Long notes breakdown
        long_notes = sorted(items, key=lambda x: -x["char_len"])[:5]
        long_note_details = []
        for n in long_notes:
            shifts = detect_topic_shifts(n["content"])
            topics = score_topics(n["content"])
            long_note_details.append({
                "chars": n["char_len"],
                "words": word_count(n["content"]),
                "sentences": sentence_count(n["content"]),
                "category": n["category"],
                "topic_shift_signals": shifts,
                "top_topics": list(topics.keys())[:3],
                "preview": n["content"][:120] + "...",
            })

        report[ctype] = {
            "total": len(items),
            "length_chars": {
                "min": min(lengths_chars),
                "max": max(lengths_chars),
                "avg": round(sum(lengths_chars) / len(lengths_chars)),
                "median": sorted(lengths_chars)[len(lengths_chars) // 2],
                "buckets": {
                    "under_100": sum(1 for n in lengths_chars if n < 100),
                    "100_300": sum(1 for n in lengths_chars if 100 <= n < 300),
                    "300_600": sum(1 for n in lengths_chars if 300 <= n < 600),
                    "600_plus": sum(1 for n in lengths_chars if n >= 600),
                },
            },
            "length_words": {
                "min": min(lengths_words),
                "max": max(lengths_words),
                "avg": round(sum(lengths_words) / len(lengths_words)),
            },
            "category_distribution": dict(category_dist.most_common()),
            "topic_distribution": dict(sorted(all_topic_scores.items(), key=lambda x: -x[1])),
            "topic_shift_analysis": {
                "notes_with_0_shifts": sum(1 for s in shift_counts if s == 0),
                "notes_with_1_shift": sum(1 for s in shift_counts if s == 1),
                "notes_with_2plus_shifts": sum(1 for s in shift_counts if s >= 2),
                "multi_topic_examples": [
                    {
                        "chars": e["char_len"],
                        "shifts": detect_topic_shifts(e["content"]),
                        "preview": e["content"][:100] + "...",
                    }
                    for e in multi_topic[:3]
                ],
            },
            "longest_notes": long_note_details,
        }

    return report


def print_report(report: dict):
    print("\n" + "=" * 60)
    print("NOTE ANALYSIS REPORT — for synthetic dataset design")
    print("=" * 60)

    for ctype, data in report.items():
        print(f"\n{'─' * 40}")
        print(f"  TYPE: {ctype.upper()}  ({data['total']} notes)")
        print(f"{'─' * 40}")

        lc = data["length_chars"]
        lw = data["length_words"]
        print(f"\nLength (chars):  min={lc['min']}  avg={lc['avg']}  median={lc['median']}  max={lc['max']}")
        print(f"Length (words):  min={lw['min']}  avg={lw['avg']}  max={lw['max']}")

        b = lc["buckets"]
        print("\nLength buckets:")
        print(f"  <100 chars:   {b['under_100']:2d} notes  {'█' * b['under_100']}")
        print(f"  100-300:      {b['100_300']:2d} notes  {'█' * b['100_300']}")
        print(f"  300-600:      {b['300_600']:2d} notes  {'█' * b['300_600']}")
        print(f"  600+:         {b['600_plus']:2d} notes  {'█' * b['600_plus']}")

        print("\nCategory distribution:")
        for cat, count in data["category_distribution"].items():
            print(f"  {cat or 'none':<15} {count:2d}  {'█' * count}")

        print("\nTopic presence (keyword hits across all notes):")
        for topic, score in list(data["topic_distribution"].items())[:6]:
            print(f"  {topic:<25} {score:3d}")

        ts = data["topic_shift_analysis"]
        print("\nTopic shift signals:")
        print(f"  0 shifts:  {ts['notes_with_0_shifts']} notes")
        print(f"  1 shift:   {ts['notes_with_1_shift']} notes")
        print(f"  2+ shifts: {ts['notes_with_2plus_shifts']} notes")

        if ts["multi_topic_examples"]:
            print("\n  Multi-topic examples:")
            for ex in ts["multi_topic_examples"]:
                print(f"    [{ex['chars']} chars] shifts={ex['shifts']}")
                print(f"    \"{ex['preview']}\"")

        print("\nLongest notes:")
        for n in data["longest_notes"]:
            print(f"  [{n['chars']}c / {n['words']}w / {n['sentences']}s] cat={n['category']} topics={n['top_topics']}")
            if n["topic_shift_signals"]:
                print(f"    shifts: {n['topic_shift_signals']}")
            print(f"    \"{n['preview']}\"")


def save_report(report: dict):
    out = Path("experiments/data/note_analysis.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nFull report saved to {out}")


if __name__ == "__main__":
    entries = load_entries(DB_PATH)
    print(f"Loaded {len(entries)} entries from {DB_PATH}")
    report = analyze(entries)
    print_report(report)
    save_report(report)
    print("\nUse this analysis to guide synthetic note generation:")
    print("  - match length distributions per type")
    print("  - replicate topic mix and category ratios")
    print("  - model multi-topic notes after the 2+ shift examples")
