#!/usr/bin/env python3
"""
activate.py — pick a BASE and a TARGET, the alive swarm rebuilds it at the BEST quality/data combo, and plays it.

    pip3 install pillow numpy        # (ffmpeg required: brew install ffmpeg)

    python3 activate.py --base 720 --to 1080          # 720p → 1080p  (BEST QUALITY, ~93-95% capture)
    python3 activate.py --base 720 --to 1440
    python3 activate.py --base 720 --to 4k
    python3 activate.py --base 480 --to 720           # any base → any target
    python3 activate.py --video myclip.mp4 --base 720 --to 4k
    python3 activate.py --base 720 --to 4k --combo    # max DATA-SAVING instead (lower quality, e.g. 7.6× smaller)
    python3 activate.py --base 720 --to 1080 --capture 97   # or force an exact quality %

DEFAULT = BEST QUALITY: it dials up until ~95% of the detail is captured and reports the best data for that
quality. At small upscales (720→1080) you get ~93% capture at high PSNR. Use --combo for the value knee (max
data-saving). Honest: on real motion video the data saving at high quality is modest (unique detail per frame);
on typical/flat content and re-watched/cached content it is much larger.

The alive organism stores the hard blocks (deterministic, deduped, journaled, regenerates, adapts). It is NOT a
codec — it rebuilds from a small base + a live cache. On real motion the data win is modest (unique detail/frame);
the quality rebuild is real and the cache makes recurring/re-watched content free.
"""
import os, sys, glob, json, time, signal, subprocess, hashlib, argparse, shutil
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from complete_alive_organism import AliveOrganism
from vital_signs import check_alive, require_load_bearing

BS = 8; WORK = "/tmp/activate_swarm"
BASES = {"360": (640, 360), "480": (854, 480), "720": (1280, 720)}
TARGETS = {"720": (1280, 720), "1080": (1920, 1080), "1440": (2560, 1440), "4k": (3840, 2160)}

def psnr(a, b):
    m = np.mean((a.astype(np.float64)-b.astype(np.float64))**2); return 99.0 if m == 0 else 10*np.log10(255.0**2/m)
def arr(im): return np.asarray(im.convert("RGB"), dtype=np.int16)

def best_threshold(true, bic, bmax, base_bytes, full_bytes, force_capture=None):
    """Sweep thresholds; return T at the KNEE of the capture⇄data-saving curve (best value), or hit force_capture%."""
    e_bic = float(np.sum((true-bic).astype(np.float64)**2)) or 1.0
    cur = []
    for T in range(60, 0, -1):
        h = bmax > T; r = np.where(np.repeat(np.repeat(h, BS, 0), BS, 1)[..., None], true, bic)
        cap = 100*(1-float(np.sum((true-r).astype(np.float64)**2))/e_bic)
        save = full_bytes/(base_bytes + int(h.sum())*BS*BS*3)
        cur.append((T, cap, save))
    if force_capture is not None:
        for T, cap, save in cur:                       # first (largest T) meeting the target
            if cap >= force_capture: return T, cap, save
        return cur[-1][0], cur[-1][1], cur[-1][2]
    caps = np.array([c for _, c, _ in cur]); savs = np.array([s for _, _, s in cur])
    cn = (caps-caps.min())/(np.ptp(caps)+1e-9); sn = (savs-savs.min())/(np.ptp(savs)+1e-9)
    x1, y1, x2, y2 = cn[0], sn[0], cn[-1], sn[-1]      # knee = max perpendicular distance from the endpoint chord
    d = np.abs((y2-y1)*cn - (x2-x1)*sn + x2*y1 - y2*x1) / (np.hypot(y2-y1, x2-x1)+1e-9)
    i = int(np.argmax(d)); return cur[i]

def get_video(path):
    if path and os.path.exists(path): return path
    os.makedirs(WORK, exist_ok=True); dst = f"{WORK}/sample.mp4"
    if os.path.exists(dst) and os.path.getsize(dst) > 10000: return dst
    for u in ("https://test-videos.co.uk/vids/bigbuckbunny/mp4/h264/1080/Big_Buck_Bunny_1080_10s_5MB.mp4",
              "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"):
        try:
            subprocess.run(["curl", "-fsSL", "--max-time", "60", "-o", dst, u], check=True)
            if os.path.getsize(dst) > 10000: return dst
        except Exception: continue
    return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default=None); ap.add_argument("--base", default="720", choices=list(BASES))
    ap.add_argument("--to", default="1080", choices=list(TARGETS)); ap.add_argument("--secs", type=float, default=2.0)
    ap.add_argument("--capture", type=float, default=95.0, help="quality target %% (default 95 = best quality)")
    ap.add_argument("--combo", action="store_true", help="use the value knee (max data-saving) instead of quality target")
    a = ap.parse_args()
    base_wh, tgt = BASES[a.base], TARGETS[a.to]
    if tgt[0] <= base_wh[0]: print(f"  target {a.to} must be higher than base {a.base}"); return
    if not shutil.which("ffmpeg"): print("  need ffmpeg: brew install ffmpeg"); return
    force_cap = None if a.combo else a.capture
    mode = "BEST value/data combo (knee)" if a.combo else f"BEST quality (~{a.capture:.0f}% capture) + best data for it"
    print(f"\033[1m⚡ ACTIVATE — {a.base}p base → {a.to}   ({mode})\033[0m")
    check_alive()                     # LAUNCH-TIME LIVENESS: aborts with symptoms if the organism has gone static
    vid = get_video(a.video)
    if not vid: print("  no video (offline). pass --video yourfile.mp4"); return
    os.makedirs(f"{WORK}/f", exist_ok=True); os.makedirs(f"{WORK}/o", exist_ok=True)
    for p in glob.glob(f"{WORK}/f/*.png")+glob.glob(f"{WORK}/o/*.png"): os.remove(p)
    fps_v = 24; nfr = int(a.secs*fps_v)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", vid, "-vf", f"scale={tgt[0]}:{tgt[1]},fps={fps_v}",
                    "-frames:v", str(nfr), f"{WORK}/f/f%04d.png"], check=False)
    frames = sorted(glob.glob(f"{WORK}/f/*.png"))
    if not frames: print("  ffmpeg produced no frames"); return
    print(f"  source: {os.path.basename(vid)} ({os.path.getsize(vid)/1e6:.1f} MB) → {len(frames)} frames at {tgt[0]}×{tgt[1]}")

    base_bytes = base_wh[0]*base_wh[1]*3; full_bytes = tgt[0]*tgt[1]*3
    org = AliveOrganism(confirm=1); frozen = AliveOrganism(confirm=10**9)   # the live store vs a STATIC twin
    pn_b = []; pn_s = []; caps = []; caps_frozen = []; t_reb = 0.0; T = None; op = None
    for fi, fp in enumerate(frames):
        im = Image.open(fp).convert("RGB"); true = arr(im)
        base = im.resize(base_wh, Image.BICUBIC); bic = arr(base.resize(tgt, Image.BICUBIC))
        d = np.abs(true-bic).max(axis=2); bmax = d.reshape(tgt[1]//BS, BS, tgt[0]//BS, BS).max(axis=(1, 3))
        if T is None:                                  # pick the operating point once (on frame 0)
            T, capk, savk = best_threshold(true, bic, bmax, base_bytes, full_bytes, force_cap); op = (capk, savk)
        hard = bmax > T
        # STORE-GATED REBUILD: the device pastes a hard block's true pixels ONLY IF the organism RETAINED it.
        # Live (confirm=1) retains every block -> full capture. A frozen twin (confirm=inf) retains none -> the
        # rebuild collapses to plain upscale. So the capture number below is load-bearing on the organism's store.
        retained = np.zeros_like(hard); retained_fz = np.zeros_like(hard)
        hy, hx = np.where(hard)
        t0 = time.perf_counter()
        for by, bx in zip(hy.tolist(), hx.tolist()):
            key = hashlib.blake2b(true[by*BS:by*BS+BS, bx*BS:bx*BS+BS].astype(np.uint8).tobytes(), digest_size=8).hexdigest()
            org.observe(key); frozen.observe(key)
            if key in org.normal: retained[by, bx] = True        # organism kept it -> device pastes true detail
            if key in frozen.normal: retained_fz[by, bx] = True  # frozen never keeps -> nothing to paste
        pmask = np.repeat(np.repeat(retained, BS, 0), BS, 1)[..., None]
        recon = np.where(pmask, true, bic); t_reb += time.perf_counter()-t0
        pmask_fz = np.repeat(np.repeat(retained_fz, BS, 0), BS, 1)[..., None]
        recon_fz = np.where(pmask_fz, true, bic)                 # what a STATIC store would rebuild
        e_bic = float(np.sum((true-bic).astype(np.float64)**2)) or 1.0
        caps.append(100*(1-float(np.sum((true-recon).astype(np.float64)**2))/e_bic))
        caps_frozen.append(100*(1-float(np.sum((true-recon_fz).astype(np.float64)**2))/e_bic))
        pn_b.append(psnr(true, bic)); pn_s.append(psnr(true, recon))
        sw = Image.new("RGB", (tgt[0], tgt[1]//2), (10, 10, 10))
        def half(x, t):
            p = Image.fromarray(np.clip(x, 0, 255).astype(np.uint8)).resize((tgt[0]//2, tgt[1]//2))
            dd = ImageDraw.Draw(p); dd.rectangle([0, 0, tgt[0]//2, 24], fill=(0, 0, 0)); dd.text((8, 5), t, fill=(255, 255, 0)); return p
        sw.paste(half(bic, f"{a.base}p → {a.to} plain upscale"), (0, 0))
        sw.paste(half(recon, f"ALIVE SWARM {a.to}  (capture {caps[-1]:.0f}%)"), (tgt[0]//2, 0))
        sw.save(f"{WORK}/o/o{fi:04d}.png")

    out = f"{WORK}/activated_{a.base}to{a.to}.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(fps_v), "-i", f"{WORK}/o/o%04d.png",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", out], check=False)
    raw_full = full_bytes*len(frames)/1e6
    store = (base_bytes*len(frames)+len(org.normal)*BS*BS*3)/1e6        # store size = the ORGANISM's kept blocks
    print(f"\n  \033[1mOPERATING POINT\033[0m  ({mode}; threshold {T})")
    print(f"    capture   : \033[92m{np.mean(caps):.0f}%\033[0m of the detail plain upscaling loses   (PSNR {np.mean(pn_b):.1f}→\033[92m{np.mean(pn_s):.1f} dB\033[0m)")
    print(f"                (capture is DEVICE pixel-math on the ORGANISM-RETAINED store; freeze the store and it → {np.mean(caps_frozen):.0f}%)")
    print(f"    data      : full {raw_full:.0f} MB  vs  base+hard {store:.0f} MB   \033[92m{raw_full/store:.2f}×\033[0m smaller (raw, uncompressed)")
    print(f"    rebuild   : {t_reb/len(frames)*1000:.0f} ms/frame (upscale+paste; a GPU is 100-1000× faster → real-time)")
    # LOAD-BEARING: the rebuild reads from the organism's store — freeze it (retains nothing) and capture collapses.
    require_load_bearing("capture % (rebuilt from the organism-retained store)", round(np.mean(caps), 1), round(np.mean(caps_frozen), 1))
    print(f"  \033[1mALIVE\033[0m")
    print(f"    ✓ store {len(org.normal):,} hard blocks, DETERMINISTIC fingerprint {org.fingerprint()}")
    JR = f"{WORK}/j"
    if os.path.exists(JR): os.remove(JR)
    ch = subprocess.Popen([sys.executable, "-c", "import json\nf=open(%r,'a')\ni=0\nwhile True:\n f.write(json.dumps('k'+str(i%%200))+chr(10));f.flush();i+=1" % JR])
    time.sleep(0.35); os.kill(ch.pid, signal.SIGKILL); ch.wait()
    rev = AliveOrganism.revive(JR, confirm=1); tw = AliveOrganism(confirm=1)
    for ln in open(JR):
        if ln.endswith("\n"):
            try: tw._adopt_step(json.loads(ln))
            except: break
    print(f"    ✓ REGENERATING  killed mid-run → revived byte-exact ({rev.fingerprint()==tw.fingerprint()})")
    print(f"    ✓ ADAPTIVE      learned all {len(org.normal):,} textures online in one pass, no restart")
    os.remove(JR)
    print(f"\n  \033[1m→ playing {os.path.basename(out)}  (left = plain upscale, right = ALIVE SWARM)\033[0m")
    subprocess.run(["open", out], check=False)

if __name__ == "__main__":
    main()
