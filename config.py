"""
Configuration for second-brain storage and defaults.
Override parameters in Storage() for testing.
"""

from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

# Database paths
DB_PATH = Path("data/database/entries.db")
CHROMA_PATH = Path("./chroma_data")

# Default categories -- defined by what you DO with the note, not the topic
DEFAULT_CATEGORIES = [
    "task",
    "mood",
    "journal",
    "learning",
    "reference",
    "insight",
    "achievement",
]

CATEGORY_DESCRIPTIONS = {
    "task":        "Something to act on -- a to-do, reminder, or action item",
    "mood":        "Basic emotion tracking -- how you feel right now, emotional states over time",
    "journal":     "Daily activity log -- what you did today, interstitial journal entries",
    "learning":    "Dry facts and concepts to repeat later -- flashcard-style, no emotional weight, things you want to quiz yourself on",
    "reference":   "Things to look up only when a specific situation comes -- tips, how-tos, instructions, places or facts to find again",
    "insight":     "Getting to know yourself -- patterns you notice, observations about your experiences, thoughts about why you feel or act a certain way",
    "achievement": "Emotionally significant breakthroughs -- the 'I finally got it' feeling after being stuck, doing something hard, showing up despite resistance",
}

# Categories eligible for rediscovery on the Mirror page
REDISCOVERY_CATEGORIES = {"insight", "achievement"}

# One-line interpretation shown for the top category on the Mirror page
CATEGORY_MIRROR_LINES = {
    "insight":     "Reflective week — you've been noticing patterns about yourself.",
    "mood":        "You've been tuning into how you feel.",
    "learning":    "Curious week — lots of things you wanted to hold onto.",
    "reference":   "Practical week — filing things away for when you need them.",
    "task":        "Action-oriented week — lots on your radar.",
    "achievement": "You logged breakthroughs this week. That's rare — notice it.",
    "journal":     "You showed up and documented your days.",
}

# Local model for Ollama fallback (change to whichever you have pulled)
OLLAMA_MODEL = "llama3.2"

# Search defaults
DEFAULT_SEARCH_LIMIT = 10
