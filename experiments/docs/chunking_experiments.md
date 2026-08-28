# Chunking Experiments: Findings & Next Steps

> **Exploratory — not acted on in v2.** No strategy from this doc is wired into the
> app or the retrieval eval; notes are still indexed whole. This is a visual
> comparison to understand how the methods differ, kept for future reference.
>
> Runs on **real personal notes**, so the input file and result reports are
> gitignored and absent from this repo. To reproduce, create
> `experiments/data/real/chunking_input.jsonl` — one JSON object per line with
> keys `id`, `type`, `category`, `text` — from your own notes.

## Overview

Standalone comparison, not wired into `runner.py`/the retrieval eval — judged visually, not scored. 10 longest real notes from the production DB (`experiments/data/real/chunking_input.jsonl`, gitignored, hand-editable), 4 chunking methods, embedding variant where applicable (MiniLM local vs. OpenAI `text-embedding-3-small`).

Code: `experiments/pipeline/chunk.py` (4 methods), `experiments/pipeline/embed.py` (embedding backends + cost tracking), `experiments/pipeline/repunctuate.py`, `experiments/chunking_experiment.py` (runner).

Reports: `experiments/artifacts/results/chunking/*.md` (gitignored — real note content).

**The 4 methods:**
- `breakpoint` — embed sentences in isolation, split where similarity to the next sentence drops past a percentile threshold. The "classic" semantic chunker.
- `clustering` — embed sentences, grow a running chunk while each new sentence stays similar to the chunk's running centroid.
- `llm_boundary` — ask an LLM to mark topic shifts directly (`|||` markers), no embeddings.
- `late` — embed the whole note first (token-level, pre-pooling), then pool per sentence and apply the same breakpoint rule as `breakpoint`. **MiniLM only** — hosted embedding APIs (OpenAI included) never expose token-level embeddings, only the final pooled vector, so this method has no OpenAI equivalent to compare against.

Total cost across all runs so far (10 notes × 6 method/provider combos, plus repunctuation pass): well under $0.01.

---

## Findings

### 1. Punctuation is a required preprocessing step, not something any chunking method compensates for

First pass on raw transcripts: all 4 methods barely disagreed — looked like a non-finding. Root cause wasn't the methods, it was the input: several notes had almost no internal punctuation (1 detected sentence in a 1353-char note, 2 in 1650 chars) — long unbroken clauses from rambly voice dictation. Every method here splits on sentence boundaries first; with ~1 sentence there's nothing to chunk regardless of algorithm.

Confirmed by re-running after an LLM repunctuation pass (`repunctuate.py`, verbatim wording + added punctuation/paragraphs, gpt-4o-mini, $0.00314 for all 10 notes): sentence counts rose 2–20x on the affected notes (1→18, 2→19, 3→42), chunk counts scaled accordingly. Two notes that already had decent punctuation barely changed (20→20, 11→9) — it's not "voice notes are always bad," it's per-note variance in how continuously each note was spoken. Both of those two were themselves voice notes, so it isn't a voice-vs-typed split either.

Caveat: the repunctuation prompt did some light grammar cleanup beyond pure punctuation (spot-checked: "try" → "tried", dropped filler words like "like") despite being told not to — accepted as fine for visual judgment, would need a stricter prompt if this became a rigorous A/B.

### 2. Repunctuation produces paragraph breaks as a side effect — an unused, near-free coarse chunking signal

The repunctuation prompt asks for paragraph breaks along with punctuation. Confirmed: 10 `\n\n` breaks inserted in the first note alone. But `split_sentences()` treats `\n\n` as an ordinary whitespace-before-sentence boundary — no different from a mid-paragraph period. The LLM's own topic-segmentation judgment is computed and then discarded by every downstream chunker.

Untested hypothesis: paragraph breaks might approximate `llm_boundary`'s explicit topic-shift markers almost for free (no second LLM call needed). Worth a direct comparison — see Next Steps.

### 3. `late` vs `breakpoint` diverge on the same note despite sharing the exact same boundary-merge code

Same note, same threshold logic — `breakpoint` (isolated sentence embeddings) gave a 35/454/4059-char split; `late` (whole-note-context embeddings) gave 35/982/3531. The only difference is what the sentence embeddings "saw" while being computed. Direct, visible evidence that context-aware embedding changes where boundaries land, not just how well they're detected.

### 4. `clustering`'s default similarity threshold (0.5, since loosened to 0.4) over-fragmented

On the first note it produced 10 chunks (near sentence-level) vs. 3 for `breakpoint`/`late` on the same text — too aggressive a cutoff for this note style. Threshold sensitivity not yet systematically explored (see Next Steps).

---

## Next steps / ideas to try further

- [ ] Compare paragraph-break positions (from repunctuation) against `llm_boundary`'s `|||` marker positions on the same notes — if they mostly agree, paragraph-aware splitting could replace a dedicated LLM boundary call
- [ ] Tighten the repunctuation prompt to be strictly verbatim (no grammar fixes) if this ever needs to be a rigorous comparison rather than visual judgment
- [ ] Sweep `clustering`'s similarity threshold and `breakpoint`/`late`'s percentile across a few values — current defaults were picked once, not tuned
- [ ] Category-aware chunking: task/reference/journal notes are structurally different (enumerable items vs. discrete facts vs. temporal narrative) — a strategy tuned per category might beat any single method winning universally. Category taxonomy already exists (`config.py`), no new data needed
- [ ] Multi-granularity / query-adaptive retrieval: chunk for precise matching, but return the parent note (or a larger window) as generation context — "small-to-big" retrieval. Connects to the existing `plan.intent` branch in `src/rag/retrieval.py` (browse vs. semantic) — extending intent-routing to also pick granularity, not just source
- [ ] RAPTOR (recursive cluster + summarize into a tree) as the "proper" answer to multi-granularity — heavier to build, worth reading the mechanics before attempting
- [ ] Whisper model size — currently `base` ([src/processing.py](../../src/processing.py)); larger models may reduce how often notes arrive punctuation-starved in the first place. Cheap to test locally, no API cost. Queued in `plan.md` "Next Block"
- [ ] `ANTHROPIC_API_KEY` not set in this dev environment — `llm_boundary/anthropic` was skipped for the full run; only the OpenAI variant has been tested
