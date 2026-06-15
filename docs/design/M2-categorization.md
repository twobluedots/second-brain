# M2 Categorization Design

## Core Design Principle

Categories are defined by **what you DO with the note**, not what it's about.

Topics (health, food, tech, travel) are open-ended and grow forever. They become auto-generated **tags** later. Categories are a small, stable set that never changes.

> "I want to look this up later" → `reference`  
> "I want to remember how I felt" → `mood`  
> Not: "this note is about health" → ~~`health`~~

---

## The 7 Categories

| Category | What you do with it | Examples |
|---|---|---|
| `task` | Act on it | "call the dentist tomorrow", "buy milk" |
| `mood` | Track emotions over time | "I feel drained today", "anxious this morning" |
| `journal` | Daily activity log | Interstitial journal entries, "I did X today" |
| `learning` | Repeat/practice later — flashcard style | "== vs is: identity vs equality", "garlic after onion" |
| `reference` | Look up when a specific situation comes | "pasta 8 min", "ibuprofen max 3x/day", "great coffee shop on X street" |
| `insight` | Get to know yourself — patterns, observations | "I'm always anxious before meetings", "I work better in the morning" |
| `achievement` | Emotionally significant breakthroughs | "I finally understood transformers", "showed up to gym despite not wanting to" |

### Key distinctions

**`learning` vs `reference`**
- `learning` = flashcard knowledge with no specific trigger situation. You want to be able to recall or quiz yourself on it anytime.
- `reference` = only needed when a specific situation comes up. You look it up, use it, close it.
- "== vs is in Python" → `learning` (you want this to stick, quiz yourself)
- "ibuprofen max 3x/day" → `reference` (only matters when you're sick)

**`learning` vs `achievement`**
- `learning` = dry fact or concept, no emotional weight
- `achievement` = emotionally significant breakthrough, the "I finally got it" feeling
- "== vs is in Python" → `learning`
- "I finally understood how attention mechanisms work" → `achievement`

**`mood` vs `insight`**
- `mood` = how you feel right now (present state)
- `insight` = a pattern or observation about yourself (derived understanding)
- "I feel anxious today" → `mood`
- "I'm always anxious before meetings" → `insight`

**`reference` vs `insight`**
- This is the hardest pair — same event, different framing
- "July is not a good month for Turkey — too crowded" → `reference` (fact to use when planning)
- "I didn't enjoy Turkey because everywhere was too crowded" → `insight` (self-knowledge about what ruins your enjoyment)
- **This ambiguity is accepted and intentional.** The AI does best-effort based on phrasing. Editability (M2.3/M2.4) is the fix.

---

## Categorization Implementation

### File: `src/categorize.py`

Single function: `categorize(text: str) -> str`

Returns one category from `DEFAULT_CATEGORIES`. Falls back to `"journal"` on all failures.

### LLM Chain

```
OpenAI (gpt-4o-mini) → Anthropic (claude-haiku-4-5) → Ollama (llama3.2) → "journal"
```

- Uses whichever key is present in `.env`
- OpenAI active now; Ollama ready once model finishes downloading
- Anthropic available once API key is added to `.env`
- All fallbacks are silent — user never sees a failure, note saves regardless

### Prompt Strategy

Categories are described in `config.py::CATEGORY_DESCRIPTIONS` — these drive the LLM's classification. The prompt sends the full descriptions with each request so any tweak to the descriptions immediately affects all future categorizations.

Prompt structure:
```
Categorize this personal note into exactly one category.
Return JSON only: {"category": "<name>"}

Categories:
- task: Something to act on...
- mood: Basic emotion tracking...
[...]

Note: <text>
```

**Why JSON response:** Structured output, no regex parsing needed, model stays focused on the classification task.

### Accuracy

Tested on 12 representative examples: **9/12 correct**.

The 3 misses:
1. "need to go back" in a note → classified as `task` instead of `reference` (phrasing-driven — "need to go back" reads as an action item)
2. "July not good for Turkey" → classified as `insight` instead of `reference` (same-event ambiguity)
3. "didn't enjoy Turkey because crowded" → classified as `mood` instead of `insight` (same-event ambiguity)

All 3 are phrasing/framing edge cases, not systematic failures. The rule: **don't chase 12/12 with prompt engineering — use editability instead.**

### Wiring

Categorization runs silently in `notes_service.save_note()`:
```python
if not category:
    category = categorize(content or "")
entry = Entry(content=content, content_type=content_type, category=category, ...)
self.storage.save(entry)
```

`storage.save()` receives an already-categorized `Entry` — it does no LLM calls. The note saves regardless of whether categorization succeeds (fallback is `"journal"`).

Journal entries pass `category="journal"` explicitly from `app.py` → `notes_service` skips categorization for them.

---

## Feedback Loop (M2.3/M2.4)

Every categorization event is logged in a `category_events` table:

```sql
CREATE TABLE category_events (
    id TEXT PRIMARY KEY,
    entry_id TEXT NOT NULL,
    ai_suggested TEXT,
    final_category TEXT NOT NULL,
    was_overridden INTEGER NOT NULL DEFAULT 0,  -- 1 if user changed it
    created_at TEXT NOT NULL,
    FOREIGN KEY (entry_id) REFERENCES entries(id)
);
```

**Why this matters:** Over time, entries where `was_overridden = 1` show which categories the AI gets wrong most often. That's the data that tells you when to tweak the prompt descriptions — not gut feeling, but actual override patterns.

**When to act on feedback:** After ~50-100 notes, check override rate per category. If one category is wrong >30% of the time, revise its description.

---

## Deferred Decisions

### Multiple categories per note
Currently single category. The DB stores it as a `TEXT` column — migration needed if moved to a list.

**Why deferred:** May become unnecessary once chunking is added. A long note that spans `mood + learning` is better served by splitting into two chunks, each with one clean label.

### Chunking strategy
Long voice memos and journal entries naturally span multiple intents. Chunking = split at semantic boundaries, label each chunk independently.

**When it's worth it:** Voice memos (free-flowing, multi-topic), long journal entries, imported text.  
**When it's not:** Single-sentence captures (most text notes).  
**Suggested sequence:** Single category now (M2) → chunking for voice/long notes (M3+).

### Auto-generated topic tags
Topics (health, food, work, travel) become auto-generated tags via the same LLM pipeline. Separate from intent categories.

**Why deferred:** Categories need to be stable and validated before adding a second classification layer.

### Spaced repetition for `learning` notes
`learning` category is flashcard-style by design — natural fit for a "practice this later" reminder. Build after M3.

---

## Open Questions (not yet decided)

- **Model conclusion:** Tested all three models on the same 12 examples (`experiments/categorization_model_comparison_2026-05-21.txt`) Initial results on 12 examples: OpenAI 9/12, llama3.2 8/12, mistral 7/12. Not final — retest after prompts and categories are further developed. OpenAI gpt-4o-mini is primary. llama3.2 is the best free fallback. Mistral available but not recommended for this task.
- **Turkish language handling:** Categorization prompt is English-only. Does the model correctly classify Turkish notes? Needs testing.
- **Cost:** gpt-4o-mini is ~$0.00015 per note. At 10 notes/day = ~$0.05/month. Negligible, but worth confirming once usage is real.
