import streamlit as st

from src.tags import extract_tag_filter
from ui.components import edit_note_dialog, render_entry_card
from ui.services import get_note_service

if st.session_state.get("_edit_target"):
    edit_note_dialog(**st.session_state["_edit_target"])

st.title("🔍 Search")
query = st.text_input(
    "What are you looking for? (type #tag to filter by an exact tag)",
    value=st.session_state.pop("prefill_search_query", ""),
)

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
    tag, remaining_query = extract_tag_filter(query)
    st.session_state.search_params = {
        "query": remaining_query,
        "content_type": None if content_type_filter == "All" else content_type_filter.lower(),
        "date_preset": date_preset,
        "tag": tag,
    }
    st.session_state.search_log_pending = True

params = st.session_state.get("search_params")
if params:
    if params.get("tag"):
        col_filter, col_clear = st.columns([5, 1])
        with col_filter:
            st.caption(f"Filtering by #{params['tag']}")
        with col_clear:
            if st.button("✕ Clear"):
                st.session_state.search_params = {**params, "tag": None}
                st.rerun()

    try:
        results = get_note_service().search(
            params["query"],
            content_type=params["content_type"],
            date_preset=params["date_preset"],
            tag=params.get("tag"),
            log_event=st.session_state.pop("search_log_pending", False),
        )
    except Exception:
        st.error("Search is temporarily unavailable — try again later.")
        results = None

    if results:
        for entry in results:
            render_entry_card(entry, key_prefix="edit_search")
    elif results is not None:
        if params.get("tag") and params["tag"] not in get_note_service().get_all_tags():
            st.write(f"No tag \"#{params['tag']}\" exists yet — check the spelling (matching is exact and case-sensitive).")
        elif params.get("tag"):
            st.write(f"No notes tagged #{params['tag']} match the other filters.")
        else:
            st.write("No results found.")
