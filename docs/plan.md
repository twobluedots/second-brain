# Second Brain MVP Plan

## Vision
**An app that catches everything I think, organizes it automatically, and shows me what I've been thinking.**

## Core Concept
- **Dump** — zero friction input, no decisions required
- **Mirror** — the app reflects back what you've been doing without you asking
- **Differentiator** — built by an ADHD brain, for ADHD brains. Auto-organizes by default so you don't have to, but you can always override, edit tags/categories, and organize manually when you want to.

## MVP Scope: "Dump and Mirror"
1. Input works reliably (text, voice, image, journal)
2. Data persists properly (survives restart)
3. Auto-categorize on save (LLM picks from predefined list)
4. Organized browsing (by category, by time)
5. Mirror/summary page (weekly overview, streaks, category breakdown)

## Architecture (keep it simple)
```
app.py              — Streamlit UI only, no business logic
notes_service.py    — business logic: categorize, orchestrate, log events
storage.py          — pure data operations (save, retrieve, search)
categorize.py       — LLM auto-tagging logic
```
No API framework. No frontend framework. Just Python files.

---

## Current State (Inventory — May 2026)

### What Works
- Streamlit app: Capture, Search, Recent, Journal pages
- Text, voice, image input functional
- Data saves as JSON files locally
- ChromaDB semantic search (in-memory, not persistent)
- Mobile access via ngrok + caffeinate
- GPT-4V tested for OCR (decided)
- Whisper tested for voice transcription

### What's Half-Built
- SQLite storage class (two competing versions started)
- Persistent ChromaDB (not wired up)
- Unified Storage class design
- Embedding model research (done but not decided)

### What's Broken/Fragile (to fix in M1)
- Voice recording may have recent errors → M1.4
- Search re-indexes all JSON files on every page load → fixed by M1.1 (persistent ChromaDB)
- ChromaDB data disappears on restart → fixed by M1.1 (persistent ChromaDB)
- All logic lives in one Streamlit file → M1.3

---

## This Week (Mon 2026-07-13 → Fri 2026-07-17) — close v1

Day shape: AM block = app, PM block = eval/learning (see [workflow.md](workflow.md)). Long-term vision lives in [roadmap.md](roadmap.md).

- [ ] **Tue AM (app)** — ask_log: confirm open decisions in [design/M4.2b-ask-log.md](design/M4.2b-ask-log.md) → write round-trip test myself → implement → Ask page shakedown with logging live (8–10 real questions, one per intent, incl. voice; failures → bugs.md)
- [ ] **Tue PM (vision)** — vision session → fill [roadmap.md](roadmap.md) (agenda questions inside)
- [ ] **Wed AM (app)** — fix search edit-dialog bug (bugs.md) + any urgent shakedown findings
- [ ] **Wed PM (eval)** — learning session: faithfulness / answer-relevance mechanics → wrap artifact
- [x] **Thu (learning+bug, unplanned but right)** — Streamlit execution model + full app.py trace; found & fixed search render-inside-button bug; discovered search_result cache-invalidation follow-up; scoped the UI refactor
- [ ] **Thu close-out** — green test run → commit ask_log implementation + bug fix; bugs.md OPEN→FIXED; search store-params fix (Claude implements, review Fri warm-up)
- [ ] **Fri AM (app)** — README rewrite + privacy sweep of tracked docs + decide which experiments/ files get tracked
- [ ] **Fri PM (app)** — private GitHub push + clone test + CI workflow (pytest + ruff; needs test-config with small embedding model). If time: Tailscale setup (~30 min)
- [ ] **Sun** — **vision session first** (fill roadmap.md — it feeds the check-in), then weekly check-in: cut week 2 = UI refactor (first build blocks) + generation-eval design/grader (eval blocks) + M5 deployment design + usage period starts
- [ ] **Slides to week 2** — UI refactor bundle (multipage, src/ui/components.py, card de-dup, services factory, date_preset→service, lru_cache categorize, whisper_ms), generation grader prototype
- [ ] **Sun** — weekly check-in (template below): cut week 2 from roadmap.md; weeks 2–3 = usage period + eval deepening

---

## Milestones

### M1: Solid Foundation (Week 1)
**Goal:** Everything that exists works reliably. Backend is separated from UI.

**Tasks:**

- [x] **M1.1a — Design storage (decide only, no code)** (~1 hr)
  - Decide: SQLite schema (what columns, what types)
  - Decide: ChromaDB persistent setup (path, embedding model — just pick one)
  - Decide: what methods does Storage class need? (save, get_recent, search, get_by_category, get_by_date_range)
  - Write decisions in decisions.md. No code yet. Close the editor.

- [x] **M1.1b — Implement storage.py** (~1-2 hrs)
  - Build what you designed in M1.1a. Use AI assistant to write the code faster.
  - SQLite for structured data (id, content, type, category, tags, timestamp)
  - Persistent ChromaDB for semantic search
  - Test: save 5 notes, restart app, notes are still there
  - (Using AI to code is smart and realistic — the learning is in the decisions and debugging, not typing every line)

- [x] **M1.2 — Migrate existing JSON data** (~1 hr)
  - Write a small script to import your existing JSON entries into the new storage
  - Don't lose what you already captured
  - Test: old notes appear in the new system

- [x] **M1.3 — Separate UI from logic** (~2-3 hrs)
  - New app.py that only does Streamlit UI
  - All save/retrieve calls go through storage.py
  - No direct database or file access in app.py
  - Move save_entry() logic into storage.py
  - Test: app works exactly like before but code is in separate files

- [x] **M1.4 — Fix voice input** (~1-2 hrs)
  - ~~Debug the recent voice recording errors~~ — skipped: no logs exist to debug from, can't reconstruct what happened. Logging needed first (see buffer tasks).
  - Make sure audio saves and persists correctly
  - Consider: what happens if recording fails mid-way? — not possible with st.audio_input, it's all-or-nothing in the browser. Error handling covers post-recording failures only. True mid-recording protection requires a custom component (see parking lot: Streaming voice save).
  - Test: record 3 voice notes, close app, reopen, they're all there

- [x] **M1.5 — Basic error handling** (~1 hr)
  - What happens when save fails? (show error, don't lose the note)
  - What happens when ChromaDB is unreachable? (graceful fallback)
  - No need to be thorough — just catch the obvious crashes

**Buffer tasks (if you have time):**
- [ ] Clean up the entries/ folder structure
- [ ] Add a simple config.py for paths, API keys, model names
- [ ] Write a quick README with setup instructions
- [ ] Add file logging (logs/app.log) — log every save success/failure in storage.py and app.py dialogs. Needed to debug silent failures like the M1.4 "missing records" incident.

**Done when:** You can close the app, reopen it, and all your notes are there. Voice works. Code is in 2-3 files not one.

**Estimated time:** 7-10 hours
**Risk:** Over-engineering the Storage class. Set a timer. If you're debating init parameters for more than 15 minutes, pick one and move on.

---

### M2: Auto-Categorize (Week 2)
**Goal:** Every note gets automatically categorized on save. The "this feels smart" moment.

**Tasks:**

- [x] **M2.0 — Transcribe voice notes on save** (~1-2 hrs)
  - Whisper transcription runs on save, stores result as `content` in SQLite + ChromaDB
  - Audio file still saved to disk via `file_path`
  - Handle: Whisper failure (save the audio anyway, leave content as user-provided context)
  - Test: save a voice note, check that spoken words appear in search results
  
- [x] **M2.1 — Define your category list** (~30 min)
  - Write down 5-8 categories that cover 90% of what you actually note down
  - Intent-based categories (decided): reference, mood, journal, learning, achievement, task
  - Keep it short. You can always add more later.
  - Write them in a config or constants file
  - **Outcome:** 7 intent-based categories: `task`, `mood`, `journal`, `learning`, `reference`, `insight`, `achievement`. Defined in `config.py`. Design principle: categories = what you DO with the note, not what it's about.

- [x] **M2.2 — Build categorize.py** (~2 hrs)
  - Single function: takes note text, returns 1-2 categories from your predefined list
  - Use OpenAI API (you already have access for GPT-4V)
  - Simple prompt: "Categorize this note into 1-2 of these categories: [list]. Return JSON."
  - Handle: API failure (default to "uncategorized"), slow response, unexpected output
  - Test with 10 different types of notes you'd actually write
  - **Outcome:** `src/categorize.py` built. OpenAI for now, Ollama fallback ready once model downloads — both still to be validated in next phases. Wired silently into `storage.save()`. 9/12 accuracy; 3 misses are phrasing ambiguity — editability in M2.3/M2.4 handles them.

- [x] **M2.2b — Add service layer** (~1 hrs)
  - Create `src/notes_service.py` with a `NoteService` class between app.py and storage.py
  - Move `categorize()` call into service layer (out of storage.save())
  - `app.py` only talks to service, never to storage directly
  - Add `st.spinner("Saving...")` in app.py around all save calls
  - Architecture: `app.py` → `notes_service.py` → `categorize.py` + `storage.py` 
  - Test: save a note, spinner appears, category is assigned, note saves correctly

- [x] **M2.3 — Wire into save flow** (~1 hr)
  - When user saves any note, auto-categorize runs
  - Store categories in SQLite alongside the note
  - Show the assigned category after save ("Saved as: mood, exercise")
  - Test: save a note, check database, category is there

- [x] **M2.4 — Override option** (~1 hr)
  - User can see what category was assigned
  - User can change it if it's wrong (dropdown with predefined list)
  - This teaches you how good the auto-categorization actually is
  - Track: how often do you override? (just mentally, no need to build tracking)
  - **Note:** Also log every change to a `category_events` table (entry_id, ai_suggested, final, was_overridden, timestamp) — feedback data for improving categorization over time.

- [x] **M2.5 — Categorize existing notes** (~1 hr)
  - Run categorization on all previously saved notes (batch)
  - Small script, run once
  - Now your entire history has categories

- [x] **M2.6 — Edit note content** (~1 hr)
  - Expanded the ✏️ edit dialog (`edit_note_dialog`) to show a text area for content alongside category
  - Added `NoteService.update_note()` which calls `storage.update()` and refreshes ChromaDB
  - Unified `context` → `content` key in Capture page session state to match DB field name

**Buffer tasks:**
- [ ] Combine `content` + `description` for LLM categorization — currently only `content` is passed to `categorize()`. For voice notes, `description` is the user-provided context which may be more meaningful. Pass both fields to the prompt for richer classification.
- [ ] Try different prompt variations to improve accuracy
- [ ] Add a "suggest new category" mechanism (just a text file where you note categories that are missing)
- [ ] Test with Turkish notes — does the LLM handle mixed language?
- [ ] Consider cost: how much per note? Estimate monthly cost at your usage rate
- [ ] Test Whisper quality in quiet environment — if `base` is not good enough, run model comparison script on `experiments/data/voice/` with auto-scoring (difflib similarity) to compare `small`, `turbo`, `medium`
- [ ] Experiment with different models and prompts to conclude best categorization setup (OpenAI vs Anthropic vs Ollama, prompt variations)

**Done when:** You save a note, it auto-categorizes, you can see the category. All old notes are categorized too.

**Estimated time:** 5-7 hours
**Risk:** Prompt engineering rabbit hole. First version that works >80% of the time is good enough. Move on.

---

### M3: Organized Views (Week 3)
**Goal:** Multiple ways to see your notes. Build quick, decide later which you actually use.

**Tasks:**

- [x] **M3.1 — Redesign Recents page** (~2 hrs)
  - Show timestamp AND category label for each note
  - Visual distinction between categories (even just a colored tag or emoji prefix)
  - Keep reverse chronological order
  - Test: can you scan the page and quickly spot all "mood" entries?

- [x] **M3.2 — Category browse page** (~2 hrs)
  - New page: shows all your categories as sections or tabs
  - Tap a category → see all notes in it, newest first
  - Show count per category ("mood: 12 notes", "task: 8 notes")
  - Test: find a specific note faster through category than scrolling recents

- [x] **M3.3 — Mirror / weekly summary page** (~3 hrs)
  - This week: how many notes total, breakdown by category
  - Streak: how many consecutive days you've captured something
  - Simple highlight: most active category this week
  - Optional: show one random old note as "you said this X days ago" (the rediscovery moment)
  - Keep it simple — even just text stats is fine, no fancy charts needed
  - Test: does opening this page make you feel something? (if not, what's missing?)

- [x] **M3.4 — Update search page** (~1 hr)
  - Search results now show category labels
  - Fix the re-indexing problem (don't reload all files on every search)
  - Search uses persistent ChromaDB now (from M1)

- [x] **M3.5 — Navigation cleanup** (~1 hr)
  - Sidebar makes sense with the new pages
  - Decide on page names that feel natural
  - Remove or rename pages that don't fit anymore

**Buffer tasks:**
- [ ] Add date range filter to recents (this week / this month / all time)
- [ ] Add a simple "favorites" or "pin" feature for important notes
- [ ] Try a timeline view (notes on a visual timeline)
- [ ] Experiment with how journal entries look vs regular notes
- [ ] Mirror page: think through a streak/consistency concept that's engaging without guilt when it resets
- [ ] Mirror page: week-over-week delta — find a format that never reads as "less than last week"
- [ ] Mirror page: try Sunday-only reflection mode after initial real use
- [ ] **Testing: unit tests for `format_relative_time`** — pure function, no Streamlit dependency; cover today/yesterday/last week/old/empty/bad-string cases with pytest
- [ ] **Testing: service-layer search test** — save a note with a known category, search for it, assert the result dict has correct `category`, `content`, `content_type`; builds on existing `test_storage_implementation.py`
- [ ] **Testing: Streamlit AppTest for search page** — use `streamlit.testing.v1.AppTest` to simulate typing a query + clicking Search and assert category badge text appears in rendered output; only worth doing once the above two pass

**Done when:** You have 3-4 distinct views that each show your notes differently. You can browse by time, by category, and see a weekly summary.

**Estimated time:** 8-10 hours
**Risk:** Making views pretty instead of functional. Build ugly-but-working first. You can style later. Also: building all buffer tasks instead of the core ones.

---

### M4: Use, Learn, Prepare to Share (Week 4)
**Goal:** Use it daily. Collect honest feedback from yourself. Prep for GitHub.

**Tasks:**

- [ ] **M4.1 — Use it every day for a week** (ongoing)
  - Capture at least 2-3 notes per day using the app
  - Use ALL input types (text, voice, image)
  - Check the mirror page daily
  - Keep a running note (can be in the app itself): what annoys you? what's missing? what do you never use?

- [ ] **M4.2 — Fix the top 3 annoyances** (~3 hrs)
  - After 3-4 days of use, you'll have a clear list
  - Pick only the top 3, fix them
  - Ignore everything else — it goes in the parking lot

- [ ] **M4.3 — Write README** (~1-2 hrs)
  - What is this project (one paragraph)
  - Why you built it (the ADHD second brain angle — this is your story)
  - How to run it (setup instructions)
  - What works now, what's planned
  - Screenshots or a short GIF of it working

- [ ] **M4.4 — Clean up repo** (~1-2 hrs)
  - Remove experiment scripts and scratch files (or move to /experiments)
  - Add .gitignore (database files, API keys, pycache)
  - Make sure no API keys are in the code
  - requirements.txt or pyproject.toml
  - Folder structure makes sense to an outsider

- [ ] **M4.5 — Push to GitHub** (~30 min)
  - Create repo
  - Push code
  - This is the goal. Don't overthink it. Push.

- [ ] **M4.6 — Share with 1-2 friends** (~30 min)
  - Show them the app running on your phone
  - Ask: "what would you want this to do?"
  - Write down their reactions (not their feature requests — their reactions)

**Buffer tasks:**
- [ ] Record a short demo video (even just screen recording with voiceover)
- [ ] Write a short blog post or Twitter thread about what you learned
- [ ] Set up a simple project board for v2 features
- [ ] Plan your v2 milestones based on what you learned
- [x] **Search log + date/type filters** — replaced `query_log` with unified `search_log` (query nullable, + content_type, date_preset, result_count). Search page has date preset buttons (Today / This week / This month / All time) and type filter (All / Text / Voice / Image). Text present → ChromaDB with metadata pre-filters; no text → SQLite `get_entries()` directly. `created_at_ts` (Unix int) backfilled in ChromaDB to enable `$gte` range filters. See decisions.md 2026-07-10.

**Done when:** Code is on GitHub. You've used it for a week. You know what to build next.

**Estimated time:** 5-7 hours of active work + daily usage
**Risk:** Perfectionism on the README or repo structure. Nobody judges a prototype repo as harshly as you think.

---

## Parking Lot (NOT now, but captured so your brain can let go)

### Categorization (from M2 design session)
- [ ] Multiple categories per note — single category for now; may become unnecessary once chunking is added
- [ ] Chunking strategy — split long voice memos and journal entries into semantic chunks, label each chunk independently
- [ ] Auto-generated topic tags (health, food, tech, travel) — separate from intent categories, build after categories are stable
- [ ] Spaced repetition for `learning` notes — flashcard-style recall reminders

### Technical
- [ ] "Today" filters use UTC midnight — should be user-local timezone (Search presets, Journal day range, Mirror week math)
- [ ] Ask-voice audio retention — currently transcribe-and-delete; revisit if ask_log shows garbled queries / re-asks during usage period (evidence-driven decision, see decisions.md 2026-07-14 area)
- [ ] Migrate to Supabase (PostgreSQL + pgvector — replaces both SQLite and ChromaDB)
- [ ] Deploy to Streamlit Community Cloud
- [ ] Migrate from Streamlit to a more flexible framework
- [ ] Build a proper REST API (FastAPI)
- [ ] Mobile native app
- [ ] Offline support
- [ ] Better embedding model (finish comparison from scratch.md — experiments 2b/3/4 defined in docs/search_experiments.md)
- [ ] Query intent classification — detect retrieval-type ("show me my note about X") vs QA-type ("what have I learned about X?"); retrieval → return notes, QA → retrieve top-k + generate answer with LLM; simple heuristic first: question words (how, why, what should) → QA mode
- [ ] Multi-answer eval — extend eval_set.jsonl to support `expected_note_ids: [id1, id2]` for queries with multiple valid answers; update grader.py to score against the set (finding from experiment analysis)
- [ ] LangGraph for smarter search
- [ ] Graph database for note relationships
- [ ] Local LLM instead of OpenAI API
- [ ] Privacy-preserving embeddings
- [ ] Streaming voice save (fallback if recording fails mid-way)

### Features
- [ ] Pattern discovery ("you always feel stressed on Mondays")
- [ ] AI question answering over your notes
- [ ] Automatic summary generation
- [ ] Spaced repetition reminders
- [ ] Import from Obsidian/Notion
- [ ] Calendar integration
- [ ] Fine-tune OCR for your handwriting
- [ ] End-of-day nudge on the capture page: "Had any wins today?" — prompt user to log achievements at capture time, not on the reflection/mirror page
- [ ] Voice synthesis (read notes back to you)
- [ ] "You forgot about this" proactive surfacing
- [ ] Continuity nudges ("you were tracking mood for 4 days, you stopped")
- [ ] Achievement tracking ("you learned X things this month")
- [ ] PDF and markdown import
- [ ] Multi-user support

### Decisions for Later
- [ ] Hosting/deployment strategy
- [ ] Cost model (what's sustainable monthly spend on API calls?)
- [ ] Open source strategy (MIT? contributions?)
- [ ] Framework migration (what and when)

---

## Weekly Check-in Template
Every Sunday (or whenever), answer these honestly:

1. Which tasks did I complete this week?
2. Which tasks am I carrying over? Why?
3. Am I still on track for the milestone? If not, what do I cut?
4. What did I spend time on that WASN'T on this plan?
5. What's my energy/motivation level (1-5)?
6. One thing I'm proud of from this week:

---

## Rules for Myself
1. **One hour a day.** Not zero, not five. One.
2. **Follow the plan.** If something isn't on the milestone, it goes in the parking lot.
3. **Time-box decisions.** 15 minutes max to decide something technical. Pick and move.
4. **Ugly is fine.** Working > pretty. Always.
5. **When stuck, shrink the task.** If a task feels overwhelming, break it in half and do the first half only.
6. **Check in weekly.** Use the template above. Be honest.
7. **The parking lot is your friend.** Every cool idea goes there. It's not forgotten. It's just not now.

---

## Ideas & Big Picture Thoughts
Dump anything here during the month. No filtering, no organizing. Just date and thought.
Review during weekly check-in.

<!-- Example:
- 2026-05-06: What if the app could generate a "weekly letter to yourself" summarizing what you did?
- 2026-05-08: Look into how Notion AI handles auto-tagging
-->
