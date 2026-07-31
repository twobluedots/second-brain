import streamlit as st

from ui.components import edit_note_dialog, render_entry_card
from ui.services import get_note_service

if st.session_state.get("_edit_target"):
    edit_note_dialog(**st.session_state["_edit_target"])

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
