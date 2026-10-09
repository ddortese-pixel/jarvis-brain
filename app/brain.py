"""The brain: Groq LLM with tool calling."""

import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from . import tools


def _system_prompt() -> str:
    date = datetime.now(ZoneInfo("America/New_York")).strftime("%A, %B %d, %Y")
    return (
        "You are J.A.R.V.I.S. (Just A Rather Very Intelligent System), an articulate, "
        "highly capable, slightly witty AI assistant in the spirit of Tony Stark's AI. "
        "Keep responses concise and natural for speech — one to three sentences unless "
        "the user asks for detail. Address the user as 'sir'. Never break character. "
        f"Today's date is {date}."
    )


def _groq_client():
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GROQ_API_KEY not set")
    import groq
    return groq.Groq(api_key=api_key)


def chat(user_text: str) -> tuple:
    """Run one conversational turn. Returns (reply: str, tools_used: list[str])."""
    user_text = (user_text or "").strip()
    if not user_text:
        return ("I didn't quite catch that, sir.", [])

    client = _groq_client()
    model = "llama-3.3-70b-versatile"
    messages = [
        {"role": "system", "content": _system_prompt()},
        {"role": "user", "content": user_text},
    ]
    tools_used: list = []

    for _ in range(5):  # max tool iterations
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools.TOOL_SCHEMAS,
            tool_choice="auto",
        )
        msg = resp.choices[0].message
        tool_calls = getattr(msg, "tool_calls", None) or []
        if not tool_calls:
            reply = (msg.content or "").strip() or "At your service, sir."
            return (reply, tools_used)

        messages.append(msg)
        for tc in tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            result = tools.execute(name, args)
            tools_used.append(name)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "name": name,
                "content": result,
            })

    # Ran out of iterations — ask the model for a final answer without tools.
    resp = client.chat.completions.create(model=model, messages=messages)
    reply = (resp.choices[0].message.content or "").strip() or "At your service, sir."
    return (reply, tools_used)
