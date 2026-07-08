# Search Experiments: Findings & Next Steps

## Overview

Two experiments on dataset1 — 36 notes, 158 eval queries.

| Run | Model | Rank@1 | Not Found | Avg Precision |
|---|---|---|---|---|
| 60052450 | all-MiniLM-L6-v2 (default) | 61% (96) | 15% (24) | 0.698 |
| 41be62cc | bge-large-en-v1.5 | 72% (113) | 11% (18) | 0.783 |

bge-large improved 35 queries, regressed on 15. Net: +20 queries, precision +0.085.

---

## Failure Categories

### 1. Dataset Quality Issues

These are problems in the eval set itself, not the model. Fix before any further experiments.

**Wrong topic mapping** — query has no real relationship to the expected note:
- `"devops continuous delivery"` → expected: knowledge graphs note (`v_learning_001`)
- `"what is pipeline orchestration"` → expected: knowledge graphs note (`v_learning_001`)
- The note is about tree-based data retrieval structures, not DevOps. These queries should be removed or replaced.

**Expected note is wrong — retrieved note is actually better:**
- `"location of laptop at home"` and `"where did I put my charger"` → expected: `t_ref_003` (keys/wallet in kitchen drawer)
- Retrieved `v_ref_001` ("Charger by the big book on the shelf above the fireplace") is the correct answer for the charger query.
- `t_ref_003` is about keys and wallet — not a laptop or charger. The expected note should be `v_ref_001`.

**Query vocabulary doesn't match note vocabulary + temporal mismatch:**
- `"when I was anxious about meeting at work friday"` → expected: `v_mood_001` ("anxious bout that call with Alex")
- The note says "call" not "meeting", says "today" not "friday", and doesn't mention work.
- The model correctly retrieves `v_ref_004` ("important meeting at 3pm tomorrow with Alex") — which actually contains "meeting" and "Alex". Not a model failure; the query is misleading and requires date metadata to resolve "friday".

**Debatable mappings** (model isn't wrong to miss these):
- `"pointless job"`, `"feeling underused at work"` → expected: `t_journal_003` ("spinning wheels, project doesn't feel right"). The connection exists but is indirect. Reasonable to miss.

---

### 2. Ambiguous Queries — Multiple Valid Answers

The eval framework assumes one correct note per query. These queries have at least two valid answers in the dataset. Every miss here is partly an eval design flaw, not a model failure.

| Query | Expected | Also valid |
|---|---|---|
| `small win I want to remember` | t_journal_008 | v_journal_003 |
| `why am I building this tool for myself` | t_insight_003 | v_insight_006 |
| `good conversation` | t_journal_008 | t_journal_004 |
| `low energy day` | v_mood_002 | t_mood_001 |
| `task I was avoiding` | t_journal_008 | t_journal_005 |
| `struggle with project alignment` | t_journal_003 | t_journal_007 |
| `reality gap in personal progress` | t_journal_007 | t_journal_003 |

**Fix:** Add `"ambiguous": true` to these entries in eval_set.jsonl and score them with relaxed grading — any top-3 hit passes.

---

### 3. Temporal & Metadata Queries — Feature Gap, Not Model Gap

No embedding model will solve these. They fail because they reference time, date, or note type — none of which are in the semantic embedding.

| Query | What's missing |
|---|---|
| `how I feel at the end of today` | date filter (today) |
| `how did I feel at the end of [today's date]` | date filter |
| `day reflection voice note` | content_type filter (voice) |
| `mid-day check-in` | time-of-day metadata |
| `intention for tomorrow` | date filter (relative: tomorrow) |
| `what I did and didn't do this week` | date range filter (this week) |

These are valid real-world queries. They need metadata-aware search (filter by date/type before or after vector search), not a better embedding model.

---

### 4. Retrieval vs Generation — Wrong Tool for the Job

Some queries aren't "find me a note" requests — they're questions that need an answer synthesized from multiple notes. Pure retrieval will always underperform on these.

- `"How do I learn best?"` → should synthesize from v_insight_004, v_insight_003, v_learning_002
- `"why no motivation?"` → should aggregate mood/insight notes and surface a pattern
- `"lesson learned about organization"` → expects an extracted insight; the note just contains "I need to be more organized" buried at the end of a vent

The "lesson learned" case also shows **embedding dilution**: v_journal_002 is a long multi-topic note (bad meeting, slow coding, time management realization). Its embedding is spread across all those topics, so the "organization lesson" signal is too weak to win over v_insight_002 (which is entirely about organizational clutter). The expected result is buried in a note that's only partly about that topic.

These queries need intent detection: is the user retrieving a specific note, or asking a question to be answered from their notes?

---

### 5. Unrealistic Queries

`"Lunch packing for tomorrow"` — not how a user would actually search. You'd look at recent notes or search "what do I need to prepare for tomorrow."

**Key insight:** We don't know what queries real users actually use. The eval dataset was written by predicting queries, not observing them. Logging real queries from day-1 use would give us ground truth to evaluate against and would catch patterns like this.

---

## Model Comparison Summary

**bge-large clearly better at:**
- Emotional/mood queries: `"feeling behind others"` ✗→#1, `"compare trap in work life"` #3→#1
- Journal/venting: `"venting note from mid-day"` ✗→#1, `"feeling frustrated at work"` ✗→#1
- Social comparison: `"compared to others in my field"` #2→#1
- Root cause: better handling of polarity and emotional directionality

**bge-large regresses on:**
- Abstract/metaphorical: `"project mirrors personal life"` #1→#4, `"why am I building this tool for myself"` #2→✗
- Multi-theme conceptual: `"lesson learned about organization"` #1→#4, `"reality gap in personal progress"` #1→✗
- Root cause: bge-large over-indexes on literal semantic match; loses on indirect conceptual connections

**Both models fail on:**
- Temporal queries (need metadata)
- Bad dataset entries (not a model problem)
- Ambiguous queries (need better eval design)
- Retrieval-vs-generation queries (need RAG, not better retrieval)

---

## Next Experiment Steps

**Step 1 — Clean the dataset** (do before any further model comparison)
- Remove or fix the 3 confirmed wrong mappings (devops/pipeline queries, charger query)
- Add `"ambiguous": true` to the 7 identified ambiguous queries
- Update grader.py to use relaxed scoring for ambiguous entries (top-3 hit = pass)
- Estimated impact: 5-8 queries move from "failure" to "pass" — makes all future comparisons more honest

**Step 2 — bge-large with query_instruction prefix**
- One-line change in config.py: add `query_instruction="Represent this sentence for searching relevant passages: "`
- Re-run against the cleaned dataset
- Expected: 2-5% precision gain; also tells us if the prefix matters for this dataset

**Step 3 — Cross-encoder reranking**
- Add `cross-encoder/ms-marco-MiniLM-L-6-v2` as a reranker on top of bge-large
- Retrieve top 20 with bi-encoder, rerank, return top 5
- Target: the remaining polarity/opposition failures and the abstract query regressions
- Estimated impact: biggest structural improvement available without changing the dataset

**Step 4 — Metadata pre-filter experiment**
- Add category and content_type as ChromaDB where-clause filters
- Test: does filtering to `mood` + `journal` notes before search improve precision for emotional queries?
- This is also production groundwork for the metadata-aware search feature in the app

---

## Product Feature Implications

| Finding | Feature | Priority |
|---|---|---|
| Temporal queries always fail | Date range filter on search | High — common real query type |
| "voice note" filter queries | Filter by input type (voice/text/image) | Medium |
| Unrealistic eval queries | Log all real search queries to SQLite | High — needed for honest future eval |
| Retrieve vs generate distinction | Intent detection: show notes vs answer question | Medium — architectural |
| Long notes dilute key signals | Chunking: index sentence/paragraph segments separately | Low — parking lot |
