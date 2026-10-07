# Credence demo film

The demo video is rendered from the real app, frame by frame, with a scripted camera, cursor and typing.

```bash
# 1. voiceover (Chariot TTS; needs CHARIOT_KEY and CHARIOT_VOICE_ID in ../.env)
python video/make_vo.py video            # writes video/vo/*.wav and vo_durations.json
# 2. app running locally with GROQ_API_KEY set
uvicorn app.main:app --port 8010
# 3. frames (needs `pip install playwright numpy` and `playwright install chromium`)
python video/render.py 30 2 video/frames  # 3840x2160 JPEG frames + timeline.json
# 4. soundtrack + encode
python video/audio.py video/frames/timeline.json video/mix.wav
ffmpeg -i video/mix.wav -af loudnorm=I=-16:TP=-1.5 video/mix_ln.wav
ffmpeg -framerate 30 -i video/frames/f%05d.jpg -i video/mix_ln.wav -c:v libx264 -crf 15 -pix_fmt yuv420p -c:a aac -b:a 256k -shortest demo_video/Credence_demo_4K.mp4
```
