import uuid
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

from src.logger import logger
from src.processing import process_voice_note
from ui.services import get_note_service, get_whisper_model

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


def save_file(file_obj, name: str) -> str:
    file_ext = Path(file_obj.name).suffix
    file_path = f"entries/{name}{file_ext}"
    with open(file_path, "wb") as f:
        f.write(file_obj.getbuffer())
    return file_path


def _edit_button(entry: dict, key_prefix: str):
    if st.button("✏️", key=f"{key_prefix}_{entry['id']}"):
        st.session_state["_edit_target"] = {
            "entry_id": entry["id"],
            "current_category": entry.get("category") or "journal",
            "current_content": entry.get("content", ""),
            "current_tags": entry.get("tags") or [],
        }


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
                _edit_button(entry, key_prefix)
        else:
            col_time, col_edit = st.columns([8, 1])
            with col_time:
                st.caption(format_relative_time(entry.get("created_at", "")))
            with col_edit:
                _edit_button(entry, key_prefix)

        tags = entry.get("tags")
        if tags:
            pills_key = f"{key_prefix}_{entry['id']}_tags"
            clicked = st.pills(
                "tags",
                options=tags,
                format_func=lambda t: f"#{t}",
                selection_mode="single",
                default=None,
                key=pills_key,
                label_visibility="collapsed",
            )
            if clicked:
                # st.pills is sticky — its selection persists in session_state across
                # reruns. Since the clicked entry's own tag guarantees it reappears in
                # its own filtered results, an un-reset selection re-fires this block
                # on every rerun with no new click, looping switch_page forever.
                # Clearing it here makes the click genuinely one-shot.
                del st.session_state[pills_key]
                st.session_state["prefill_search_query"] = f"#{clicked}"
                st.session_state["search_params"] = {"query": "", "content_type": None, "date_preset": "All time", "tag": clicked}
                st.session_state["search_log_pending"] = True
                st.switch_page("pages/search.py")


@st.dialog("🎙️ Add Voice Note")
def add_voice_dialog():
    service = get_note_service()
    st.write("Record or upload a voice message:")
    audio = st.audio_input("Voice input")

    if not audio:
        st.session_state.pop("voice_draft_path", None)

    if audio and "voice_draft_path" not in st.session_state:
        try:
            st.session_state.voice_draft_path = save_file(audio, str(uuid.uuid4()))
        except Exception as e:
            st.error(f"Couldn't write audio file: {e}")

    context = st.text_input("Optional context", placeholder="This audio is about...")
    tags = st.multiselect("Tags", options=service.get_all_tags(), accept_new_options=True, default=[])
    if st.button("Save"):
        if audio:
            try:
                file_path = st.session_state.get("voice_draft_path") or save_file(audio, str(uuid.uuid4()))
                with st.spinner("Transcribing..."):
                    transcription, whisper_ms = process_voice_note(file_path, get_whisper_model())
                    logger.info("Whisper transcription: %d ms", whisper_ms)
                content = transcription or context or ""
                description = context if transcription else None
                with st.spinner("Saving..."):
                    entry_id, category, saved_tags = service.save_note(
                        content=content,
                        content_type="voice",
                        file_path=file_path,
                        description=description,
                        tags=tags,
                    )
                st.session_state.pop("voice_draft_path", None)
                st.session_state.entries.append({
                    "content_type": "voice",
                    "file_path": file_path,
                    "content": content,
                    "description": description,
                    "category": category,
                    "id": entry_id,
                    "tags": saved_tags,
                    "created_at": None,
                })
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
    service = get_note_service()
    st.write("Record or upload an image:")
    image = st.camera_input("Take photo")
    content = st.text_input("Optional context", placeholder="This image is about...")
    tags = st.multiselect("Tags", options=service.get_all_tags(), accept_new_options=True, default=[])
    if st.button("Save"):
        if image:
            try:
                file_path = save_file(image, str(uuid.uuid4()))
                with st.spinner("Saving..."):
                    entry_id, category, saved_tags = service.save_note(
                        content=content, content_type="image", file_path=file_path, tags=tags
                    )
                st.session_state.entries.append({
                    "content_type": "image",
                    "file_path": file_path,
                    "content": content,
                    "category": category,
                    "id": entry_id,
                    "tags": saved_tags,
                    "created_at": None,
                })
                st.rerun()
            except Exception as e:
                st.error(f"Couldn't save — please try again. Error: {e}")
        else:
            st.error("Please take or upload a photo first.")


@st.dialog("✏️ Add Text Note")
def add_text_dialog():
    service = get_note_service()
    st.write("What are you thinking?")
    text = st.text_area("Enter text", placeholder="I think that...")
    tags = st.multiselect("Tags", options=service.get_all_tags(), accept_new_options=True, default=[])
    if st.button("Save"):
        if text:
            try:
                with st.spinner("Saving..."):
                    entry_id, category, saved_tags = service.save_note(
                        content=text, content_type="text", tags=tags
                    )
                st.session_state.entries.append({
                    "content_type": "text",
                    "content": text,
                    "category": category,
                    "id": entry_id,
                    "tags": saved_tags,
                    "created_at": None,
                })
                st.rerun()
            except Exception as e:
                st.error(f"Couldn't save — please try again. Error: {e}")
        else:
            st.error("Text cannot be empty.")


def _clear_edit_target():
    st.session_state.pop("_edit_target", None)
    st.session_state.pop("_confirm_delete", None)


@st.dialog("Edit Note", on_dismiss=_clear_edit_target)
def edit_note_dialog(entry_id: str, current_category: str, current_content: str, current_tags: list = None):
    service = get_note_service()
    current_tags = current_tags or []
    new_content = st.text_area("Content", value=current_content)
    cats = service.get_categories()
    idx = cats.index(current_category) if current_category in cats else 0
    new_cat = st.selectbox("Category", cats, index=idx)
    new_tags = st.multiselect("Tags", options=service.get_all_tags(), default=current_tags, accept_new_options=True)
    if st.button("Save", use_container_width=True, type="secondary"):
        ask_result = st.session_state.get("ask_result")
        if new_content != current_content:
            service.update_note(entry_id, new_content)
            for e in st.session_state.get("entries", []):
                if e.get("id") == entry_id:
                    e["content"] = new_content
                    break
            if ask_result is not None:
                for n in ask_result.notes:
                    if n.get("id") == entry_id:
                        n["content"] = new_content
                        break
        if new_cat != current_category:
            service.override_category(entry_id, new_cat)
            for e in st.session_state.get("entries", []):
                if e.get("id") == entry_id:
                    e["category"] = new_cat
                    break
            if ask_result is not None:
                for n in ask_result.notes:
                    if n.get("id") == entry_id:
                        n["category"] = new_cat
                        break
        if new_tags != current_tags:
            saved_tags = service.update_tags(entry_id, new_tags)
            for e in st.session_state.get("entries", []):
                if e.get("id") == entry_id:
                    e["tags"] = saved_tags
                    break
            if ask_result is not None:
                for n in ask_result.notes:
                    if n.get("id") == entry_id:
                        n["tags"] = saved_tags
                        break
        _clear_edit_target()
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
                ask_result = st.session_state.get("ask_result")
                if ask_result is not None:
                    ask_result.notes = [n for n in ask_result.notes if n.get("id") != entry_id]
                _clear_edit_target()
                st.rerun()
        with col_no:
            if st.button("Cancel", use_container_width=True):
                st.session_state.pop("_confirm_delete", None)
                st.rerun()
