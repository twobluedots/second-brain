from datetime import datetime, timezone

import streamlit as st

from src.utils import time_filter_to_iso
from ui.services import get_note_service

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
