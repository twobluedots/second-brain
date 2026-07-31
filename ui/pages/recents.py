import streamlit as st

from ui.components import edit_note_dialog, render_entry_card
from ui.services import get_note_service

if st.session_state.get("_edit_target"):
    edit_note_dialog(**st.session_state["_edit_target"])

st.title("📋 Recents")

try:
    recent_entries = get_note_service().get_recent(10)
except Exception as e:
    st.error(f"Couldn't load recent notes: {e}")
    recent_entries = []

for entry in recent_entries:
    render_entry_card(entry, key_prefix="edit_rec")
