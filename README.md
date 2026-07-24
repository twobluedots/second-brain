# Second Brain

**Second Brain** is a personal knowledge capture app — dump text, voice, or image notes with zero friction, and it auto-categorizes and organizes them for you. Built for fast, low-friction capture (originally motivated by ADHD-style note-taking), with semantic search and a weekly "mirror" summary to reflect back what you've been thinking about.

## What works now

- **Capture** — text, voice (Whisper transcription), and image (OCR) notes
- **Auto-categorize** — every note gets tagged on save (`task`, `mood`, `journal`, `learning`, `reference`, `insight`, `achievement`), with a provider chain (OpenAI → Anthropic → Ollama) and manual override
- **Search** — semantic search over all notes (ChromaDB), with date and type filters
- **Browse** — recents view and per-category browsing
- **Mirror** — weekly summary: note counts, category breakdown, streaks
- **Ask** — ask questions over your notes and get a generated answer (retrieval + LLM)

## Setup

```bash
uv sync
cp .env.example .env   # fill in your API keys
uv run streamlit run src/app.py
```

## Tests

```bash
uv run pytest
```

## Status

Actively evolving personal project, in daily use — not a polished public product.
