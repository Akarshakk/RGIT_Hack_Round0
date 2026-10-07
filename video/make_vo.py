import json, subprocess, sys
V = sys.argv[1]
lines = json.load(open(f"{V}/vo_lines.json"))
durs = {}
for k, text in lines.items():
    raw = f"{V}/vo/{k}_raw.wav"
    subprocess.run([sys.executable, f"{V}/tts.py", raw, text], check=True, capture_output=True)
    out = f"{V}/vo/{k}.wav"
    # trim leading/trailing silence, keep a natural 80 ms head and 150 ms tail
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-af",
                    "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.08,areverse,silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.15,areverse",
                    "-ar", "48000", "-ac", "1", out], check=True)
    d = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", out], capture_output=True, text=True).stdout)
    durs[k] = round(d, 3)
    print(k, durs[k], flush=True)
json.dump(durs, open(f"{V}/vo_durations.json", "w"), indent=1)
print("total", round(sum(durs.values()), 1))
