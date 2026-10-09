"""FastAPI app: serves the phone client and the voice/chat APIs."""

import base64
import os
import tempfile

from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import brain, voice

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "static")
DATA_DIR = os.environ.get("JARVIS_DATA_DIR", os.path.join(BASE_DIR, "data"))

app = FastAPI(title="J.A.R.V.I.S.", version="1.0.0")


@app.on_event("startup")
def _startup():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(STATIC_DIR, exist_ok=True)


def _require_token(authorization: str | None) -> None:
    expected = os.environ.get("JARVIS_TOKEN", "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="server token not configured")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    if authorization[7:] != expected:
        raise HTTPException(status_code=403, detail="invalid token")


def _require_groq() -> None:
    if not os.environ.get("GROQ_API_KEY", "").strip():
        raise HTTPException(status_code=503, detail="GROQ_API_KEY not set on server")


def _voice_payload(transcript: str, reply: str, tools_used: list, with_audio: bool) -> dict:
    payload = {"transcript": transcript, "reply": reply, "tools_used": tools_used,
               "audio_base64": None}
    if with_audio:
        try:
            audio = voice.tts(reply)
            payload["audio_base64"] = base64.b64encode(audio).decode("ascii")
        except Exception as e:
            payload["tts_error"] = str(e)
    return payload


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "version": "1.0.0",
        "groq_configured": bool(os.environ.get("GROQ_API_KEY", "").strip()),
    }


@app.post("/api/voice")
async def api_voice(audio: UploadFile = File(...),
                   authorization: str | None = Header(default=None)):
    _require_token(authorization)
    _require_groq()
    suffix = ".webm"
    fname = (audio.filename or "").lower()
    if fname.endswith(".wav"):
        suffix = ".wav"
    elif fname.endswith(".mp3"):
        suffix = ".mp3"
    elif fname.endswith(".m4a"):
        suffix = ".m4a"
    elif fname.endswith(".ogg"):
        suffix = ".ogg"
    fd, tmp = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    try:
        data = await audio.read()
        if not data:
            raise HTTPException(status_code=400, detail="empty audio upload")
        with open(tmp, "wb") as f:
            f.write(data)
        try:
            transcript = voice.stt(tmp)
        except RuntimeError as e:
            raise HTTPException(status_code=503, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"speech recognition failed: {e}")
        if not transcript:
            return JSONResponse({
                "transcript": "",
                "reply": "I didn't catch that, sir. One more time?",
                "tools_used": [],
                "audio_base64": None,
            })
        try:
            reply, tools_used = brain.chat(transcript)
        except RuntimeError as e:
            raise HTTPException(status_code=503, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"brain error: {e}")
        return JSONResponse(_voice_payload(transcript, reply, tools_used, True))
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


class ChatIn(BaseModel):
    text: str
    voice: bool = False


@app.post("/api/chat")
def api_chat(body: ChatIn, authorization: str | None = Header(default=None)):
    _require_token(authorization)
    _require_groq()
    text = (body.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="empty text")
    try:
        reply, tools_used = brain.chat(text)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"brain error: {e}")
    return JSONResponse(_voice_payload(text, reply, tools_used, bool(body.voice)))


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
