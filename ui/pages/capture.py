import streamlit as st

from ui.components import (
    add_image_dialog,
    add_text_dialog,
    add_voice_dialog,
    edit_note_dialog,
    render_entry_card,
)

if st.session_state.get("_edit_target"):
    edit_note_dialog(**st.session_state["_edit_target"])

st.title("📥 Capture")

if st.button("Add Voice", width="stretch"):
    add_voice_dialog()
if st.button("Add Image", width="stretch"):
    add_image_dialog()
if st.button("Add Text", width="stretch"):
    add_text_dialog()

for entry in st.session_state.entries:
    render_entry_card(entry, key_prefix="edit_cap")
