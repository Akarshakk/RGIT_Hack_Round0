"""Chariot TTS: python tts.py <out.wav> "<text>"  (key + voice from the project .env)."""
import os, sys, httpx
from dotenv import dotenv_values
env = dotenv_values(str(__import__("pathlib").Path(__file__).resolve().parent.parent / ".env"))
r = httpx.post("https://api.chariot.in/v1/tts", timeout=120,
               headers={"chariotai-api-key": env["CHARIOT_KEY"], "Content-Type": "application/json"},
               json={"voice_id": env["CHARIOT_VOICE_ID"], "text": sys.argv[2], "model_type": "chariot-multilingual-v1"})
print(r.status_code, r.headers.get("content-type"), len(r.content))
r.raise_for_status()
open(sys.argv[1], "wb").write(r.content)
