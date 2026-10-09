"""Persistent memory for J.A.R.V.I.S. — facts and notes stored as JSON files."""

import json
import os
from datetime import datetime, timezone

DATA_DIR = os.environ.get("JARVIS_DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "data"))
DATA_DIR = os.path.abspath(DATA_DIR)

MEMORY_FILE = os.path.join(DATA_DIR, "memory.json")
NOTES_FILE = os.path.join(DATA_DIR, "notes.json")


def _ensure_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def _load(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def _save(path, data):
    _ensure_dir()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def add_fact(fact: str) -> str:
    """Store a fact about the user. Returns a confirmation string."""
    try:
        fact = (fact or "").strip()
        if not fact:
            return "I need an actual fact to remember, sir."
        _ensure_dir()
        data = _load(MEMORY_FILE, {"facts": []})
        facts = data.get("facts", [])
        if fact not in facts:
            facts.append(fact)
        data["facts"] = facts
        _save(MEMORY_FILE, data)
        return f"Committed to memory, sir: {fact}"
    except Exception as e:
        return f"I couldn't store that memory, sir: {e}"


def get_facts() -> list:
    """Return the list of stored facts."""
    try:
        data = _load(MEMORY_FILE, {"facts": []})
        return data.get("facts", [])
    except Exception:
        return []


def add_note(text: str) -> str:
    """Store a timestamped note. Returns a confirmation string."""
    try:
        text = (text or "").strip()
        if not text:
            return "I need actual text for the note, sir."
        _ensure_dir()
        data = _load(NOTES_FILE, {"notes": []})
        notes = data.get("notes", [])
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        notes.append({"text": text, "created": ts})
        data["notes"] = notes
        _save(NOTES_FILE, data)
        return f"Note taken, sir: {text}"
    except Exception as e:
        return f"I couldn't take that note, sir: {e}"


def get_notes() -> list:
    """Return the list of stored notes (dicts with text/created)."""
    try:
        data = _load(NOTES_FILE, {"notes": []})
        return data.get("notes", [])
    except Exception:
        return []
