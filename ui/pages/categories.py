import streamlit as st

from config import DEFAULT_CATEGORIES
from ui.components import CATEGORY_COLOR, edit_note_dialog, render_entry_card
from ui.services import get_note_service

if st.session_state.get("_edit_target"):
    edit_note_dialog(**st.session_state["_edit_target"])

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
