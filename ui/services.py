import streamlit as st

from src.notes_service import NoteService
from src.rag.service import AskService
from src.storage.storage import Storage
from src.processing import load_model


@st.cache_resource
def get_storage() -> Storage:
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
