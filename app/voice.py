"""Voice: Groq Whisper STT + edge-tts TTS."""

import asyncio
import os
import tempfile


def stt(audio_path: str) -> str:
    """Transcribe an audio file with Groq Whisper. Returns plain text."""
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GROQ_API_KEY not set")
    import groq
    client = groq.Groq(api_key=api_key)
    with open(audio_path, "rb") as f:
        resp = client.audio.transcriptions.create(
            model="whisper-large-v3",
            file=f,
        )
    text = (resp.text or "").strip()
    return text


async def _tts_async(text: str, out_path: str) -> None:
    import edge_tts
    # Honor the standard proxy env vars (needed on networks with an egress
    # proxy; harmless when unset, e.g. on the Oracle server).
    proxy = (
        os.environ.get("HTTPS_PROXY")
        or os.environ.get("https_proxy")
        or os.environ.get("ALL_PROXY")
        or os.environ.get("all_proxy")
    )
    communicate = edge_tts.Communicate(text, "en-GB-RyanNeural", proxy=proxy)
    await communicate.save(out_path)


def tts(text: str) -> bytes:
    """Synthesize speech (British male voice). Returns MP3 bytes. Sync wrapper."""
    text = (text or "").strip() or "At your service, sir."
    # edge-tts handles long text, but keep it bounded for the phone client.
    if len(text) > 1200:
        text = text[:1197] + "..."
    fd, tmp = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    try:
        asyncio.run(_tts_async(text, tmp))
        with open(tmp, "rb") as f:
            return f.read()
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass
