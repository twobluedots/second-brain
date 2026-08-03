# Plan — current: v2 (Topics & Compound Knowledge)

> **This is `plan.md` — the current operating doc (build track).** Everything about the version I'm building now lives here: focus, this week, check-ins, rules, parking lot.
> v1 (MVP) is archived in [plan-v1.md](plan-v1.md). Direction across all versions: [roadmap.md](roadmap.md). Eval/learning track: [learning.md](learning.md) + [docs/learning/](learning/).
> When v2 ships, snapshot this file to `plan-v2.md` and roll `plan.md` into v3 — **the current version is always `plan.md`.**

---

## Current Focus

**v2 thesis — "Do the notes I save compound over time into a valuable knowledge base on a topic, or just pile up?"**

**Done when:** I've used tags on 2–3 real topics long enough to *judge* — does a topic collection become genuinely valuable, or does it rot? This is **evidence, not a feature**: it needs weeks of real usage, so the build is fast but the answer is time-gated.

**Design status:** the v2 *experience* is deferred to its own design session — the open question is cards vs. a built-up resource: process existing notes into a single whole-page story you update, or extract statements into a knowledge base of learnable bits. This chunk is not that. This chunk = **build the data engine (tag capture) + start the usage clock** so the material to answer the thesis starts accumulating now.

---
## This Week (Mon 2026-08-04 → Fri 2026-08-08)

**Week goal:** By Friday — the eval pipeline has produced its first retrieval and
generation numbers with a written weaknesses list, and the repo is ready to open-source.

Day shape: **AM = eval, PM = build.**

### AM — eval track (in order)
- [ ] RAGAS pipeline, part 1 — wire up context/retrieval metrics, run on the question set
- [ ] Evaluate retrieval — read first scores, write down where retrieval is weak
- [ ] RAGAS pipeline, part 2 — generation metrics (faithfulness, answer-relevancy)
- [ ] Evaluate generation — read scores, write down where generation is weak
- [ ] Chunking strategies — experiment (also feeds v2 multi-topic)
- [ ] Further RAG-component experiments as time allows
  - **Deliverable = a findings list:** concrete weaknesses ("retrieval misses X",
    "generation drifts on Y"). Honest findings over exhaustive tuning.

### PM — build track
- [ ] **Bug-fix day** — Tailscale voice capture, timeboxed (~1–2 hr). If it fights past
  the box, that's the signal that an always-on deployment is the real fix — schedule it
  next week rather than patching further. (App was unreachable over the weekend; the
  current setup depends on my machine being awake.)
- [ ] **Pre-release pass — docs + config** — review tracked docs and README for anything
  not meant to ship; tidy structure (merge the duplicate M1.1a storage docs)
- [ ] **Safe config defaults** — restore XSRF/CORS protection in `.streamlit/config.toml`
  (or document the override)
- [ ] **Better tests** — add coverage for the RAG pipeline (currently thin)
- [ ] **Flex** — implement any fix the eval surfaces

### Background
- [ ] Daily tagged capture continues — the usage clock for the v2 thesis

### Success check
Must-hits: **eval numbers + findings list · repo release-ready.**
**Friday gut-check:** *Is the repo ready to open-source, and can I name what my retrieval
and generation are each weak at?*

**Not this week:** full deployment (unless bug-fix day escalates it) · v2 experience
design · parking lot items.

---

## Weekly Check-in Log

Template — every Sunday (newest entry on top; paste the finished week's task list under its check-in before clearing "This Week" above):

1. Which tasks did I complete this week?
2. Which am I carrying over? Why?
3. On track for the Current Focus? If not, what do I cut?
4. What did I spend time on that WASN'T on the plan?
5. Energy/motivation level (1–5)?
6. One thing I'm proud of this week:

### Week of 2026-07-27 — pending (fill Sunday 2026-08-02)

<!-- First check-in of v2. Verbal mid-week review already done 2026-07-27: v1 closeout basically complete (README, CI, bugs, ask-log); UI refactor + Tailscale carried; doc restructure + v2 thesis locked this session. -->

### Archived task list — v2 week 1 (Mon 2026-07-27 → Fri 2026-07-31)

Day shape: **AM = app, PM = eval/learning.**

**Week goal:** By Friday, the machine that feeds the v2 bet is running — I'm capturing tagged notes from my phone daily, the docs are reorganized, and the eval pipeline gave me its first real numbers.

#### AM — app track (in order)
- [x] **Today — Tailscale** (~30 min) — get phone capture working. Starts the usage clock (feeds both v3 time-data and the v2 compound bet). Timebox: if it fights past ~1 hr, log it in bugs.md and move on.
- [x] **Doc migration** — freeze plan.md, stand up this file, decisions.md entry. *(in progress)*
- [x] **Tags — minimal capture** — tag field on the Entry model + SQLite + ~~ChromaDB metadata~~ (deferred — own `tags` table instead, see spec non-goals); free-text multi-tag input on the capture form (all three dialogs) + editable on existing notes; tags shown on note cards. **Rough UI is fine** — the point is data starts accumulating. Goes *before* the refactor so the clock starts early.
  - Spec (15-min ratify before building): free-text user-defined · multi-tag per note · manual only (no LLM suggest yet) · stored SQLite + ~~Chroma metadata~~ (deferred) · **no backfill** of old notes (batch script later, once real topics are known).
  - Built: [`design/tags-minimal-capture.md`](design/tags-minimal-capture.md). Deltas from spec logged in `decisions.md` (2026-07-29).
- [x] **UI refactor** — the scoped bundle: multipage, `src/ui/components.py`, card de-dup, services factory, `date_preset`→service, `lru_cache` categorize, `whisper_ms`. Absorbs the rough tag UI into clean components. *(soft — carrying it to next week is fine.)*
  - Spec: [`design/ui-refactor.md`](design/ui-refactor.md) — decisions already made (prior scoping session), written up + sequenced into 3 build groups.

#### PM — eval track (all week)
- [ ] (Carried over) **RAGAS self-study → `eval_ask.py` running** — read the docs *myself* (TestsetGenerator + the three metrics already in the file: faithfulness, answer_relevancy, ContextPrecisionWithoutReference), get it running on the 5 questions, read the first scores, and **write down where the pipeline is weak**. That findings list is the deliverable.

#### Background / parallel
- [x] **Daily capture *with tags*** once Tailscale's green — 2–3 notes/day on a couple of real topics. The new normal, not a task. This is me starting to *feed* the v2 bet.
- [x] (Short discussion session) **Reading (light):** topic / taxonomy / in-context learning — keep it as *reading*; it feeds next week's v2 design session, don't let it turn into building.

#### Success check
Binary must-hits: **#1 Tailscale live · #3 tags storing · eval numbers + findings list.** Soft: UI refactor. The real signal (the only time-gated thing): **tagged capture from the phone on ~4+ days.**

**Friday gut-check:** *Did I capture tagged notes from my phone most days this week?* If yes, the week succeeded regardless of what else moved.
 Notes: (1) Tailscale audio bug broke phone voice capture, fix tracked in bugs.md. (2) Most notes came from laptop; phone stays away during focus blocks by design.

**Explicitly NOT this week:** v2 tags *experience* / topic pages, LLM tag-suggest, chunking / extract-statements, tag backfill — all wait on the v2 design session.

### Archived task list — v1 final week (Mon 2026-07-13 → Fri 2026-07-17) — close v1

Day shape: AM block = app, PM block = eval/learning (see [workflow.md](workflow.md)).

- [x] **Tue AM (app)** — ask_log: confirm open decisions in [design/M4.2b-ask-log.md](design/M4.2b-ask-log.md) → write round-trip test myself → implement → Ask page shakedown with logging live (8–10 real questions, one per intent, incl. voice; failures → bugs.md)
- [x] **Tue PM (vision)** — vision session → fill [roadmap.md](roadmap.md) (agenda questions inside)
- [x] **Wed AM (app)** — fix search edit-dialog bug (bugs.md) + any urgent shakedown findings *(carried into Thu)*
- [x] **Wed PM (eval)** — learning session: faithfulness / answer-relevance mechanics → wrap artifact
- [x] **Thu (learning+bug)** — Streamlit execution model + full app.py trace; found & fixed search render-inside-button bug; scoped the UI refactor
- [x] **Thu close-out** — green test run → commit ask_log implementation + bug fix; bugs.md OPEN→FIXED; search store-params fix
- [x] **Fri AM (app)** — README rewrite + privacy sweep of tracked docs + decide which experiments/ files get tracked
- [x] **Fri PM (app)** — private GitHub push + clone test + CI workflow (pytest + ruff). Tailscale attempted → **broken, carried to v2 week 1**
- [x] **Sun** — vision session (filled roadmap.md) + weekly check-in
- Slid to v2: UI refactor bundle, tags, generation-eval deepening

---

## Rules for Myself
1. **One hour a day.** Not zero, not five. One.
2. **Follow the plan.** If something isn't on the Current Focus, it goes in the parking lot.
3. **Time-box decisions.** 15 minutes max to decide something technical. Pick and move.
4. **Ugly is fine.** Working > pretty. Always.
5. **When stuck, shrink the task.** If a task feels overwhelming, break it in half and do the first half only.
6. **Check in weekly.** Use the template above. Be honest.
7. **The parking lot is your friend.** Every cool idea goes there. It's not forgotten. It's just not now.
8. **Ship gate before new features.** Finish and commit the current thing before opening the next.

---

## Parking Lot (NOT now, but captured so your brain can let go)

### Categorization / tags / chunking
- [ ] **v2 experience design** — cards vs. built-up resource; whole-page story vs. extract-statements-into-knowledge-base (the deferred v2 design session)
- [ ] Multiple categories per note — single category for now; may become unnecessary once chunking is added
- [ ] Chunking strategy — split long voice memos and journal entries into semantic chunks, label each chunk independently (feeds v2 cards; Dataset 2)
- [ ] Extract statements from notes into learnable bits (the "learnable chunk parts" idea — part of v2 experience design)
- [ ] LLM auto-suggest topic tags — after manual tags are stable and real topics are known
- [ ] Tag backfill of existing notes — batch script (M2.5-style), once real topics emerge from usage
- [ ] Spaced repetition for `learning` notes — flashcard-style recall reminders

### Technical
- [ ] "Today" filters use UTC midnight — should be user-local timezone (Search presets, Journal day range, Mirror week math)
- [ ] Ask-voice audio retention — currently transcribe-and-delete; revisit if ask_log shows garbled queries / re-asks during usage period (evidence-driven, see decisions.md 2026-07-14)
- [ ] Persist `whisper_ms` to `ask_log` table — timing is now captured in `process_voice_note()` return value; small schema addition + migration needed to store it for analysis
- [ ] Migrate to Supabase (PostgreSQL + pgvector — replaces both SQLite and ChromaDB)
- [ ] Deploy to Streamlit Community Cloud
- [ ] Migrate from Streamlit to a more flexible framework
- [ ] Build a proper REST API (FastAPI)
- [ ] Better embedding model (finish comparison from scratch.md — experiments 2b/3/4 in docs/search_experiments.md)
- [ ] Query intent classification — retrieval-type vs QA-type; simple heuristic first (question words → QA mode)
- [ ] Multi-answer eval — extend eval_set.jsonl to `expected_note_ids: [id1, id2]`; update grader.py to score against the set
- [ ] LangGraph for smarter search
- [ ] Graph database for note relationships
- [ ] Local LLM instead of OpenAI API
- [ ] Privacy-preserving embeddings
- [ ] Streaming voice save (fallback if recording fails mid-way)

### Features
- [ ] Pattern discovery ("you always feel stressed on Mondays")
- [ ] Automatic summary generation
- [ ] Import from Obsidian/Notion
- [ ] Calendar integration
- [ ] Fine-tune OCR for your handwriting
- [ ] End-of-day nudge on the capture page: "Had any wins today?" — log achievements at capture time (graduates to v3 prerequisite)
- [ ] Voice synthesis (read notes back to you)
- [ ] "You forgot about this" proactive surfacing
- [ ] Continuity nudges ("you were tracking mood for 4 days, you stopped")
- [ ] PDF and markdown import
- [ ] Multi-user support

### Decisions for Later
- [ ] Whisper API instead of local model ? (how will the performance change)
- [ ] Hosting/deployment strategy (M5 — deployment research thread; candidate designs A/B/C/D in roadmap.md)
- [ ] Cost model (sustainable monthly API spend?)
- [ ] Open source strategy (MIT? contributions?)
- [ ] Framework migration (what and when)

---

## Ideas & Big Picture Thoughts
Dump anything here during the version. No filtering, no organizing. Just date and thought. Review at weekly check-in.

<!-- Example:
- 2026-05-06: What if the app could generate a "weekly letter to yourself" summarizing what you did?
-->
