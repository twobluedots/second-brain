import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import streamlit as st

from src.logger import logger
from src.processing import process_voice_note
from src.services import get_ask_service, get_note_service, get_whisper_model
from src.ui.components import (
    CATEGORY_COLOR,
    add_image_dialog,
    add_text_dialog,
    add_voice_dialog,
    edit_note_dialog,
    render_entry_card,
)
from src.utils import time_filter_to_iso
from config import DEFAULT_CATEGORIES, CATEGORY_MIRROR_LINES

os.makedirs("entries", exist_ok=True)

try:
    get_note_service()
except Exception as _service_init_error:
    logger.error("Service init failed: %s", _service_init_error)
    st.error(f"Failed to initialise storage: {_service_init_error}")
    st.info("Check that the data/ directory is writable and the database file is not corrupted.")
    st.stop()

page = st.sidebar.radio(
    "Navigation",
    ["Capture", "Ask", "Search", "Recents", "Categories", "Journal", "Mirror"],
    label_visibility="collapsed",
)

if "entries" not in st.session_state:
    st.session_state.entries = []

if st.session_state.get("_edit_target"):
    edit_note_dialog(**st.session_state["_edit_target"])


if page == "Capture":
    st.title("📥 Capture")

    if st.button("Add Voice", width="stretch"):
        add_voice_dialog()
    if st.button("Add Image", width="stretch"):
        add_image_dialog()
    if st.button("Add Text", width="stretch"):
        add_text_dialog()

    for entry in st.session_state.entries:
        render_entry_card(entry, key_prefix="edit_cap")

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

    # Button click stores search intent; rendering recomputes on every rerun so
    # edits/deletes are always reflected (no stale results cache).
    if st.button("Search"):
        st.session_state.search_params = {
            "query": query,
            "content_type": None if content_type_filter == "All" else content_type_filter.lower(),
            "date_preset": date_preset,
        }
        st.session_state.search_log_pending = True

    params = st.session_state.get("search_params")
    if params:
        try:
            results = get_note_service().search(
                params["query"],
                content_type=params["content_type"],
                date_preset=params["date_preset"],
                log_event=st.session_state.pop("search_log_pending", False),
            )
        except Exception:
            st.error("Search is temporarily unavailable — try again later.")
            results = None

        if results:
            for entry in results:
                render_entry_card(entry, key_prefix="edit_search")
        elif results is not None:
            st.write("No results found.")

elif page == "Recents":
    st.title("📋 Recents")

    try:
        recent_entries = get_note_service().get_recent(10)
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
            counts = get_note_service().get_category_counts()
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
            cat_entries = get_note_service().get_by_category(selected, limit=50)
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
                    get_note_service().save_note(
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

    today_start = time_filter_to_iso("today")
    today_end = (
        datetime.now(timezone.utc)
        .replace(hour=23, minute=59, second=59, microsecond=0)
        .isoformat()
        .replace("+00:00", "") + "Z"
    )

    try:
        journal_entries = get_note_service().get_by_date_range(today_start, today_end)
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
        stats = get_note_service().get_mirror_stats()
    except Exception as e:
        st.error(f"Couldn't load stats: {e}")
        st.stop()

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

    now_date = datetime.now(timezone.utc).date()
    dots = "".join(
        "●" if (now_date - timedelta(days=i)) in stats["active_days"] else "○"
        for i in range(6, -1, -1)
    )
    st.markdown(f"**{dots}**")
    active_count = len(stats["active_days"])
    if active_count > 0:
        st.caption(f"You showed up {active_count} of 7 days")

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

elif page == "Ask":
    st.title("Ask")

    st.session_state.setdefault("ask_form_version", 0)
    version = st.session_state.ask_form_version
    audio_key = f"ask_voice_{version}"
    text_key = f"ask_text_{version}"
    transcribed_flag = f"ask_transcribed_{version}"

    voice_query = st.audio_input("Or ask with your voice", key=audio_key)

    # Transcribe once on audio arrival so it lands in the editable text field
    # instead of silently overriding what gets submitted.
    if voice_query is not None and not st.session_state.get(transcribed_flag):
        with st.spinner("Transcribing..."):
            try:
                tmp_path = f"entries/ask_voice_{uuid.uuid4()}.wav"
                with open(tmp_path, "wb") as f:
                    f.write(voice_query.getbuffer())
                transcription, whisper_ms = process_voice_note(tmp_path, get_whisper_model())
                logger.info("Whisper transcription (ask): %d ms", whisper_ms)
                Path(tmp_path).unlink(missing_ok=True)
                st.session_state[text_key] = transcription or ""
            except Exception as e:
                logger.warning("Voice query transcription failed: %s", e)
                st.warning("Couldn't transcribe voice — type your question instead.")
        st.session_state[transcribed_flag] = True

    query_text = st.text_input("Ask anything about your notes", key=text_key)

    if st.button("Ask", type="primary"):
        query = query_text.strip()
        if not query:
            st.warning("Type or record a question first.")
        else:
            input_type = "voice" if voice_query is not None else "text"
            with st.spinner("Thinking..."):
                try:
                    result = get_ask_service().ask(query, input_type=input_type)
                except Exception as e:
                    logger.error("Ask pipeline failed: %s", e)
                    st.error("Something went wrong — please try again.")
                    st.stop()

            st.session_state.ask_query = query
            st.session_state.ask_result = result
            st.session_state.ask_form_version += 1
            st.rerun()

    result = st.session_state.get("ask_result")
    if result is not None:
        last_query = st.session_state.get("ask_query")
        if last_query:
            st.caption(f"You asked: {last_query}")

        if result.fallback and not result.notes:
            st.info("I couldn't find any relevant notes for that query.")

        elif result.intent == "browse":
            if result.fallback:
                st.info("No notes found for those filters.")
            else:
                st.caption(f"{len(result.notes)} notes found")
                for entry in result.notes:
                    render_entry_card(entry, key_prefix="ask_browse")

        else:
            if result.fallback:
                st.warning("Couldn't find a clear match — here are the closest notes I found.")

            st.markdown(result.answer)

            if result.notes:
                with st.expander(f"Sources ({len(result.notes)} notes)"):
                    for entry in result.notes:
                        render_entry_card(entry, key_prefix="ask_src")
