Day 1 

Inputs: 

Image input: 
- Tried two open source OCR: pytesseract and easyOCR 
- not a single word could be extracted correctly. 
- on the other side, gpt4 gives >90% accuracy
- check further this post: https://www.reddit.com/r/LLMDevs/comments/1h8ra4a/seeking_advice_for_handwritten_text_recognition/

Voice input:
- Whisper lib works well on short and english texts
- longer, turkis

## YYYY-MM-DD: [Short Decision Title]

**What I decided:** [One sentence]

**Why:** [1-3 bullets of reasoning]
- [Reason 1]
- [Reason 2]

**What I tried first:** [What didn't work]

**Trade-offs:**
- ✅ Pro: [Good thing]
- ❌ Con: [Bad thing]

**When to reconsider:** [Condition that would make you change this]

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

## 2025-10-30: Use GPT-4V Instead of Tesseract/EasyOCR

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
