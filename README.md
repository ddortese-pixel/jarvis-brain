# J.A.R.V.I.S. v1 — Just A Rather Very Intelligent System

A real, working voice assistant that runs on your own server. Talk to it from
your phone's browser: hold the mic button, speak, and Jarvis answers out loud
in a British butler voice — and can actually *do* things (weather, time,
system stats, web lookup, memory, notes).

## Architecture

```
┌──────────────┐   HTTPS (Cloudflare      ┌─────────────────────────────┐
│  Phone        │   quick tunnel)          │  Oracle VPS                 │
│  browser      │ ───────────────────────► │                             │
│  (mic/speaker │                          │  ┌───────────────────────┐  │
│   hold-to-talk│ ◄─────────────────────── │  │ FastAPI (uvicorn)     │  │
└──────────────┘   MP3 reply (base64)      │  │  /api/voice  /api/chat│  │
                                           │  └──────┬────────┬───────┘  │
                                           │         │        │          │
                                           │   ┌─────▼──┐ ┌──▼────────┐  │
                                           │   │ Groq   │ │ edge-tts  │  │
                                           │   │ Whisper│ │ en-GB-    │  │
                                           │   │ STT    │ │ RyanNeural│  │
                                           │   └────────┘ └───────────┘  │
                                           │   ┌─────────────────────┐  │
                                           │   │ Groq llama-3.3-70b  │  │
                                           │   │ + tool calling      │  │
                                           │   │ (weather/time/stats │  │
                                           │   │  search/memory/…)   │  │
                                           │   └─────────────────────┘  │
                                           └─────────────────────────────┘
```

Voice path: `MediaRecorder (webm/opus)` → `POST /api/voice` → Groq Whisper
transcription → Groq LLM with tools → edge-tts MP3 → base64 in JSON → phone
plays it. Text path: `POST /api/chat` does the same without audio.

## One-command install (on the server, as root)

```bash
curl -fsSL <installer-url>/install.sh | sudo bash
```

The installer will:
1. Install `python3-venv`, `ffmpeg`, `curl`
2. Create a `jarvis` system user and `/opt/jarvis`
3. Set up a venv and install Python deps
4. Ask for your Groq API key (free at https://groq.com — Enter to skip and add later)
5. Generate a random 64-hex-char `JARVIS_TOKEN`, write `/etc/jarvis.env` (600)
6. Install + start `jarvis.service` and `jarvis-tunnel.service`
7. Print the public tunnel URL and your token

Then on your phone: open the URL, paste the token, tap Save, hold the mic.

### Adding the Groq key later

```bash
sudo nano /etc/jarvis.env     # set GROQ_API_KEY=...
sudo systemctl restart jarvis
```

## Security notes

- Every API call requires `Authorization: Bearer <JARVIS_TOKEN>` (64 random hex chars).
- Uvicorn binds to `127.0.0.1` only — the only public surface is the Cloudflare tunnel.
- The `*.trycloudflare.com` URL is unguessable, but the token is still required.
- `/etc/jarvis.env` is `chmod 600`, owned by the `jarvis` user.
- Tools are a fixed allowlist — the LLM cannot run arbitrary shell commands.

## Roadmap

- **Room satellite**: Raspberry Pi / old phone running openWakeWord ("Jarvis")
  with mic + speaker, streaming to the server — true hands-free.
- **Voice upgrade**: ElevenLabs British butler voice (needs paid API key).
- **More tools**: Home Assistant (lights/thermostat), Google Calendar, timers,
  YouTube search, screenshot + vision questions.
- **Barge-in**: interrupt Jarvis mid-reply; streaming STT/TTS for sub-second latency.
- **Voice biometrics**: high-privilege actions only for your voiceprint.

## Local dev

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
export JARVIS_TOKEN=dev GROQ_API_KEY=...  # key optional for /api/health
uvicorn app.main:app --reload --port 8123
```
