import os

import streamlit as st

from src.notes_service import NoteService
from src.rag.service import AskService
from src.storage.storage import Storage
from src.processing import load_model


@st.cache_resource
def get_storage() -> Storage:
    # Opt-in demo store: set BOTH env vars (as a one-command shell prefix) to
    # point the app at scripts/seed_demo.py output. Unset → normal store.
    db_path = os.getenv("SECOND_BRAIN_DB")
    chroma_path = os.getenv("SECOND_BRAIN_CHROMA")
    if db_path and chroma_path:
        return Storage(db_path=db_path, chroma_path=chroma_path)
    return Storage()


@st.cache_resource
def get_note_service() -> NoteService:
    return NoteService(get_storage())


@st.cache_resource
def get_ask_service() -> AskService:
    return AskService(get_storage())


@st.cache_resource
def get_whisper_model():
    return load_model("base")
