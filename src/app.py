import streamlit as st
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.logger import logger
from src.notes_service import NoteService
from src.storage.storage import Storage
from src.processing import load_model, process_voice_note
from config import DEFAULT_CATEGORIES, CATEGORY_MIRROR_LINES

os.makedirs("entries", exist_ok=True)


@st.cache_resource
def get_service() -> NoteService:
    return NoteService(Storage())


@st.cache_resource
def get_whisper_model():
    return load_model("base")


try:
    service = get_service()
except Exception as _service_init_error:
    logger.error("Service init failed: %s", _service_init_error)
    st.error(f"Failed to initialise storage: {_service_init_error}")
    st.info("Check that the data/ directory is writable and the database file is not corrupted.")
    st.stop()

CATEGORY_COLOR = {
    "task":        ("rgba(30,136,229,0.12)",  "#1565C0"),
    "mood":        ("rgba(233,30,99,0.12)",   "#AD1457"),
    "journal":     ("rgba(67,160,71,0.12)",   "#2E7D32"),
    "learning":    ("rgba(142,36,170,0.12)",  "#6A1B9A"),
    "reference":   ("rgba(251,140,0,0.12)",   "#E65100"),
    "insight":     ("rgba(0,172,193,0.12)",   "#006064"),
    "achievement": ("rgba(249,168,37,0.12)",  "#F57F17"),
}


def format_relative_time(created_at: str) -> str:
    if not created_at:
        return ""
    try:
        ts = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta = now - ts
        if delta.days == 0:
            return f"Today {ts.strftime('%H:%M')}"
        elif delta.days == 1:
            return f"Yesterday {ts.strftime('%H:%M')}"
        elif delta.days < 7:
            return ts.strftime("%a %H:%M")
        else:
            return ts.strftime("%b %d %H:%M")
    except Exception:
        return created_at[:10]


def render_entry_card(entry: dict, key_prefix: str, show_category: bool = True):
    category = entry.get("category", "")
    bg, fg = CATEGORY_COLOR.get(category, ("rgba(0,0,0,0.08)", "#555555"))
    with st.container(border=True):
        if entry["content_type"] == "voice":
            st.audio(entry["file_path"])
            if entry.get("description"):
                st.write(entry["description"])
            if entry.get("content"):
                st.caption(f"Transcription: {entry['content']}")
        elif entry["content_type"] == "image":
            st.image(entry["file_path"])
            if entry.get("content"):
                st.write(entry["content"])
        else:
            st.write(entry["content"])

        if show_category:
            col1, col2, col3 = st.columns([3, 5, 1])
            with col1:
                st.markdown(
                    f'<span style="background:{bg};color:{fg};padding:2px 10px;'
                    f'border-radius:12px;font-size:0.8em;border:1px solid {fg}40">'
                    f'{category}</span>',
                    unsafe_allow_html=True,
                )
            with col2:
                st.caption(format_relative_time(entry.get("created_at", "")))
            with col3:
                if st.button("✏️", key=f"{key_prefix}_{entry['id']}"):
                    edit_note_dialog(entry["id"], category or "journal", entry.get("content", ""))
        else:
            col_time, col_edit = st.columns([8, 1])
            with col_time:
                st.caption(format_relative_time(entry.get("created_at", "")))
            with col_edit:
                if st.button("✏️", key=f"{key_prefix}_{entry['id']}"):
                    edit_note_dialog(entry["id"], category or "journal", entry.get("content", ""))

page = st.sidebar.radio("Navigation", ["Capture", "Search", "Recents", "Categories", "Journal", "Mirror"], label_visibility="collapsed")


def save_file(file_obj, name: str) -> str:
    file_ext = Path(file_obj.name).suffix
    file_path = f"entries/{name}{file_ext}"
    with open(file_path, "wb") as f:
        f.write(file_obj.getbuffer())
    return file_path


@st.dialog("🎙️ Add Voice Note")
def add_voice_dialog():
    st.write("Record or upload a voice message:")
    audio = st.audio_input("Voice input")

    # Clear stale draft if dialog was dismissed without saving
    if not audio:
        st.session_state.pop("voice_draft_path", None)

    # Auto-save file to disk as soon as recording finishes, before user hits Save
    if audio and "voice_draft_path" not in st.session_state:
        try:
            st.session_state.voice_draft_path = save_file(audio, str(uuid.uuid4()))
        except Exception as e:
            st.error(f"Couldn't write audio file: {e}")

    context = st.text_input("Optional context", placeholder="This audio is about...")
    if st.button("Save"):
        if audio:
            try:
                file_path = st.session_state.get("voice_draft_path") or save_file(audio, str(uuid.uuid4()))
                with st.spinner("Transcribing..."):
                    transcription = process_voice_note(file_path, get_whisper_model())
                content = transcription or context or ""
                description = context if transcription else None
                with st.spinner("Saving..."):
                    entry_id, category = service.save_note(
                        content=content,
                        content_type="voice",
                        file_path=file_path,
                        description=description,
                    )
                st.session_state.pop("voice_draft_path", None)
                st.session_state.entries.append({"type": "voice", "audio": audio, "content": transcription or context, "category": category, "id": entry_id})
                st.rerun()
            except Exception as e:
                if st.session_state.get("voice_draft_path"):
                    st.error(f"Couldn't save — audio file is safe on disk. Error: {e}")
                else:
                    st.error(f"Couldn't save — please try recording again. Error: {e}")
        else:
            st.error("Please record or upload audio first.")


@st.dialog("📷 Add Image Note")
def add_image_dialog():
    st.write("Record or upload an image:")
    image = st.camera_input("Take photo")
    content = st.text_input("Optional context", placeholder="This image is about...")
    if st.button("Save"):
        if image:
            try:
                file_path = save_file(image, str(uuid.uuid4()))
                with st.spinner("Saving..."):
                    entry_id, category = service.save_note(content=content, content_type="image", file_path=file_path)
                st.session_state.entries.append({"type": "image", "image": image, "content": content, "category": category, "id": entry_id})
                st.rerun()
            except Exception as e:
                st.error(f"Couldn't save — please try again. Error: {e}")
        else:
            st.error("Please take or upload a photo first.")


@st.dialog("✏️ Add Text Note")
def add_text_dialog():
    st.write("What are you thinking?")
    text = st.text_area("Enter text", placeholder="I think that...")
    if st.button("Save"):
        if text:
            try:
                with st.spinner("Saving..."):
                    entry_id, category = service.save_note(content=text, content_type="text")
                st.session_state.entries.append({"type": "text", "content": text, "category": category, "id": entry_id})
                st.rerun()
            except Exception as e:
                st.error(f"Couldn't save — please try again. Error: {e}")
        else:
            st.error("Text cannot be empty.")


@st.dialog("Edit Note")
def edit_note_dialog(entry_id: str, current_category: str, current_content: str):
    new_content = st.text_area("Content", value=current_content)
    cats = service.get_categories()
    idx = cats.index(current_category) if current_category in cats else 0
    new_cat = st.selectbox("Category", cats, index=idx)
    if st.button("Save", use_container_width=True, type="secondary"):
        if new_content != current_content:
            service.update_note(entry_id, new_content)
            for e in st.session_state.get("entries", []):
                if e.get("id") == entry_id:
                    e["content"] = new_content
                    break
        if new_cat != current_category:
            service.override_category(entry_id, new_cat)
            for e in st.session_state.get("entries", []):
                if e.get("id") == entry_id:
                    e["category"] = new_cat
                    break
        st.rerun()

    if st.button("Delete", use_container_width=True, type="primary"):
        st.session_state["_confirm_delete"] = entry_id

    if st.session_state.get("_confirm_delete") == entry_id:
        st.warning("Delete this note permanently?")
        col_yes, col_no = st.columns(2)
        with col_yes:
            if st.button("Yes, delete", use_container_width=True, type="primary"):
                service.delete_note(entry_id)
                st.session_state["entries"] = [
                    e for e in st.session_state.get("entries", []) if e.get("id") != entry_id
                ]
                st.session_state.pop("_confirm_delete", None)
                st.rerun()
        with col_no:
            if st.button("Cancel", use_container_width=True):
                st.session_state.pop("_confirm_delete", None)
                st.rerun()


if "entries" not in st.session_state:
    st.session_state.entries = []


if page == "Capture":
    st.title("📥 Capture")

    if st.button("Add Voice", width="stretch"):
        add_voice_dialog()
    if st.button("Add Image", width="stretch"):
        add_image_dialog()
    if st.button("Add Text", width="stretch"):
        add_text_dialog()

    if st.session_state.entries:
        for idx, entry in enumerate(st.session_state.entries):
            st.write(f"Note {idx + 1}:")
            if entry["type"] == "voice":
                st.audio(entry["audio"])
                st.write(entry["content"])
            elif entry["type"] == "image":
                st.image(entry["image"])
                st.write(entry["content"])
            elif entry["type"] == "text":
                st.markdown(entry["content"])
            if entry.get("category"):
                col1, col2 = st.columns([8, 1])
                with col1:
                    st.caption(f"category: {entry['category']}")
                with col2:
                    if st.button("✏️", key=f"edit_cap_{entry.get('id', idx)}"):
                        edit_note_dialog(entry["id"], entry["category"], entry.get("content", ""))

elif page == "Search":
    st.title("🔍 Search")
    query = st.text_input("What are you looking for?")

    col_date, col_type = st.columns(2)
    with col_date:
        date_preset = st.segmented_control(
            "When",
            options=["All time", "Today", "This week", "This month"],
            default="All time",
            key="search_date_preset",
        )
    with col_type:
        content_type_filter = st.segmented_control(
            "Type",
            options=["All", "Text", "Voice", "Image"],
            default="All",
            key="search_content_type",
        )

    if st.button("Search"):
        now = datetime.now(timezone.utc)
        if date_preset == "Today":
            date_from = now.replace(hour=0, minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
        elif date_preset == "This week":
            date_from = (now - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
        elif date_preset == "This month":
            date_from = (now - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            date_from = None

        content_type_val = None if content_type_filter == "All" else content_type_filter.lower()

        try:
            results = service.search(query, content_type=content_type_val, date_from=date_from)
            if results:
                for entry in results:
                    render_entry_card(entry, key_prefix="edit_search")
            else:
                st.write("No results found.")
        except Exception:
            st.error("Search is temporarily unavailable — try again later.")

elif page == "Recents":
    st.title("📋 Recents")

    try:
        recent_entries = service.get_recent(10)
    except Exception as e:
        st.error(f"Couldn't load recent notes: {e}")
        recent_entries = []

    for entry in recent_entries:
        render_entry_card(entry, key_prefix="edit_rec")

elif page == "Categories":
    if "selected_category" not in st.session_state:
        st.session_state.selected_category = None

    if st.session_state.selected_category is None:
        st.title("Categories")
        try:
            counts = service.get_category_counts()
        except Exception as e:
            st.error(f"Couldn't load category counts: {e}")
            counts = {}

        for i in range(0, len(DEFAULT_CATEGORIES), 2):
            col_a, col_b = st.columns(2)
            for col, cat in zip([col_a, col_b], DEFAULT_CATEGORIES[i:i+2]):
                bg, fg = CATEGORY_COLOR.get(cat, ("rgba(0,0,0,0.08)", "#555555"))
                count = counts.get(cat, 0)
                with col:
                    with st.container(border=True):
                        st.markdown(
                            f'<div style="background:{bg};padding:8px 12px;border-radius:6px;'
                            f'margin-bottom:6px;border:1px solid {fg}40">'
                            f'<span style="color:{fg};font-weight:600">{cat}</span></div>',
                            unsafe_allow_html=True,
                        )
                        st.markdown(f"**{count}** notes")
                        if st.button("Open →", key=f"cat_{cat}", use_container_width=True):
                            st.session_state.selected_category = cat
                            st.rerun()

    else:
        selected = st.session_state.selected_category
        bg, fg = CATEGORY_COLOR.get(selected, ("rgba(0,0,0,0.08)", "#555555"))

        col_back, col_title = st.columns([1, 5])
        with col_back:
            if st.button("← Back"):
                st.session_state.selected_category = None
                st.rerun()
        with col_title:
            st.markdown(
                f'<span style="background:{bg};color:{fg};padding:4px 14px;'
                f'border-radius:12px;font-size:1em;border:1px solid {fg}40">'
                f'{selected}</span>',
                unsafe_allow_html=True,
            )

        try:
            cat_entries = service.get_by_category(selected, limit=50)
        except Exception as e:
            st.error(f"Couldn't load entries: {e}")
            cat_entries = []

        if not cat_entries:
            st.caption("No notes in this category yet.")

        for entry in cat_entries:
            render_entry_card(entry, key_prefix="edit_cat", show_category=False)

elif page == "Journal":
    st.title("📝 Interstitial Journal")
    journal_entry = st.text_area("Write your interstitial journal entry here...", height=300)

    if st.button("Save Journal Entry"):
        if journal_entry:
            try:
                with st.spinner("Saving..."):
                    service.save_note(
                        content=journal_entry,
                        content_type="text",
                        category="journal",
                        tags=["interstitial", "journal"],
                    )
                st.success("Saved as: journal")
                st.rerun()
            except Exception as e:
                st.error(f"Couldn't save journal entry — please try again. Error: {e}")
        else:
            st.error("Journal entry cannot be empty.")

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat().replace("+00:00", "") + "Z"
    today_end = datetime.now(timezone.utc).replace(hour=23, minute=59, second=59, microsecond=0).isoformat().replace("+00:00", "") + "Z"

    try:
        journal_entries = service.get_by_date_range(today_start, today_end)
    except Exception as e:
        st.error(f"Couldn't load today's entries: {e}")
        journal_entries = []
    for entry in journal_entries:
        if entry.get("category") == "journal":
            time_str = datetime.fromisoformat(entry["created_at"].replace("Z", "+00:00")).strftime("%H:%M")
            st.markdown(f"**{time_str}** — {entry['content']}")

elif page == "Mirror":
    st.title("Mirror")

    try:
        stats = service.get_mirror_stats()
    except Exception as e:
        st.error(f"Couldn't load stats: {e}")
        st.stop()

    # --- A: Snapshot ---
    col_week, col_total = st.columns(2)
    with col_week:
        st.metric("This week", stats["week_count"])
    with col_total:
        st.metric("Total so far", stats["total_count"])

    if stats["category_breakdown"]:
        pills_html = " · ".join(
            f'<span style="background:{CATEGORY_COLOR.get(cat, ("rgba(0,0,0,0.08)","#555"))[0]};'
            f'color:{CATEGORY_COLOR.get(cat, ("rgba(0,0,0,0.08)","#555"))[1]};'
            f'padding:2px 10px;border-radius:12px;font-size:0.85em;'
            f'border:1px solid {CATEGORY_COLOR.get(cat, ("rgba(0,0,0,0.08)","#555"))[1]}40">'
            f'{cat} ×{count}</span>'
            for cat, count in sorted(stats["category_breakdown"].items(), key=lambda x: -x[1])
        )
        st.markdown(pills_html, unsafe_allow_html=True)

    if stats["top_category"] and stats["top_category"] in CATEGORY_MIRROR_LINES:
        st.caption(CATEGORY_MIRROR_LINES[stats["top_category"]])

    st.divider()

    # --- B: Consistency ---
    now_date = datetime.now(timezone.utc).date()
    dots = "".join(
        "●" if (now_date - timedelta(days=i)) in stats["active_days"] else "○"
        for i in range(6, -1, -1)
    )
    st.markdown(f"**{dots}**")
    active_count = len(stats["active_days"])
    if active_count > 0:
        st.caption(f"You showed up {active_count} of 7 days")

    # --- D: Rediscovery ---
    rediscovery = stats["rediscovery"]
    if rediscovery:
        st.divider()
        try:
            ts = datetime.fromisoformat(rediscovery["created_at"].replace("Z", "+00:00"))
            days_ago = (datetime.now(timezone.utc) - ts).days
            label = f"{days_ago} days ago you wrote:"
        except Exception:
            label = "From the past:"
        text = rediscovery.get("content") or rediscovery.get("description", "")
        st.info(f"*{label}*\n\n{text}")
