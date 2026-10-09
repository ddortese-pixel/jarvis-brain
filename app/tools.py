"""Tool functions for J.A.R.V.I.S. — every function never raises.

Each tool returns a concise plain-text string suitable for speech output.
TOOL_SCHEMAS holds OpenAI-style function definitions for Groq tool calling.
"""

import json
import urllib.parse
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

from . import memory

USER_TZ = ZoneInfo("America/New_York")


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def get_current_time() -> str:
    """Return the current local date and time in America/New_York."""
    try:
        now = datetime.now(USER_TZ)
        # e.g. "Thursday, October 8, 2026, 8:25 PM EDT"
        s = now.strftime("%A, %B %d, %Y, %-I:%M %p %Z")
        return s
    except Exception as e:
        return f"I'm unable to read the clock at the moment, sir: {e}"


def get_weather(city: str = "Indianapolis") -> str:
    """Current weather via Open-Meteo (no API key needed)."""
    try:
        city = (city or "Indianapolis").strip() or "Indianapolis"
        # 1. Geocode
        geo_url = (
            "https://geocoding-api.open-meteo.com/v1/search?"
            + urllib.parse.urlencode({"name": city, "count": 1, "format": "json"})
        )
        with urllib.request.urlopen(geo_url, timeout=15) as resp:
            geo = json.loads(resp.read().decode("utf-8"))
        results = geo.get("results") or []
        if not results:
            return f"I couldn't locate {city} on the map, sir."
        place = results[0]
        lat, lon = place["latitude"], place["longitude"]
        name = place.get("name", city)
        # 2. Current conditions
        fc_url = (
            "https://api.open-meteo.com/v1/forecast?"
            + urllib.parse.urlencode({
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,apparent_temperature,"
                           "weather_code,wind_speed_10m",
                "temperature_unit": "fahrenheit",
                "wind_speed_unit": "mph",
                "timezone": "auto",
            })
        )
        with urllib.request.urlopen(fc_url, timeout=15) as resp:
            fc = json.loads(resp.read().decode("utf-8"))
        cur = fc.get("current", {})
        temp = cur.get("temperature_2m")
        feels = cur.get("apparent_temperature")
        hum = cur.get("relative_humidity_2m")
        wind = cur.get("wind_speed_10m")
        code = cur.get("weather_code")
        desc = _weather_code_desc(code)
        parts = [f"Currently in {name}: {desc}"]
        if temp is not None:
            parts.append(f"{round(temp)}°F")
        if feels is not None:
            parts.append(f"feels like {round(feels)}°F")
        if hum is not None:
            parts.append(f"humidity {hum}%")
        if wind is not None:
            parts.append(f"wind {round(wind)} mph")
        return ", ".join(parts) + "."
    except Exception as e:
        return f"Weather satellites are unresponsive, sir: {e}"


def _weather_code_desc(code) -> str:
    mapping = {
        0: "clear skies", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
        45: "foggy", 48: "foggy with rime",
        51: "light drizzle", 53: "drizzle", 55: "heavy drizzle",
        56: "freezing drizzle", 57: "freezing drizzle",
        61: "light rain", 63: "rain", 65: "heavy rain",
        66: "freezing rain", 67: "freezing rain",
        71: "light snow", 73: "snow", 75: "heavy snow", 77: "snow grains",
        80: "light showers", 81: "showers", 82: "violent showers",
        85: "light snow showers", 86: "snow showers",
        95: "thunderstorms", 96: "thunderstorms with hail", 99: "thunderstorms with hail",
    }
    try:
        return mapping.get(int(code), "unsettled conditions")
    except (TypeError, ValueError):
        return "unsettled conditions"


def system_stats() -> str:
    """CPU / memory / disk usage via psutil."""
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        return (
            f"CPU load {cpu:.0f} percent, memory {mem.percent:.0f} percent used "
            f"({mem.used / 1e9:.1f} of {mem.total / 1e9:.1f} GB), "
            f"disk {disk.percent:.0f} percent used "
            f"({disk.used / 1e9:.1f} of {disk.total / 1e9:.1f} GB). "
            "All systems nominal, sir."
        )
    except ImportError:
        return "System diagnostics unavailable — psutil is not installed, sir."
    except Exception as e:
        return f"Unable to read system diagnostics, sir: {e}"


def web_search(query: str) -> str:
    """Quick web lookup via the DuckDuckGo instant-answer API (no key)."""
    try:
        query = (query or "").strip()
        if not query:
            return "Give me something to search for, sir."
        url = "https://api.duckduckgo.com/?" + urllib.parse.urlencode(
            {"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"}
        )
        req = urllib.request.Request(url, headers={"User-Agent": "JARVIS/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        abstract = (data.get("AbstractText") or "").strip()
        if abstract:
            return abstract[:600]
        topics = data.get("RelatedTopics") or []
        for t in topics:
            if isinstance(t, dict) and t.get("Text"):
                return t["Text"][:600]
            if isinstance(t, dict) and t.get("Topics"):
                for sub in t["Topics"]:
                    if isinstance(sub, dict) and sub.get("Text"):
                        return sub["Text"][:600]
        return "I couldn't find anything solid on that, sir."
    except Exception:
        return "I couldn't find anything solid on that, sir."


def remember(fact: str) -> str:
    """Store a fact about the user in long-term memory."""
    return memory.add_fact(fact)


def recall() -> str:
    """Read back everything stored about the user."""
    try:
        facts = memory.get_facts()
        if not facts:
            return "My memory banks are empty on personal details, sir. Tell me something worth remembering."
        lines = [f"{i + 1}. {f}" for i, f in enumerate(facts)]
        return "Here's what I remember about you, sir:\n" + "\n".join(lines)
    except Exception as e:
        return f"Unable to access memory, sir: {e}"


def take_note(text: str) -> str:
    """Save a timestamped note."""
    return memory.add_note(text)


def list_notes() -> str:
    """Read back all saved notes."""
    try:
        notes = memory.get_notes()
        if not notes:
            return "No notes on file, sir."
        lines = [f"{i + 1}. [{n.get('created', '?')}] {n.get('text', '')}"
                 for i, n in enumerate(notes)]
        return "Your notes, sir:\n" + "\n".join(lines)
    except Exception as e:
        return f"Unable to read notes, sir: {e}"


# ---------------------------------------------------------------------------
# OpenAI-style tool schemas + dispatcher
# ---------------------------------------------------------------------------

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Get the current local date and time (America/New_York).",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather conditions for a city.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name, e.g. Indianapolis"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "system_stats",
            "description": "Report server CPU, memory, and disk usage.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for a quick factual answer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remember",
            "description": "Store a fact about the user in long-term memory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "fact": {"type": "string", "description": "The fact to remember"},
                },
                "required": ["fact"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recall",
            "description": "Read back all stored facts about the user.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "take_note",
            "description": "Save a timestamped note.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Note text"},
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_notes",
            "description": "List all saved notes.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]

_DISPATCH = {
    "get_current_time": get_current_time,
    "get_weather": get_weather,
    "system_stats": system_stats,
    "web_search": web_search,
    "remember": remember,
    "recall": recall,
    "take_note": take_note,
    "list_notes": list_notes,
}


def execute(name: str, args: dict) -> str:
    """Run a tool by name with args dict. Never raises."""
    try:
        fn = _DISPATCH.get(name)
        if fn is None:
            return f"Unknown tool '{name}', sir."
        args = args or {}
        return str(fn(**args))
    except TypeError as e:
        return f"Tool '{name}' received bad arguments, sir: {e}"
    except Exception as e:
        return f"Tool '{name}' failed, sir: {e}"
