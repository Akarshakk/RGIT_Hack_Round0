"""python render.py <fps> <dsf> <outdir> [start_frame_to_save]  — renders the film frame by frame."""
import json, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

V = Path(__file__).parent
fps, dsf, out = float(sys.argv[1]), float(sys.argv[2]), Path(sys.argv[3])
out.mkdir(parents=True, exist_ok=True)
vo = json.load(open(V / "vo_durations.json"))
with sync_playwright() as p:
    b = p.chromium.launch(args=["--force-color-profile=srgb", "--hide-scrollbars"])
    ctx = b.new_context(viewport={"width": 1920, "height": 1080}, device_scale_factor=dsf, reduced_motion="reduce")
    page = ctx.new_page()
    page.on("console", lambda m: m.type in ("error", "warning") and print("console:", m.type, m.text[:200], flush=True))
    page.on("pageerror", lambda e: print("pageerror:", e, flush=True))
    page.add_init_script(f"window.__VO = {json.dumps(vo)};")
    page.goto("http://localhost:8010/?film=1", wait_until="networkidle")
    page.add_script_tag(path=str(V / "film.js"))
    t0 = time.time()
    info = page.evaluate("FILM.setup()")
    print("setup", round(time.time() - t0, 1), "s", json.dumps(info, ensure_ascii=False)[:600], flush=True)
    plan = page.evaluate("FILM.build()")
    total = plan["total"]
    print("total", round(total, 2), "s", flush=True)
    n = int(total * fps) + 1
    t0 = time.time()
    for f in range(n):
        t = f / fps
        x, y = page.evaluate(f"FILM.render({t})")
        page.mouse.move(x, y)
        page.screenshot(path=str(out / f"f{f:05d}.jpg"), type="jpeg", quality=93, scale="device")
        if f % 60 == 0:
            print(f"frame {f}/{n} t={t:.1f}s elapsed={time.time() - t0:.0f}s", flush=True)
    json.dump({"total": total, "fps": fps, "vo": plan["vo"], "sounds": page.evaluate("FILM.sounds()"), "T": plan["T"]}, open(out / "timeline.json", "w"), indent=1)
    print("done", n, "frames in", round(time.time() - t0), "s", flush=True)
    b.close()
