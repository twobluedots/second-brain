import os

import streamlit as st

from src.logger import logger
from ui.services import get_note_service

os.makedirs("entries", exist_ok=True)

try:
    get_note_service()
except Exception as _err:
    logger.error("Service init failed: %s", _err)
    st.error(f"Failed to initialise storage: {_err}")
    st.info("Check that the data/ directory is writable and the database file is not corrupted.")
    st.stop()

if "entries" not in st.session_state:
    st.session_state.entries = []

pg = st.navigation([
    st.Page("pages/capture.py", title="Capture", icon="📥"),
    st.Page("pages/ask.py",     title="Ask",     icon="🤖"),
    st.Page("pages/search.py",  title="Search",  icon="🔍"),
    st.Page("pages/recents.py", title="Recents", icon="📋"),
    st.Page("pages/categories.py", title="Categories", icon="🗂️"),
    st.Page("pages/journal.py", title="Journal", icon="📝"),
    st.Page("pages/mirror.py",  title="Mirror",  icon="🔮"),
])
pg.run()
