### 2025-10-30: Use GPT-4V instead of Tesseract/EasyOCR

**What I decided:** Use GPT-4V for image-to-text extraction

**Why:**
- Tesseract accuracy: ~0% on my handwriting
- EasyOCR accuracy: ~20-30% even with preprocessing
- Scanner app + GPT-4V: ~95% accuracy
- Cost is acceptable (~$0.01 per image)

**What I tried first:** 
Tesseract → EasyOCR → preprocessing experiments → all failed

**Trade-offs:**
- ✅ Pro: High accuracy, works immediately, handles poor images
- ✅ Pro: Can extract structure (code, lists) not just text
- ❌ Con: Costs money (~$3/month for daily use)
- ❌ Con: Requires internet connection
- ❌ Con: Data goes to OpenAI

**When to reconsider:** 
If cost exceeds $10/month, or if I need offline functionality

---
### 2026-05-07: [M1.1a] Storage architecture

| Decision | Detail |
|---|---|
| **Structured storage** | SQLite. Notes are same shape (text + metadata). Zero-config. Migrate to PostgreSQL/Supabase later when needed. |
| **Semantic search** | ChromaDB PersistentClient at `./chroma_data`. Default embedding model (all-MiniLM-L6-v2). Search index only — SQLite is source of truth. |
| **One Storage class** | Single `Storage` class in `storage.py`. UI layer only imports this. All read/write goes through it. Writes to both SQLite and ChromaDB. Deletes from both too. |
| **Soft delete** | `deleted_at` column in SQLite + remove from ChromaDB. Never lose data. |
| **Timestamps** | `created_at` + `modified_at`. Audit trail/event log is post-MVP. |
| **User ID** | `user_id TEXT DEFAULT 'default'`. No user logic yet. Text type because auth systems return string IDs (UUIDs). |
| **Categories** | DB table (`categories`), not config file. Predefined starting list. Users can add new ones deliberately — same list for LLM and user. Closed but growable. |
| **Tags** | Freeform JSON array in TEXT column. No validation needed. |
| **File storage** | Binary files (audio, images) stay on disk. SQLite stores `file_path`. Consistency validation is post-MVP. |

**Full design:** [`design/M1.1a-storage.md`](design/M1.1a-storage.md)

**When to reconsider:**  After getting done with MVP 

---

### 2026-05-12: [M1.1b] Config file for paths and defaults

**What I decided:** Paths (DB, ChromaDB) and default categories live in `config.py`, imported by `storage.py`. Override with parameters for testing.

**Why:**
- Single source of truth for environment config
- Easy to change DB location later (cloud sync, mobile modes)
- Non-developers can edit config without touching code
- Parameters still available for unit tests

**What I tried first:** Parameters only → too verbose; hardcoding → inflexible

**Trade-offs:**
- ✅ Pro: Flexible, environment-aware, testable
- ❌ Con: One extra file to manage

**When to reconsider:** If config grows too complex, migrate to `.env` or environment variables

---

### 2026-05-12: [M1.1b] Row factories + dict conversion

**What I decided:** Use `sqlite3.Row` row_factory to access columns by name, always convert `Row → dict` before returning to UI layer.

**Why:**
- `row["column"]` more readable than `row[2]`
- Safe on schema changes (tuple indices break, dict keys don't)
- UI layer never touches SQLite directly

**What I tried first:** Raw tuples → hard to maintain, fragile indexing

**Trade-offs:**
- ✅ Pro: Readable, refactor-safe, clear API boundary
- ❌ Con: Tiny overhead of Row→dict conversion (negligible)

**When to reconsider:** If performance becomes critical (unlikely for MVP)

---

### 2026-05-12: [M1.1b] ISO 8601 timestamps (not UNIX)

**What I decided:** Store all timestamps as ISO 8601 text with UTC explicit (`"2026-05-12T10:30:00Z"`), not UNIX integers.

**Why:**
- Human-readable when debugging databases at 3am
- JSON-friendly (Streamlit serializes natively)
- Portable for backups/exports
- Explicit UTC prevents timezone confusion

**What I tried first:** Considered UNIX timestamps → less readable, more parsing needed

**Trade-offs:**
- ✅ Pro: Debuggable, portable, JSON-native
- ✅ Pro: Same query speed for MVP (no 10M rows)
- ❌ Con: String sorting slower than number sorting (doesn't matter for MVP)

**When to reconsider:** If sorting 100K+ entries becomes slow, add UNIX column post-MVP

---

### 2026-05-12: [M1.1b] Soft delete with `deleted_at` NULL check

**What I decided:** Soft delete: set `deleted_at` column to ISO timestamp (never NULL on delete). Query filter: `WHERE deleted_at IS NULL`. No boolean flag.

**Why:**
- Audit-friendly: `WHERE deleted_at IS NOT NULL` shows what you deleted and when
- Self-documenting: `deleted_at IS NULL` clearly means "not deleted"
- Reversible: set `deleted_at = NULL` to "undelete" if needed
- Same performance as BOOL (SQLite indexes NULL values fine)

**What I tried first:** Considered `is_deleted BOOL` → cryptic, loses deletion timestamp

**Trade-offs:**
- ✅ Pro: Clear intent, audit trail, reversible
- ❌ Con: Requires WHERE filter on every query (wrap in helper function)

**When to reconsider:** If index performance degrades (add index post-MVP)

---

### 2026-05-13: [M1.2] Migration — field mapping and search strategy

**What I decided:** Added `description` field to schema. For voice/image entries: old `context` → `description`, `content` left null (filled later by Whisper/OCR). For text entries: `context` → `content`, `description` null. ChromaDB indexes `content + description` combined.

**Why:**
- Voice/image `context` was user-typed notes, not transcription — wrong field for `content`
- `description` is nullable for all types so text entries can use it later (e.g. titles)
- Combining both fields for ChromaDB gives richer search without schema complexity

**Trade-offs:**
- ✅ Voice/image entries are searchable via description until transcription is added
- ❌ `content` is null for all voice/image until M1.4 runs Whisper/OCR

**Future notes:**
- M1.4: fill `content` for voice entries with Whisper transcriptions
- M2: Q&A/RAG page sits on top of the same search index, passes both fields to LLM
- Post-MVP: note splitting (one recording → multiple entries) needs `parent_id` column
- Post-M1.4: once all voice/image entries have transcriptions, restore `content TEXT NOT NULL` constraint and verify no nulls remain

---

### 2026-05-14: [M1.3] Pydantic Entry model as UI↔storage contract

**What I decided:** An `Entry` Pydantic model in `src/models/entry.py` is the single contract between `app.py` and `storage.py`. `storage.save()` accepts `Entry` directly — no dict dumping at the call site.

**Why:**
- Type validation at the boundary: wrong fields or types raise before reaching the database
- IDE autocomplete on `entry.` throughout storage code
- Passing the model directly is cleaner than `model.model_dump()`

**Trade-offs:**
- ✅ Catches field mistakes at save time, not at query time
- ✅ Storage importing models is correct here — they're part of the same application. Models survive any backend migration (e.g. SQLite → Supabase); only `storage.py` internals change.

---

### 2026-05-14: [M1.3] src/models/ folder, not a single models.py

**What I decided:** Models live in `src/models/` as individual files (`entry.py`), with `__init__.py` re-exporting for clean imports (`from src.models import Entry`).

**Why:**
- One file per model scales without refactoring when new models arrive (e.g. `Category`, `SearchResult`)
- `__init__.py` re-export means callers don't change if a model moves or is renamed

---

### 2026-05-14: [M1.3] Session state stays as plain dicts

**What I decided:** `st.session_state.entries` holds plain dicts, not `Entry` objects.

**Why:**
- Session state entries hold raw Streamlit objects (`UploadedFile`) for in-session display — these can't be put into a Pydantic model
- Session state is ephemeral UI state, gone on page refresh — not worth modeling
- `Entry` is only for the storage boundary

---

### 2026-05-14: [M1.3] @st.cache_resource for Storage instantiation

**What I decided:** `Storage()` is wrapped in `@st.cache_resource` so it's created once per server lifetime, not on every Streamlit rerun.

**Why:**
- Streamlit reruns the entire script on every user interaction
- Without the cache, a new SQLite connection and ChromaDB client would open on every rerun
- Data stays on disk — the cache only keeps the connection object alive

---

### 2026-05-14: [M1.3] save_file() in app.py — known shortcut

**What I decided:** The helper that writes a Streamlit `UploadedFile` to disk lives in `app.py`, not `storage.py`.

**Why:**
- `storage.py` shouldn't know about Streamlit's file objects
- `storage.save()` receives `file_path: str` — storage only cares where the file ended up

**Trade-offs:**
- ✅ Keeps storage framework-agnostic
- ❌ `app.py` currently acts as both view and controller. Will move to a service layer when M2 LLM logic makes it necessary.

---

### 2026-05-14: [M1.3] UUID for file names, not type_timestamp

**What I decided:** Media files saved as `entries/{uuid}{ext}` instead of `entries/{type}_{YYYYMMDD_HHMMSS}{ext}`.

**Why:**
- Old format collides if two entries are saved in the same second
- Type and timestamp are already stored as separate columns in SQLite — encoding them in the filename is redundant

**Trade-offs:**
- ✅ No collision risk
- ❌ Can't identify a file by browsing `entries/` — need a DB query. Acceptable: the app is the interface, not the filesystem.

---

### 2026-05-14: [M1.4] Voice input — error handling and auto-save on recording finish

**What I decided:**
- Audio file written to disk immediately when `st.audio_input` returns a value (recording stops), path stored in `st.session_state.voice_draft_path`
- Save button only does the SQLite/ChromaDB write — file is already safe before user touches context or clicks anything
- Stale draft path cleared when dialog opens with no recording (handles dismissed-without-saving case)
- All three dialogs (voice, image, text) wrapped in try/except: error shown, dialog stays open, no `st.rerun()` on failure so the user can retry without re-recording

**Why:**
- With the old flow (file + DB write both on button click), a DB failure meant re-recording from scratch
- Audio is the highest-friction input to redo — file safety matters most there
- Dialog staying open on error means retry without losing anything

**Constraints discovered:**
- Mid-recording protection is not possible with `st.audio_input` — browser records entirely in memory, sends the complete file only when the user stops. Crash during recording = data gone. True protection needs a custom Streamlit component (parking lot: Streaming voice save).
- "Debug the recent recording errors" sub-task was skipped — no logs exist to reconstruct what happened. File logging added to M1 buffer tasks.

**Trade-offs:**
- ✅ File on disk before any DB interaction — survives DB failures
- ✅ Orphaned files (recorded but dialog dismissed) are acceptable for MVP — recoverable later
- ❌ Mid-recording data loss remains unaddressed until a custom component is built

**When to reconsider:** When adding a custom recording component for true streaming save (parking lot)

---

### 2026-05-18: [M1.5] Error handling strategy — what surfaces to the user vs what stays in logs

**What I decided:**
- SQLite failures → always raise, always shown to user (SQLite is source of truth — if it fails, the operation genuinely failed)
- ChromaDB runtime failures (save/update/delete) → caught, logged as WARNING, not shown to user (note is safe in SQLite; search degradation is a background concern)
- ChromaDB search failure → raises, shown as "Search temporarily unavailable" (distinguishes broken search from empty results)
- Storage init failure → shown as full-page error + `st.stop()` (nothing works without SQLite)
- All errors logged to `logs/app.log` via rotating file handler

**Why:**
- Users shouldn't see internal infrastructure messages — "ChromaDB index failed" means nothing to them
- Hiding ChromaDB save failures is safe because SQLite is source of truth; the note is not lost
- "No results found" when search is broken is a lie — needs a distinct message
- Logs give a durable record for debugging silent failures (the M1.4 lesson)

**Trade-offs:**
- ✅ User sees accurate, actionable messages — not internal errors
- ✅ Every failure is recorded in logs regardless of whether it surfaces to UI
- ❌ ChromaDB save failures are silent to the user — they won't know a note won't appear in search until they search for it

**Future work:** Add a ChromaDB sync/recovery mechanism — on startup or on demand, compare SQLite entries against ChromaDB and re-index anything missing. This covers entries that were saved to SQLite but failed to index (ChromaDB down, crash mid-save, etc.)

**When to reconsider:** If ChromaDB failures become frequent enough to matter, add a visible search-index health indicator

---

### 2026-05-18: [M1.5] No degraded mode flag for ChromaDB

**What I decided:** No `_chroma_ok` flag or degraded mode. ChromaDB init failure is fatal (raises). Runtime failures are caught per-call.

**Why:**
- A flag set at init becomes stale: ChromaDB could recover (e.g. a lock clears on restart) but the flag would stay `False` for the entire session
- Per-call exception handling naturally recovers if ChromaDB comes back — no stale state
- If ChromaDB can't init at all, the app shouldn't silently pretend search exists

**Trade-offs:**
- ✅ No stale state — each call reflects actual ChromaDB health at that moment
- ❌ No fast-path skip if ChromaDB is persistently down (minor overhead of repeated failed calls)

---

### 2026-05-18: [M1.5] File logging with rotating handler

**What I decided:** Python's standard `logging` module, single `second_brain` logger configured in `src/logger.py`. Writes to `logs/app.log` with 1MB rotation and 3 backups. Warnings and errors also print to terminal.

**Why:**
- M1.4 had silent failures with nothing to debug from — logs are the fix
- Standard library only, no new dependencies
- Single logger shared across `storage.py` and `app.py` — one place to configure
- `if not logger.handlers:` guard prevents duplicate handlers on Streamlit reruns

**Log levels used:**
- INFO: every successful save / update / delete / init
- WARNING: ChromaDB runtime failures (operation succeeded in SQLite)
- ERROR: ChromaDB search failure, duplicate entry, storage init failure

---

### 2026-05-18: [M1.5] Voice dialog — accurate "safe on disk" message

**What I decided:** Error message after a failed Save only says "audio file is safe on disk" if `voice_draft_path` is present in session state. Otherwise says "please try recording again."

**Why:** The auto-save can itself fail (e.g. disk full). `voice_draft_path` presence is the only reliable signal the file actually landed on disk — without it, telling the user it's "safe" is misleading.

---

### 2026-05-18: [M2.0] Whisper transcription — model, loading, and field mapping

**What I decided:**
- Model: `base` — chose the fastest model for initial testing. Further investigation after observing real-use weaknesses.
- Lazy loading via `@st.cache_resource`: model loads on first transcription call, stays in memory for the session. `processing.py` exposes `load_model()` and `process_voice_note(path, model)` — no Streamlit import in the processing layer.
- Field mapping: transcription → `content`, user's typed context → `description`. On failure, context falls back to `content` so the note is never empty.

**Why:**
- Module-level `whisper.load_model()` (old code) ran on every import, blocking app startup
- `@st.cache_resource` in `app.py` keeps the loaded model object alive across reruns without coupling `processing.py` to Streamlit
- `description` was already the right field for user-typed context (set in M1.2 migration); `content` is for machine-extracted text

**Trade-offs:**
- ✅ First transcription per session: ~6s (3s model load + 3s audio). All subsequent: ~3s.
- ✅ Graceful fallback: Whisper failure never loses a note
- ❌ `base` model struggles with Turkish and noisy environments — tested, known limitation

**When to reconsider:** If transcription quality is consistently bad in real use, run a model comparison experiment against `experiments/data/voice/` test files with auto-scoring (difflib similarity). Candidates: `small` (perfect on EN, ~7s) or `turbo` (untested).

**Future work:** Think through failure cases more carefully — if heavier models prove unreliable or too slow on device, consider a tiered fallback strategy (e.g. try `small`, fall back to `base` on timeout).

---

### 2026-05-20: [M2.1] Intent-based category design

**What I decided:** 7 categories defined by what you DO with the note, not what it's about: `task`, `mood`, `journal`, `learning`, `reference`, `insight`, `achievement`.

**Why:**
- Topic-based categories (health, food, tech) grow forever and cause overlap — the same note fits multiple topics
- Intent-based categories are stable: there are only so many reasons to save a note
- Topics become auto-generated tags later (separate concern, separate pipeline)

**Trade-offs:**
- ✅ Small stable set — AI and user agree on what each means
- ✅ `journal` stayed but narrowly redefined: daily activity log only, not catch-all
- ❌ Edge cases exist where the same event fits two categories depending on phrasing ("July Turkey crowded" = `reference` or `insight`). Accepted — editability handles it.

**Full design:** [`design/M2-categorization.md`](design/M2-categorization.md)

**When to reconsider:** After ~100 notes, if a category is almost never used or always wrong, drop or redefine it.

---

### 2026-05-20: [M2.2] Categorization approach — single category, LLM chain, silent on save

**What I decided:**
- One category per note (not multiple)
- LLM chain: OpenAI (gpt-4o-mini) → Anthropic (Haiku) → Ollama (llama3.2) → fallback `"journal"`
- Runs silently in `storage.save()` — user never sees a spinner or failure
- Category descriptions in `config.py` drive the prompt — tweak descriptions to change behaviour

**Why:**
- Single category keeps filtering unambiguous and the feedback loop clean
- Chain approach means no hard dependency on any one provider — credits run out, switch providers
- Silent on save = zero friction for capture (ADHD design principle)
- 9/12 accuracy is good enough; remaining 3 are phrasing-ambiguity edge cases

**Trade-offs:**
- ✅ Zero added friction to the save flow
- ✅ Provider-agnostic — any key works
- ❌ User doesn't see the assigned category until they open the note (M2.3 adds this)
- ❌ Misclassifications are silent until editability is built (M2.3/M2.4)

**Full design:** [`design/M2-categorization.md`](design/M2-categorization.md)

**When to reconsider:** If override rate for any one category stays above 30% after 100 notes — that's the signal to revise its description.

---

### 2026-05-21: [M2.2b] Service layer — NoteService between app and storage

**What I decided:** Added `src/notes_service.py` with a `NoteService` class. `app.py` only talks to `NoteService`, never to `Storage` directly. `categorize()` call moved from `storage.save()` into `notes_service.save_note()`.

**Why:**
- `storage.save()` had business logic (LLM call) mixed into the data layer — wrong abstraction level
- Service layer is where orchestration belongs: categorize, then save, then log events (M2.3)
- `storage.py` stays pure data operations — no LLM imports, no categorization logic

**Architecture:**
```
app.py → notes_service.py → categorize.py + storage.py
```

**Trade-offs:**
- ✅ Data layer stays framework-agnostic — storage knows nothing about LLMs
- ✅ Adding new logic (event logging, auto-tagging, summarization) goes in service, not storage
- ✅ Journal entries pass `category="journal"` explicitly — service skips categorization for them
- ❌ One more file to understand for new contributors

**Future work:** When multiple AI operations exist (M3 summarization, future Q&A), extract an `ai_service.py` layer under `notes_service.py`. Not worth it for a single `categorize()` call.

**When to reconsider:** Never extract a layer until it has 2+ operations sharing setup (retry logic, model selection). One operation belongs in its own module, not wrapped in a service.

---

### 2026-05-21: [M2.3] Category displayed on entry card, not as a toast banner

**What I decided:** After saving a note, the assigned category shows as a `st.caption` on the entry card in `st.session_state.entries`, not as a separate success banner.

**Why:**
- `@st.dialog` calls `st.rerun()` on save, which closes the dialog and reruns the full page — any `st.success()` rendered inside the dialog before `st.rerun()` is never actually seen
- Entry cards in `session_state` persist for the whole session, so the category stays visible while the user is on the Capture page
- Same `entry.get("category")` pattern works identically on the Recent page, where entries come from the DB

**Trade-offs:**
- ✅ No timing tricks or session_state plumbing just for a notification
- ✅ Category is part of the note's identity, not a flash message — feels more natural
- ✅ Category is persisted in SQLite permanently — the Recent page always shows it from DB
- ❌ The Capture page's in-session list clears on page refresh — Recent is the persistent view

---

### 2026-05-21: [M2.3] category_events table — separate log, not bundled into save

**What I decided:** Every save logs to a `category_events` table via `storage.log_category_event()`, called by `NoteService.save_note()` after `storage.save()`. Two separate calls, not one.

**Why:**
- `storage.save()` is pure data persistence — it shouldn't know whether a category came from AI or a human
- `NoteService` has the context: it knows `ai_suggested` vs `final_category` because it ran `categorize()`. Storage doesn't have this context unless you pass it in, which would pollute the storage API
- Separate calls = isolated failure: if logging throws, the note is already safely saved

**Schema:** `(id, entry_id, ai_suggested, final_category, was_overridden=0, created_at)`. `was_overridden` hardcoded to `0` for now — M2.4 will add the override UI and set it to `1` on user changes.

**When to reconsider:** If the event log design changes significantly (e.g. multi-category or pre-save confirmation), revisit whether `save_note()` should accept `ai_suggested` as an explicit param rather than computing it internally.

---

### 2026-05-22: [M2.4] Category override — dialog via ✏️ icon, event_type replaces was_overridden

**What I decided:**
- Override UI: ✏️ icon next to category caption in a two-column layout. Tapping opens a `@st.dialog` with a selectbox pre-selected to current category.
- `category_events` schema: renamed `was_overridden INTEGER` → `event_type TEXT` (`'ai_assignment'` / `'user_override'`). Migration script: `scripts/migrate_m2_4_event_type.py`.
- `NoteService.override_category()` calls `storage.update()` + `storage.log_category_event(..., event_type='user_override')`.

**Why event_type over was_overridden:**
- Event log tables have event types, not boolean flags
- Adding new event types (e.g. `'batch_recategorize'` in M2.5) requires no schema change — just a new string value
- More readable in queries and future analytics

**Why dialog over inline selectbox:**
- Only one dialog renders at a time — no Streamlit widget key collisions in loops
- Cards stay clean; edit affordance is discoverable but not intrusive
- Mobile-friendly: tap, change, confirm

**Scope decision:** Category-only for M2.4. Content editing moved to M2.6 — Whisper transcription quality makes it necessary but it's a separate concern.

**When to reconsider:** If override rate for any category stays above 30% after ~100 notes, revise that category's prompt description rather than making UX more prominent.

---

### 2026-06-08: [M3.1] Recents page — card layout and category colors

**What I decided:**
- Each entry renders in a `st.container(border=True)` card
- Category shown as a muted pill badge: `rgba` tinted background + dark matching text + subtle border. One color per category (7 total).
- Timestamp on every entry including older ones: `Today HH:MM` / `Yesterday HH:MM` / `DayName HH:MM` / `Mon DD HH:MM`
- Metadata row (pill + timestamp + edit button) sits at the **bottom** of the card, content first

**Why:**
- Colors over emojis: easier to spot a category at a glance when scanning a list — color fires faster than reading an emoji
- Muted pills over solid vivid: solid colors felt heavy and loud; `rgba` tint keeps the badge informative without dominating the content
- Metadata at bottom: content is the point — category and time are context, not headlines
- Time always included (not just date for old entries): a note from last week at 2am means something different than one at 9am

**Trade-offs:**
- ✅ Scannable by category without reading content
- ✅ Timestamps give temporal context at a glance
- ❌ Edit button renders full-width in its column — Streamlit doesn't size buttons down easily. Accepted for now since app will eventually leave Streamlit.

**When to reconsider:** When migrating off Streamlit — rebuild the card component natively with proper CSS control.

---

### 2026-06-09: [M3.2] Category browse page — grid layout and drill-down navigation

**What I decided:**
- Page name: "Categories" in sidebar
- Layout: 2-column grid of cards, each showing category name (colored badge) + note count. Tap "Open →" → drill into note list for that category. "← Back" returns to grid.
- Navigation state: `st.session_state.selected_category` (None = grid, string = note list). `st.rerun()` after state change to re-render immediately.
- Note list inside a category: no category badge — it's redundant context. Shows content + timestamp + edit button only. Edit dialog still allows changing category (supports fixing wrong categorizations).
- `CATEGORY_COLOR` extracted to module level — shared by Recent and Categories pages.
- Categories with 0 notes still show in the grid — helps spot unused categories.

**Why:**
- Grid with drill-down gives a spatial overview — easier to see which categories are active at a glance vs tabs or accordions
- Session state + rerun is the standard Streamlit navigation pattern — no routing library needed
- Hiding the category badge inside the category view reduces noise; you're already in context

**Trade-offs:**
- ✅ Overview + drill-down in one page, no extra sidebar entries
- ✅ Reuses existing `storage.get_by_category()` and `storage.get_category_counts()` — no new storage code
- ❌ `st.rerun()` navigation is manual and stateful — will need a real router when migrating off Streamlit

**Also fixed:** Discovered voice entries with `description=NULL` where user-typed context had fallen back to `content` (Whisper didn't run). Added `scripts/migrate_backfill_whisper.py`: moves `content → description`, runs Whisper, sets real transcription as new `content`.

---

### 2026-06-12: [M3.4] Delete note — placed inside edit dialog, not on card

**What I decided:** Delete lives inside the Edit Note dialog as a full-width red button below Save. No separate delete button on the note card.

**Why:**
- Adding a delete button directly on each card makes cards visually busy (two icon buttons competing)
- Edit dialog is already a deliberate action — delete fits naturally as a secondary action inside it
- Confirmation step (Yes / Cancel) inside the dialog is the safety net

**What I tried first:** Separate 🗑️ button next to ✏️ on the card → too cluttered. Delete in a side column next to Save inside the dialog → visual imbalance between button sizes.

**Trade-offs:**
- ✅ Cards stay clean — one edit affordance per card
- ✅ Delete requires two deliberate taps (open dialog → confirm) — accidental deletion is hard
- ❌ Slightly more taps to delete than a direct card button

**When to reconsider:** If users frequently open edit just to delete — add a swipe-to-delete gesture when migrating off Streamlit.

---

### 2026-06-12: [M3.4] Button color semantics — Save neutral, Delete red on confirmation only

**What I decided:** Save button is `type="secondary"` (neutral/white). Delete button is `type="primary"` (red). Confirmation "Yes, delete" is also red. Cancel is neutral.

**Why:**
- Streamlit's primary color in this theme is red/coral — using `type="primary"` for Save made the safe action look dangerous
- Red should only appear when an action is irreversible — the delete button and its confirmation are the right place for it
- This matches the convention: red = stop/danger, neutral = proceed safely

**Trade-offs:**
- ✅ Color communicates risk accurately — user can scan the dialog and immediately know which button is dangerous
- ❌ Save looks less prominent than Delete — acceptable since the dialog is already opened with intent to save

---

### 2026-07-10: [M4] Unified search_log — replacing query_log, merging search paths

**What I decided:**
- Replaced `query_log` (text-only, never-null) with `search_log` capturing full context: `query` (nullable), `content_type`, `date_preset`, `result_count`
- `NoteService.search()` handles both execution paths in one method: text present → ChromaDB vector search with metadata pre-filters; no text → SQLite `get_entries()` with the same filters directly
- `Storage.get_entries()` added as a SQLite-only retrieval method (dynamic WHERE clause, no ChromaDB)
- `created_at_ts` (Unix int) stored in ChromaDB metadata alongside `created_at` ISO string — enables `$gte`/`$lte` range filters (ChromaDB only supports numeric operators for ranges)
- One-time migration backfills `created_at_ts` for all existing ChromaDB documents on Storage init

**Why:**
- `query_log` logged empty strings when filters were used without text — meaningless data
- ChromaDB `$gte` only accepts numbers, not ISO strings — `created_at_ts` is the fix
- Vector search on an empty string is meaningless; SQLite handles filter-only queries directly
- One `search()` method means the caller never has to choose which path to use
- `search_log` with nullable query serves both use cases: filter `WHERE query IS NOT NULL` → eval dataset; all rows → usage analytics (filter popularity, result counts)

**Trade-offs:**
- ✅ Single caller interface for all search scenarios
- ✅ `result_count` in the log reveals which searches succeed — signals dataset gaps
- ✅ `date_preset` stored as a UI label ("This week") — human-readable for analytics
- ❌ Two metadata timestamps in ChromaDB (`created_at` string + `created_at_ts` int) — redundant but ChromaDB's limitation forces it
- ❌ `date_preset` label depends on when the log was written (e.g. "This week" means different dates each time)

**When to reconsider:** When building the eval pipeline, join `search_log` with a future click-tracking table to know which result the user actually opened. That pair is the ground-truth dataset.

---

### 2026-06-12: Categories table — one-time cleanup of stale entries

**What I decided:** Ran a one-time SQL delete to remove stale categories (`exercise`, `idea`, `memory`, `thought`) from the `categories` table.

**Why:** The old `sqlite_storage.py` schema (now unused) seeded a different starting list. `Storage._init_db()` uses `INSERT OR IGNORE` so it adds missing defaults but never removes stale ones. The dropdown in the Edit dialog reads from the `categories` table, so stale entries appeared as valid options.

**Fix applied:**
```sql
DELETE FROM categories WHERE name NOT IN ('task','mood','journal','learning','reference','insight','achievement');
```

**When to reconsider:** If the category list in `config.py` changes, manually sync the DB table. Future: consider a startup sync that removes categories not in `DEFAULT_CATEGORIES` — but only after category-add UI exists and there's a real risk of drift.

---

### 2026-06-10: [M3.3] Mirror page — snapshot, consistency, and rediscovery design

**What I decided:**

**Snapshot (section A)**
- Total notes in the rolling last 7 days as a flat number. No week-over-week delta — any comparison can introduce a "down" signal (the guilt trap). Delta approach needs more thought before adding — parked.
- Cumulative total ("X notes so far") shown nearby — only ever climbs.
- Category breakdown as counts using the colored pill badges from the Recent/Categories pages.

**Consistency (section B)**
- 7-dot row always shown (● = captured that day, ○ = nothing). Visual, non-judgmental.
- "You showed up X of 7 days" shown only when X > 0. If X = 0, show nothing — not even the sentence.
- No streak counter, no consecutive-days number. Classic streak framing resets to 0 and the reset becomes a demotivating signal. Dropped entirely for v1.
- Rolling last 7 days. Sunday-only mode (show a full week behind you when opening on Sunday) is a better-fit option to try after initial real use — parked, not decided yet.

**Top category interpretation (section C)**
- One hardcoded sentence per category, warm and factual. Only the top category of the week gets a sentence.

**Rediscovery (section D)**
- One random note older than 7 days, drawn from `insight` and `achievement` only.
- `learning` excluded: better suited for a future topic-grouped page. `task` excluded: old to-do reads as "you forgot this." `reference`, `mood`, `journal` excluded: emotionally flat for a rediscovery moment.
- `random.choice` over the eligible pool — no weighting for v1.
- Notes longer than 300 characters excluded from the pool. Long entries (even correctly categorised ones) don't make good rediscovery moments — they feel like unfinished work, not a punchy insight. Short notes surface cleaner memories. This also incidentally filters out long journal entries that got miscategorised as `insight`.

**Why:**
- ADHD design principle: every element must make you want to come back, never make you want to hide.
- No delta and no streak counter remove the two main guilt branches from A and B.
- Limiting rediscovery to insight/achievement maximises the chance the surfaced note feels meaningful.

**Trade-offs:**
- ✅ No element can produce a "bad" reading
- ❌ Rediscovery pool is small if insight/achievement usage is low — acceptable for v1, widen later if needed

**When to reconsider:**
- Delta: week-over-week is too blunt. Think through a better format before adding — something that shows trend without a single number that reads as "less than last week."
- Sunday-only mode: try after enough real use to know if rolling 7 feels stale mid-week.
- Widen rediscovery pool if insight/achievement notes feel too sparse in practice.
- Rediscovery length cap: 300 chars chosen without much data — revisit if good notes are being excluded.
- Streak concept: think about how to make it engaging without the guilt of resetting — needs more thought before building.

---

### 2026-07-13: [M4.2] Embedding model — switched from all-MiniLM-L6-v2 to bge-large-en-v1.5

**What I decided:** Replaced ChromaDB's default embedding model (`all-MiniLM-L6-v2`) with `BAAI/bge-large-en-v1.5`. Configured via `EMBEDDING_MODEL` in `config.py`. Query-time instruction prefix applied in `storage.search()`.

**Why:**
- Experiment results on 36-note dataset: Rank@1 improved from 61% → 72%, Avg Precision from 0.698 → 0.783
- bge-large is notably better at emotional/mood queries and journal/venting entries — the most common note types in this app
- `sentence-transformers` was already a dependency — no new packages needed

**What I tried first:** Default ChromaDB embedding (all-MiniLM-L6-v2, 384 dims, 22M params)

**Trade-offs:**
- ✅ +11% Rank@1, +0.085 Avg Precision on real-note dataset
- ✅ Better emotional query handling (key for mood/journal retrieval)
- ❌ bge-large regresses on abstract/metaphorical queries — but these are rare in practice
- ❌ Slower inference and larger model (~335M params, ~1.3GB download on first run)
- ❌ Dimension change (384 → 1024) required wiping and re-indexing ChromaDB

**Migration:** Deleted `chroma_data/`, re-indexed 151 entries via `scripts/reindex_chroma.py`. SQLite is source of truth — no data loss risk.

**When to reconsider:** If inference speed becomes noticeably annoying during daily use, switch back to `all-MiniLM-L6-v2` in `config.py` and re-run `scripts/reindex_chroma.py`.

---

### 2026-07-13: [M4.2] RAG pipeline — query analyzer design

**What I decided:**
- Query analyzer is LLM call #1 in the RAG pipeline: takes raw user text, returns a `QueryPlan` dataclass with `{intent, time_filter, category_filter, content_type, k}`
- Provider chain: OpenAI → Anthropic → plain default (no heuristics)
- Plain default: `{intent: "qa", k: 8, everything else: null}` — "do a semantic search and synthesize an answer"
- Lives in `src/rag/analyzer.py`; the full pipeline lives in `src/rag/` (analyzer, retrieval, generator)

**Intent types and k values:**
| Intent | Triggered by | k |
|---|---|---|
| browse | wants a list ("show me", "list", "find all") | 0 (no LLM generation) |
| factual | specific stored fact ("where did I put", named item) | 5 |
| qa | open question needing synthesis | 8 |
| pattern | aggregation over time ("lately", "how has my mood been") | 20 |

**Why no heuristic fallback:**
- Heuristics are English-only — Turkish queries won't match
- Brittle to phrasing variations — the list grows forever as edge cases appear
- Both providers being simultaneously down is rare; plain default is honest and safe in that case
- If fallback triggers too often in real use, add Ollama then (don't build for a rare edge case)

**Why plain default is "qa" not "browse":**
- "qa" (semantic search + generate answer) is a reasonable response to almost any query
- "browse" (return a list) is less useful when we don't know the intent — a generated answer is more helpful than a random list of notes

**When to reconsider:** Add Ollama as third fallback if logs show `"All query analysis providers failed"` appearing frequently in real use.

---

### 2026-07-13: [M4.2] RAG retrieval — category filter is hard gate for browse, hint for everything else

**What I decided:**
- `category_filter` from the QueryPlan is applied as a hard ChromaDB filter **only for browse intent**
- For factual/qa/pattern intents, `category_filter` is passed to the generator as context — not used to filter retrieval
- Semantic search retrieves notes regardless of category; the LLM judges relevance

**Why:**
- Categorization accuracy is ~75% (9/12 in M2 tests) — 1 in 4 notes may be miscategorized
- Hard filtering at retrieval on an imperfect category means silently missing notes. For a factual query ("where did I put my manual?"), a miscategorized note returns nothing — wrong answer with no signal that something was missed
- Browse is the exception: user explicitly said "show me my tasks" — they are choosing to filter by category. They see a list and can notice gaps themselves

**Implication:**
- `retrieval.py`: builds `where` clause with category only when `intent == "browse"`
- `generator.py`: receives `category_filter` as a hint in the prompt for non-browse intents ("user was asking about their learning notes")

**When to reconsider:** Once category override data accumulates (from `category_events` table), calculate real per-category accuracy. If any category reaches >95% accuracy consistently, it's safe to use as a hard filter for that category.

---

### 2026-07-13: Process — re-cut M4 around the ask-a-question loop; two-track workflow adopted

**What I decided:**
- MVP bar is the end-to-end loop "ask a question, get an answer" (came from a real-user test). Sequence: commit RAG pipeline → minimal Ask page → README + cleanup + GitHub push → then a **2–3 week usage period** with no new features.
- Adopted a two-track workflow: **build sessions** (small predefined weekly tasks, one task = one commit = one decision entry) and **learning sessions** (curiosity-driven, must end with an artifact in `docs/learning/`). Full guide: [`workflow.md`](workflow.md).
- Tasks over ~1 hr get a half-page spec first ([`design/_template.md`](design/_template.md)); implementation standards decided once and applied via [`engineering-standards.md`](engineering-standards.md).

**Why:**
- Review of 33 past sessions showed finishing repeatedly lost to starting: M4 ship tasks deferred while new scope (RAG, embeddings, tags design) kept arriving; work sat uncommitted for weeks; learning threads swallowed build sessions.
- The usage period doubles as data collection: real queries land in `search_log` and become the realistic eval dataset the learning track was missing.

**Trade-offs:**
- ✅ Both goals (usable app + learning/interview prep) get dedicated space and feed each other
- ❌ Curiosity-driven detours during build sessions now get parked, which takes discipline

**When to reconsider:** At a weekly check-in, if the split feels heavier than the problem it solves — simplify the rules, don't abandon the separation.

---

### 2026-07-14: [M4.2b] ask_log + AskService — instrumentation before usage

**What I decided:**
- New `ask_log` table records every Ask interaction: query, input_type (text/voice), intent, retrieved note ids (JSON), answer, result_count, **model provenance** (`analyzer_model`, `generator_model` — nullable; None = fallback/no LLM), **stage latencies** (`analyzer_ms`, `retrieval_ms`, `generation_ms` as INTEGER ms), nullable `error`, created_at. Failures are logged as rows with `error` filled.
- New **`AskService`** (`src/rag/service.py`) — a *peer* of NoteService, not an extension of it: NoteService owns capture/CRUD, AskService owns question→answer. It runs the pure pipeline and owns the logging side effect. app.py now talks to it instead of reaching through `service.storage` (which violated the M1.3 rule).
- `storage.log_ask_event()` never raises (same contract as `log_search`) — logging must not break the ask.
- Latencies live in the table, not just log files: the purpose is analytical (SQL aggregation — e.g. the bge-large speed question), not operational debugging.
- Test-first: the round-trip test in `tests/test_storage.py` was written before implementation and defined the API (plain kwargs — storage doesn't import RAG types).

**Why instrumentation first:** every real question asked from now on becomes eval data; shakedown queries land in the dataset instead of evaporating. Same principle as M1.4 voice auto-save — make the data safe before anything else.

**Trade-offs:**
- ✅ Real-usage eval dataset builds itself during the usage period
- ✅ Per-stage latency + per-model provenance = answerable quality/speed questions later
- ❌ One more service class; two peer services share the Storage dependency (normal)

**When to reconsider:** If a third service appears, check whether shared orchestration concerns (provider chains, logging) deserve a common helper. Parking lot: 👍/👎 rating on answers → ground truth for generation evals.

---

### 2026-07-24: Ask page — echo the asked query above the result

**What I decided:** Added a "You asked: ..." caption above the Ask page result (`src/app.py:577`, `581-584`). Query is stashed in `st.session_state.ask_query` on submit; caption renders once above the fallback/browse/answer branching so it covers all three without duplication.

**Why:** The text input clears itself after submit (widget-key bump), so the query was no longer visible anywhere once the answer showed — easy to lose track of what was asked.

**Trade-offs:**
- ✅ No schema, pipeline, or `AskResult` changes — just a session_state addition and one render line
- ❌ Resets on page refresh, same as `ask_result` already does

---

### 2026-07-27: Doc restructure — versioned plan files + two-track homes

**What I decided:**
- `plan.md` is **always the current version's operating doc** (build track): Current Focus + This Week + weekly check-in log + rules + parking lot. When a version ships, snapshot it to `plan-vN.md` and roll `plan.md` into the next version. The name `plan.md` always means "now" — so `workflow.md`'s references never break.
- v1 (MVP, M1–M4) archived frozen as `plan-v1.md`.
- `roadmap.md` = direction across all versions. `learning.md` + `docs/learning/` = the eval/learning track (separate, permanent, version-independent). Retired M-numbering for future work — "M5" was a transient mislabel for deployment, which is a roadmap research thread, not a milestone.
- Locked the **v2 thesis** as the current focus: *"Do the notes I save compound over time into a valuable knowledge base on a topic, or just pile up?"* — evidence-based (needs weeks of usage), not a feature checkbox.

**Why:**
- `plan.md` had become unmanageable: two mental models fighting (MVP milestones M1–M5 vs. the versioned-product framing from the 2026-07-20 vision session), a stale "This Week", and a phantom "M5" never defined. Root cause: the vision session reframed the project from "MVP that finishes" to "versioned product + ongoing research", but plan.md stayed in the old frame.
- Keeping the *current* doc named `plan.md` (not `plan-v2.md`) means zero relearning and no edits to `workflow.md`.
- The eval track already had a permanent home (`learning.md` + `docs/learning/`); it was never build-plan content, so versioned plan files don't orphan it.

**What I tried first:** cycled through `now.md`+`log.md` (clean-desk split), a single `plan-v2.md`, and a separate check-in log — each stumbled on a different doc having a different lifecycle. Resolved once it was clear the eval track is version-independent and already homed, leaving only the build plan to restructure.

**Trade-offs:**
- ✅ Current work is always `plan.md`; finished versions archive cleanly with a suffix; `workflow.md` untouched
- ✅ Each doc has one lifecycle: plan.md (current build), plan-vN.md (frozen), roadmap.md (direction), learning.md (eval track)
- ❌ Rules + parking lot get copied forward at each version boundary (rare, ~monthly)

**When to reconsider:** If the version-boundary copy-forward becomes annoying, or if a doc starts serving two lifecycles again.

---

### 2026-07-28: Tags minimal capture — st.multiselect over streamlit-tags

**What I decided:** Use native `st.multiselect(accept_new_options=True)` for tag input (see `docs/design/tags-minimal-capture.md`), not the third-party `streamlit-tags` package.

**Why:**
- Zero new dependency — Streamlit 1.51.0 already supports free-text additions to multiselect
- Gives pills + × removal + autocomplete against existing tags natively

**What I tried first:** Didn't evaluate `streamlit-tags` in depth — parked instead of spending time confirming its delimiter behavior (space vs. Enter/comma) since `st.multiselect` already covered every requirement.

**When to reconsider:** If the `st.multiselect` tag UX feels wrong once actually used (e.g. autocomplete or pill interaction is clunky on mobile) — check `streamlit-tags` then.

---

### 2026-07-29: Tags minimal capture — build deltas from spec

**What I decided:** Distinct tags live in their own `tags` table (mirrors `categories`), not derived from `entries.tags` on read — cheaper than scanning/deduping every entry on each Streamlit rerun. Tags are case-sensitive, not case-folded (reverses the spec doc's original line — updated there too). Tag editing added to `edit_note_dialog`, beyond the spec's original touchpoints. Full detail in `docs/design/tags-minimal-capture.md`.

**Why:** Case-folding would be a silent auto-merge; tag rename/merge is already deferred to a future session — better to keep merging a deliberate later action than an automatic one now.

---

### 2026-07-31: [UI refactor] Separate ui/ from src/ at project root

**What I decided:** All Streamlit code lives in `ui/` at the project root; `src/` is pure Python with zero Streamlit imports.

**Why:** Mid-refactor we noticed `src/` was mixing business logic with Streamlit-specific code. Keeping them as siblings makes the boundary obvious — `src/` is independently testable without Streamlit installed.

**Delta from spec:** Spec said `src/ui/components.py` and `src/pages/`. We went one level up: `ui/` at the root, `src/` stays clean.

**When to reconsider:** If we migrate away from Streamlit — `ui/` becomes the swap-out layer.


**Known gap:** Tags that predate the `tags` table (e.g. Journal's hardcoded `["interstitial", "journal"]`) aren't reachable in that entry's edit dialog until reused elsewhere on a new save — no backfill migration built this round.

---

### 2026-08-07: Pre-commit hook — ruff lint only, no ruff-format yet

**What I decided:** Added `.pre-commit-config.yaml` running `ruff check --fix` on commit (`pre-commit` as a new dev dependency, hook installed via `pre-commit install`). Left `ruff-format` out for now, and did not add `pytest` to the hook.

**Why:**
- Triggered by a CI lint failure caused by an unused import that should've been caught before commit
- `ruff-format` has never been run on this repo — a first pass reformatted 34 files (~900 lines) with no functional change, which is too noisy to fold into an unrelated change
- `pytest` in a pre-commit hook slows down every commit; CI already runs the full suite

**Trade-offs:**
- ✅ Catches the exact class of failure (unused imports, undefined names) before it reaches CI
- ✅ Fast — lint only, no test run, no reformat
- ❌ Formatting stays inconsistent repo-wide until a dedicated formatting pass is done

**When to reconsider:** Do a one-time `ruff format .` across the repo as its own standalone commit, then add `ruff-format` back to the hook so formatting stays consistent going forward.

---

### 2026-08-12: `format_note()` extracted — generation prompt and eval context now share one formatter

**What I decided:** Added `format_note(note) -> str` to `src/rag/generator.py`, returning `"{date} | {category} | {content_type}\n{content}"`. `_format_notes()` (prompt building) now calls it per note instead of inlining the formatting; `experiments/ask_eval/collector.py` now captures `created_at`/`category`/`content_type` alongside `id`/`content` in `retrieved_contexts`; `experiments/ask_eval/grader.py` builds its RAGAS context strings via the same `format_note()` instead of raw note content.

**Why:** eval's `retrieved_contexts` only ever carried `id` + `content`, so the RAGAS faithfulness judge was checking date claims in generated answers (e.g. "On July 28...") against context text that never had a date in it — even though the generator legitimately saw the date, since `_format_notes()` includes it in the actual prompt. Two separate implementations of "what does the model see for a note" had drifted apart. One shared formatter removes the drift risk, not just this one instance of it.

**Also decided in the same pass:**
- `_NOTE_TRUNCATE` (400-char per-note cap in the prompt) removed — see `docs/bugs.md` (OPEN) for the reasoning and revisit plan.
- `format_note()` includes time, not just date (`created_at[:16]` → `"2026-07-28T14:32"`), since same-day notes need to be distinguishable.
- Date/time is still extracted via fixed-width string slicing, same as before — flagged as OPEN in `docs/bugs.md` rather than fixed now, to keep this change scoped to the drift fix.

**Verified:** faithfulness average went from ~0.73 to 1.0 on a fresh run. More directly — same question ("most important wins from last month"), the judge's own reasoning flipped from *"context does not specify a timeline of July 2026"* (verdict 0) to *"context explicitly states the user exercised and ate healthy on July 28"* (verdict 1), confirming the missing-date context was the cause, not something else.

---

### 2026-08-24: Query analyzer — time_filter only on exact calendar-window match, not guessed buckets

**What I decided:** `src/rag/analyzer.py`'s query-analyzer prompt now only sets `time_filter` when the query names one of the three exact windows ("today" / "this week" / "this month"). Vague relative time language ("a couple days ago", "last Sunday", "a few weeks ago", "lately", "on Sundays") stays `null`. Final prompt addition is one line: `"Only set time_filter on an exact match: \"today\", \"this week\", \"this month\". Otherwise null."`

**Why:**
- `time_filter` is a hard filter downstream (Chroma/SQLite), not a hint — a wrong bucket can exclude the correct note entirely, not just mislabel a metric. E.g. a note 10 days old wrongly force-fit into `this_week` would never come back for that query.
- The dataset2 intent eval (`dataset2_intent_baseline.yaml`) showed 16/56 mismatches, most of them vague-time queries the model was guessing a bucket for — the prompt had no rule telling it not to.

**What I tried first:** Considered a richer time schema (actual date ranges instead of 3 fixed buckets) so vague-but-computable phrases like "a few weeks ago" could be represented precisely instead of discarded. Parked as the "detailed version" — needs schema changes across analyzer → retrieval → storage, plus regenerating eval gold labels. This exact-match fix addresses the actual failures without that scope.

**Trade-offs:**
- ✅ `time_filter` accuracy: 0.875 → 0.964 on the dataset2 intent eval (run `dataset2_intent_20260824-185808` vs. `dataset2_intent_20260824-120557`), measured against a fuller draft of this rule (explicit rule + 3 few-shot examples)
- ✅ `category_filter` accuracy: 0.893 → 0.929 in that same run (incidental — this change didn't touch category logic)
- ❌ `intent` accuracy: 0.911 → 0.839 in that same run — same failure categories as before (qa↔factual, qa↔pattern, qa↔browse boundary cases), just more of them. The time-filter section doesn't touch intent-classification rules, so this reads as run-to-run LLM variance on already-ambiguous boundary queries rather than a regression, but it isn't confirmed.
- ⚠️ The prompt was then trimmed from that fuller draft down to the one-liner above (rationale + examples were unnecessary weight for a 2-line change) — **not re-verified against the eval**, so the 0.964/0.929/0.839 numbers above are for the fuller draft, not the shipped one-liner. Skipped consciously: low-risk wording trim, re-run deferred to whenever the intent-accuracy question below is chased down anyway.
- ❌ Vague-but-genuinely-time-scoped queries ("a few weeks ago") still get no time signal at all — retrieval falls back entirely to semantic similarity, which struggles to disambiguate near-duplicate notes (e.g. the three near-identical "Sunday evening dread" journal entries in dataset2). This is exactly what the parked richer schema would fix.

**When to reconsider:** If near-duplicate note disambiguation becomes a real recurring failure in practice, revisit the richer date-range schema. Also worth an intent-eval re-run — both to confirm whether the intent-accuracy dip is noise or real, and to verify the trimmed one-liner still gets the same `time_filter` improvement as the fuller draft it replaced.

---

### 2026-08-27: Tag search implementation — json_each match, unified click+type entry point, native Chroma ids restriction

**What I decided:** Implemented `docs/design/tag-search.md`. Three follow-on calls made during the build, beyond what the spec locked:
- Clicking a tag chip and typing `#tag` in the search box both go through one parser (`src/tags.extract_tag_filter`, pure + tested) instead of two separate code paths — a chip click just pre-fills `#tag` into the search box and jumps to Search.
- Combining a tag filter with a free-text query: first tried widening the Chroma candidate pool to a fixed constant (`TAG_FILTER_CANDIDATE_POOL = 10000`) before post-filtering by tag in Python. Replaced it after review — ChromaDB's `collection.query()` accepts an `ids=` parameter (confirmed by checking the installed `chromadb==1.2.1` signature and testing against real data), so SQLite resolves the exact tag match first (`get_entry_ids_by_tag`, `json_each`) and Chroma ranks semantically *within* that exact candidate set. No overfetch, no post-filter step, no magic number.
- Tag click was originally a real `st.button` per tag in `st.columns(len(tags))` — looked huge because columns stretch each button to fill an equal-width slot. Replaced with `st.pills` (self-sizing, small, rounded — matches the old inert-pill look, same widget family as the existing `segmented_control` filters).

**Why:** the `ids=` restriction is strictly better than the overfetch-pool approach — correct at any scale (cost scales with actual tag membership, not a guessed constant), no post-filter step, no number to re-tune as the note count grows. Confirmed via direct testing against the real Chroma collection before committing to it, including composing with the existing `content_type`/date `where` filters.

**What I tried first:** the `TAG_FILTER_CANDIDATE_POOL` overfetch-then-filter approach above — worked correctly but felt like a band-aid (flagged as such before landing on the `ids=` fix); storing tags as Chroma metadata directly (so `where` could filter natively) was considered and rejected for this task — Chroma metadata values are scalar, tags are open-ended lists, and it would touch `save()`/`update()`/`reindex_all()`, out of scope for a spec explicitly limited to the SQLite `json_each()` path.

**Bug found during build:** `st.pills`'s click handler caused an infinite rerun loop — see `docs/bugs.md` ("Tag chip click — infinite rerun loop") for the mechanism and fix (clearing the widget's session_state key right after acting on a click, to make it genuinely one-shot).

**Trade-offs:**
- ✅ Exact match, no schema migration to `entries` (per spec), `search_log` gained a `tag` column with a migration script
- ✅ Cost scales with real tag membership, not a fixed pool size
- ❌ Case-sensitive tag matching (`#Python` ≠ `#python`) — consciously left as-is, matches existing `normalize_tag()` behavior elsewhere in the app, not revisited this round
- ❌ Multi-tag AND filtering still deferred (per spec's own parking lot) — single-tag only

**When to reconsider:** If tag search is used often enough that multi-tag AND filtering becomes a real ask, or if case-sensitivity causes real friction (e.g. typing `#Python` for a note tagged `python` and getting a false "no such tag" message).

---

### 2026-08-31: Demo seed store — synthetic sample data, opt-in via env var

**What I decided:** `scripts/seed_demo.py` builds a self-contained demo store (`data/demo/`, gitignored) from a synthetic fixture. `get_storage()` uses it only when both `SECOND_BRAIN_DB` and `SECOND_BRAIN_CHROMA` are set — default launch unchanged.

**Why:** README screenshots and a "clone and try it" path need sample data anyone can regenerate. Env-var opt-in avoids a demo-mode flag or auto-seed-on-empty, which would hand a new user fake notes to delete. Backdating happens in the script (`UPDATE created_at` + `reindex_all()`) rather than adding a `created_at` param to `Storage.save()` — no core change for a fixture-only need. Categories come from the fixture, so the build is deterministic and needs no API key.

**Trade-offs:**
- ✅ Zero change to `src/`; small opt-in branch in `ui/services.py`; safe to re-run
- ❌ All rows seed as text — voice cards need an audio file the demo doesn't have

**Full design:** [`design/demo-seed-store.md`](design/demo-seed-store.md)

---

### 2026-09-01: Demo corpus — curated fixture, not the eval set

**What I decided:** `seed_demo.py` reads `scripts/fixtures/demo_notes.jsonl` (39 notes: 18 carried over from the eval set, 21 new short practical ones). Eval fixture untouched.

**Why:** The eval set is built for retrieval eval, not for a demo. Its deliberate near-duplicate hard negatives make Ask look broken when they land in one citation list, and its long rambling notes don't read well as sample data. A separate fixture also means demo content can be hand-edited without shifting eval numbers.

**Trade-offs:**
- ✅ Eval numbers untouched; demo corpus readable and editable as one file
- ❌ The 18 carried-over notes are duplicated across two fixtures, and demo notes retrieve well by construction

**When to reconsider:** If v2 topics/tags need demo notes that carry tags.

---

### 2026-09-01: README demo — two GIFs plus collapsed stills

**What I decided:** Demo section directly under the intro: `demo-capture.gif` (11.3s) then `demo-ask.gif` (13.1s), with two Ask screenshots collapsed in `<details>`. 2.1 MB total in `docs/assets/`.

**Why:** An autoplaying GIF needs zero clicks; a linked screen recording doesn't get watched in a 2-minute skim. Two clips cover capture, auto-categorization and grounded retrieval. Text capture plus voice Ask shows both input modes, and the note captured in clip 1 comes back as a cited source in clip 2.

**Trade-offs:**
- ✅ 2.1 MB, loads instantly, ffmpeg-only toolchain
- ❌ Re-shoot needed whenever the UI changes; the 2.8× speedup hides real LLM latency

**When to reconsider:** After v2 topics/tags land, since the nav and note cards will change.
