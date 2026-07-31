import uuid
from pathlib import Path

import streamlit as st

from src.logger import logger
from src.processing import process_voice_note
from ui.components import edit_note_dialog, render_entry_card
from ui.services import get_ask_service, get_whisper_model

if st.session_state.get("_edit_target"):
    edit_note_dialog(**st.session_state["_edit_target"])

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
