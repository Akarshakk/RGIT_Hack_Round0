"""Builds the soundtrack: voiceover on the film timeline, a synthesized ambient bed ducked under the voice, soft UI sounds.
python audio.py <timeline.json> <out.wav>"""
import json, sys, wave
from pathlib import Path
import numpy as np

SR = 48000
V = Path(__file__).parent
tl = json.load(open(sys.argv[1]))
total = tl["total"] + 0.4
N = int(total * SR)
rng = np.random.default_rng(11)
t_all = np.arange(N) / SR


def read_wav(p):
    with wave.open(str(p)) as w:
        a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
        assert w.getframerate() == SR, p
    return a


def db(x):
    return 10 ** (x / 20)


# ---------- voiceover ----------
vo = np.zeros(N, np.float32)
active = np.zeros(N, np.float32)
for item in tl["vo"]:
    a = read_wav(V / "vo" / f"{item['id']}.wav")
    rms = np.sqrt(np.mean(a[np.abs(a) > 0.01] ** 2))
    a = a * (db(-17) / rms)  # same speaking level for every line
    i = int(item["t"] * SR)
    j = min(N, i + len(a))
    vo[i:j] += a[: j - i]
    active[i:j] = 1

# ---------- music: slow ambient pad + sparse soft plucks ----------
def note(m):
    return 440 * 2 ** ((m - 69) / 12)

chords = [  # midi notes, one chord per 8 s, gentle and modern
    [53, 60, 64, 67, 72],   # Fmaj7 / add9 colour
    [57, 60, 64, 67, 71],   # Am7(add9-ish)
    [48, 55, 59, 64, 67],   # Cmaj7
    [55, 59, 62, 66, 69],   # G6/maj7 colour
]
seg = 8.0
pad = np.zeros((N, 2), np.float32)
for ci in range(int(total // seg) + 2):
    ch = chords[ci % len(chords)]
    t0 = ci * seg - 1.5
    i0, i1 = max(0, int(t0 * SR)), min(N, int((t0 + seg + 3.0) * SR))
    if i0 >= i1:
        continue
    tt = t_all[i0:i1] - t0
    env = np.minimum(1, tt / 2.2) * np.minimum(1, np.maximum(0, (seg + 3.0 - tt) / 2.6))
    for k, m in enumerate(ch):
        f = note(m)
        for side, det in ((0, -0.18), (1, 0.21)):
            ph = 2 * np.pi * (f + det) * tt
            tone = 0.62 * np.sin(ph) + 0.18 * np.sin(2 * ph + 0.4) + 0.06 * np.sin(3 * ph + 1.1)
            amp = 0.055 * (0.75 if k == 0 else 1.0) * (1 + 0.08 * np.sin(2 * np.pi * 0.11 * tt + k))
            pad[i0:i1, side] += (tone * amp * env).astype(np.float32)
    # sub root, very low
    sub = 0.05 * np.sin(2 * np.pi * note(ch[0] - 12) * tt) * env
    pad[i0:i1, 0] += sub; pad[i0:i1, 1] += sub
# sparse plucks on a pentatonic set, quiet, every ~1.3 s
pluck = np.zeros((N, 2), np.float32)
scale = [72, 74, 76, 79, 81, 84]
t = 2.0
while t < total - 3:
    m = scale[rng.integers(len(scale))]
    dur = 1.6
    i0, i1 = int(t * SR), min(N, int((t + dur) * SR))
    tt = t_all[i0:i1] - t
    s = (np.sin(2 * np.pi * note(m) * tt) + 0.25 * np.sin(2 * np.pi * note(m) * 2 * tt)) * np.exp(-tt * 3.2) * np.minimum(1, tt / 0.01)
    pan = rng.uniform(0.3, 0.7)
    pluck[i0:i1, 0] += (s * 0.028 * (1 - pan)).astype(np.float32)
    pluck[i0:i1, 1] += (s * 0.028 * pan).astype(np.float32)
    t += rng.choice([1.3, 1.3, 2.6, 0.65])
# soft air: filtered noise
air = np.zeros((N, 2), np.float32)
f = np.fft.rfftfreq(N, 1 / SR)
shape = 1 / (1 + (f / 700) ** 2)  # soft low-pass "air"
for c in range(2):
    spec = np.fft.rfft(rng.standard_normal(N)) * shape
    y = np.fft.irfft(spec, N)
    air[:, c] = (y / np.max(np.abs(y)) * 0.05).astype(np.float32)
music = pad + pluck + air
# duck under the voice (smoothed), fade in/out with the film
k = int(0.35 * SR)
kern = np.ones(k, np.float32) / k
duck = np.convolve(active, kern, mode="same")
gain = 1 - 0.55 * np.clip(duck, 0, 1)
fade = np.minimum(1, t_all / 2.5) * np.clip((total - 0.4 - t_all) / 2.6, 0, 1)
music *= (gain * fade)[:, None]
music *= db(-3)

# ---------- UI sounds ----------
sfx = np.zeros(N, np.float32)
def add(t0, sig):
    i = int(t0 * SR); j = min(N, i + len(sig))
    if 0 <= i < N:
        sfx[i:j] += sig[: j - i]
def click_sig(level, f):
    n = int(0.045 * SR); tt = np.arange(n) / SR
    body = np.sin(2 * np.pi * f * tt) * np.exp(-tt * 160)
    tick = rng.standard_normal(n) * np.exp(-tt * 900) * 0.6
    return ((body + tick) * db(level)).astype(np.float32)
for s in tl["sounds"]:
    if s["type"] == "click":
        add(s["t"], click_sig(-27, 2300))
    elif s["type"] == "key":
        add(s["t"], click_sig(-35 + rng.uniform(-2, 1), rng.uniform(2600, 3600)))
    elif s["type"] == "chime":
        n = int(0.9 * SR); tt = np.arange(n) / SR
        c = np.sin(2 * np.pi * 1318.5 * tt) * np.exp(-tt * 6) + 0.8 * np.where(tt > 0.11, np.sin(2 * np.pi * 1975.5 * (tt - 0.11)) * np.exp(-(tt - 0.11) * 6), 0)
        add(s["t"], (c * db(-25)).astype(np.float32))

import os
if os.environ.get("STEMS"):
    for name, sig in (("stem_music", music), ("stem_vo", np.stack([vo, vo], 1)), ("stem_sfx", np.stack([sfx, sfx], 1))):
        with wave.open(f"{V}/{name}.wav", "wb") as w:
            w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(sig, -1, 1) * 32767).astype(np.int16).tobytes())
mix = music + (vo + sfx)[:, None]
peak = np.max(np.abs(mix))
mix = mix * (db(-1.5) / peak)
out = (np.clip(mix, -1, 1) * 32767).astype(np.int16)
with wave.open(sys.argv[2], "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(out.tobytes())
print("wrote", sys.argv[2], round(total, 2), "s; vo lines", len(tl["vo"]), "sounds", len(tl["sounds"]))
