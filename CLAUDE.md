# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Second Brain is a personal knowledge capture system designed for ADHD brains. It provides zero-friction input for text, voice, and image notes with automatic organization and intelligent search. The project follows a "dump and mirror" philosophy - capture everything without friction, then the app reflects back what you've been thinking.

## Development Commands

### Running the Application
```bash
streamlit run ui/app.py
```

### Dependencies Management  
This project uses `uv` for dependency management:
```bash
uv sync                    # Install/update dependencies
uv add <package>          # Add new dependency
uv run streamlit run ui/app.py  # Run with uv
```

### Testing
Currently no formal test framework is configured. The project is in MVP phase with manual testing through the Streamlit interface.

## Architecture

### Current State (M2 in progress)

```
ui/                     — all Streamlit code; no business logic
  app.py                — navigation entrypoint (st.navigation + shared session init)
  services.py           — st.cache_resource wrappers; single Storage instance shared across services
  components.py         — render_entry_card(), dialogs, shared UI helpers
  pages/                — one file per page (capture, ask, search, recents, categories, journal, mirror)

src/                    — pure Python; zero Streamlit imports
  notes_service.py      — orchestration: categorize, save, log events
  storage/storage.py    — SQLite + ChromaDB, no business logic
  categorize.py         — LLM auto-tagging (OpenAI → Anthropic → Ollama → fallback); lru_cache(256)
  processing.py         — Whisper transcription; returns (text, whisper_ms)
  utils.py              — shared date/time helpers (time_filter_to_ts, time_filter_to_iso)
  models/entry.py       — Entry Pydantic model — contract between service and storage
  rag/                  — Ask pipeline (retrieval + generation)
```

- **ui/services.py**: `get_storage()`, `get_note_service()`, `get_ask_service()`, `get_whisper_model()` — `get_ask_service().storage is get_note_service().storage` guaranteed
- **src/notes_service.py**: `NoteService` — `save_note()` calls categorize, storage, and event log; `search()` resolves `date_preset` internally
- **src/storage/storage.py**: `Storage` — SQLite + ChromaDB, no business logic
- **entries/**: Audio/image files on disk; SQLite stores the `file_path`

### Storage Design
- **SQLite**: Source of truth — `entries` table + `category_events` audit log
- **ChromaDB**: Persistent vector store for semantic search (`./chroma_data`)
- **File System**: Audio/image files in `entries/`, path stored in SQLite

### Data Flow
1. **Input**: Text, voice (via Whisper), or image (via camera/upload)
2. **Processing**: Voice → `processing.py` Whisper transcription before save
3. **Save**: `app.py` → `NoteService.save_note()` → `categorize()` → `storage.save()` → `storage.log_category_event()`
4. **Retrieval**: Recent (SQLite), Search (ChromaDB), Categories (SQLite)

## Key Technologies

- **Streamlit**: Web interface
- **SQLite**: Primary database
- **ChromaDB**: Vector database for semantic search
- **OpenAI Whisper**: Voice transcription
- **OpenAI API / Anthropic / Ollama**: Auto-categorization (provider chain)

## Development Notes

### File Conventions
- Entry IDs: UUID (e.g. `a3f2c1d0-...`)
- Audio files: `.wav` format in `entries/`
- Images: `.jpg` format in `entries/`
- Categories: 7 intent-based — `task`, `mood`, `journal`, `learning`, `reference`, `insight`, `achievement` (defined in `config.py`)

### Mobile Usage
The app is designed for mobile-first capture via ngrok tunneling for remote access.

## Project Milestones

Currently in **M2: Auto-Categorize** — M2.0 through M2.3 complete. See `docs/plan.md` for full breakdown.

Next:
- **M2.4**: Category override option
- **M3**: Organized views and weekly summaries
- **M4**: Daily usage and GitHub deployment