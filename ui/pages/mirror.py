from datetime import datetime, timedelta, timezone

import streamlit as st

from config import CATEGORY_MIRROR_LINES
from ui.components import CATEGORY_COLOR
from ui.services import get_note_service

st.title("Mirror")

try:
    stats = get_note_service().get_mirror_stats()
except Exception as e:
    st.error(f"Couldn't load stats: {e}")
    st.stop()

col_week, col_total = st.columns(2)
with col_week:
    st.metric("This week", stats["week_count"])
with col_total:
    st.metric("Total so far", stats["total_count"])

if stats["category_breakdown"]:
    pills_html = " · ".join(
        f'<span style="background:{CATEGORY_COLOR.get(cat, ("rgba(0,0,0,0.08)","#555"))[0]};'
        f'color:{CATEGORY_COLOR.get(cat, ("rgba(0,0,0,0.08)","#555"))[1]};'
        f'padding:2px 10px;border-radius:12px;font-size:0.85em;'
        f'border:1px solid {CATEGORY_COLOR.get(cat, ("rgba(0,0,0,0.08)","#555"))[1]}40">'
        f'{cat} ×{count}</span>'
        for cat, count in sorted(stats["category_breakdown"].items(), key=lambda x: -x[1])
    )
    st.markdown(pills_html, unsafe_allow_html=True)

if stats["top_category"] and stats["top_category"] in CATEGORY_MIRROR_LINES:
    st.caption(CATEGORY_MIRROR_LINES[stats["top_category"]])

st.divider()

now_date = datetime.now(timezone.utc).date()
window = [now_date - timedelta(days=i) for i in range(6, -1, -1)]
dots = "".join("●" if d in stats["active_days"] else "○" for d in window)
st.markdown(f"**{dots}**")
active_count = sum(1 for d in window if d in stats["active_days"])
if active_count > 0:
    st.caption(f"You showed up {active_count} of 7 days")

rediscovery = stats["rediscovery"]
if rediscovery:
    st.divider()
    try:
        ts = datetime.fromisoformat(rediscovery["created_at"].replace("Z", "+00:00"))
        days_ago = (datetime.now(timezone.utc) - ts).days
        label = f"{days_ago} days ago you wrote:"
    except Exception:
        label = "From the past:"
    text = rediscovery.get("content") or rediscovery.get("description", "")
    st.info(f"*{label}*\n\n{text}")
