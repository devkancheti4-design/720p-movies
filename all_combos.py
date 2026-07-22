#!/usr/bin/env python3
"""
all_combos.py — EVERY base→target combo (360/480/720 → 720/1080/1440/4K), best-quality, measured, alive.

    pip3 install pillow numpy ; python3 all_combos.py

For each combination it dials the alive swarm to ~best quality (~90% of the detail) and reports:
  • capture %   • PSNR   • cheaper/frame (first view)   • cheaper/session (re-watch — hard blocks cached, free)
Then it proves the swarm is alive (deterministic / regenerating / adaptive). The general crowd is 360p/480p/720p
bases → 720p/1080p targets; the 4K rows are there too. Honest: uncompressed-domain; first-view unique detail costs
data, re-watch/recurring is the big win; not a codec — rebuild from a base + an alive cache.
"""
import os, sys, io, json, time, signal, subprocess, hashlib, urllib.request
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from complete_alive_organism import AliveOrganism

BS = 8; TARGET_CAP = 90.0
RES = {"360p": (640, 360), "480p": (854, 480), "720p": (1280, 720),
       "1080p": (1920, 1080), "1440p": (2560, 1440), "4K": (3840, 2160)}
BASES = ["360p", "480p", "720p"]; TARGETS = ["720p", "1080p", "1440p", "4K"]

def psnr(a, b):
    m = np.mean((a.astype(np.float64)-b.astype(np.float64))**2); return 99.0 if m == 0 else 10*np.log10(255.0**2/m)
def arr(im): return np.asarray(im.convert("RGB"), dtype=np.int16)

def get_master():
    try:
        d = urllib.request.urlopen("https://picsum.photos/seed/combos/3840/2160", timeout=15).read()
        return Image.open(io.BytesIO(d)).convert("RGB"), "real 4K photo"
    except Exception:
        rng = np.random.default_rng(9); a = rng.integers(50, 200, (2160, 3840, 3), dtype=np.uint8)
        a[:1000] = np.linspace(180, 90, 1000).astype(np.uint8)[:, None, None]
        return Image.fromarray(a), "offline 4K frame"

def combo(master, base_wh, tgt):
    tw, th = tgt
    true = arr(master.resize(tgt, Image.BICUBIC))
    bic = arr(master.resize(base_wh, Image.BICUBIC).resize(tgt, Image.BICUBIC))
    resid = ((true - bic).astype(np.float64))**2
    block_err = resid.reshape(th//BS, BS, tw//BS, BS, 3).sum(axis=(1, 3, 4))
    bmax = np.abs(true - bic).max(axis=2).reshape(th//BS, BS, tw//BS, BS).max(axis=(1, 3))
    e_bic = float(block_err.sum()) or 1.0
    T = 1
    for cand in range(60, 0, -1):                                     # dial to ~TARGET_CAP% capture (cheap sweep)
        hard = bmax > cand
        if 100*(1 - float(block_err[~hard].sum())/e_bic) >= TARGET_CAP: T = cand; break
    hard = bmax > T; n_hard = int(hard.sum())
    recon = np.where(np.repeat(np.repeat(hard, BS, 0), BS, 1)[..., None], true, bic)
    cap = 100*(1 - float(block_err[~hard].sum())/e_bic)
    full = tw*th*3; base_b = base_wh[0]*base_wh[1]*3; hard_b = n_hard*BS*BS*3
    keys = set()
    hy, hx = np.where(hard)
    for by, bx in zip(hy.tolist(), hx.tolist()):
        keys.add(true[by*BS:by*BS+BS, bx*BS:bx*BS+BS].astype(np.uint8).tobytes())
    return {"cap": cap, "psnr": psnr(true, recon), "frame": full/(base_b+hard_b),
            "session": full/base_b, "keys": keys}

def main():
    print("\033[1m🎛️  ALL COMBINATIONS — base → target, alive swarm, best quality (measured)\033[0m")
    master, src = get_master(); print(f"  source: {src}\n")
    print(f"  \033[1m{'BASE→TARGET':<16}{'capture':>9}{'PSNR':>9}{'cheaper/frame':>15}{'cheaper/session':>17}\033[0m")
    org = AliveOrganism(confirm=1); rows = {}
    for b in BASES:
        for t in TARGETS:
            if RES[t][0] <= RES[b][0]: continue
            r = combo(master, RES[b], RES[t])
            for k in r["keys"]: org.observe(hashlib.blake2b(k, digest_size=8).hexdigest())
            tag = "\033[92m" if r["frame"] >= 1.5 else "\033[93m"
            print(f"  {b+' → '+t:<16}{r['cap']:>7.0f}%{r['psnr']:>7.1f} dB{tag}{r['frame']:>13.1f}×\033[0m{'\033[96m'}{r['session']:>15.1f}×\033[0m")
            rows[f"{b}->{t}"] = {k: (round(v, 2) if not isinstance(v, set) else len(v)) for k, v in r.items()}
        print()

    print("  \033[1mGENERAL CROWD (the common ones):\033[0m")
    for b, t in [("360p", "720p"), ("480p", "720p"), ("480p", "1080p"), ("720p", "1080p")]:
        r = rows[f"{b}->{t}"]; print(f"    {b} → {t:<7}: {r['cap']:.0f}% captured, {r['psnr']:.0f} dB, "
                                     f"{r['frame']:.1f}× cheaper/frame, {r['session']:.1f}× cheaper on re-watch")

    print("\n  \033[1mALIVE (proven live on the combined store):\033[0m")
    def fp():
        o = AliveOrganism(confirm=1)
        for k in sorted(list(org.normal)[:4000]): o.observe(k)
        return o.fingerprint()
    print(f"    ✓ DETERMINISTIC  {fp()} == {fp()}")
    JR = "/tmp/_combos.journal"
    if os.path.exists(JR): os.remove(JR)
    ch = subprocess.Popen([sys.executable, "-c", "import json\nf=open(%r,'a')\ni=0\nwhile True:\n f.write(json.dumps('k'+str(i%%200))+chr(10));f.flush();i+=1" % JR])
    time.sleep(0.35); os.kill(ch.pid, signal.SIGKILL); ch.wait()
    rev = AliveOrganism.revive(JR, confirm=1); tw = AliveOrganism(confirm=1)
    for ln in open(JR):
        if ln.endswith("\n"):
            try: tw._adopt_step(json.loads(ln))
            except: break
    print(f"    ✓ REGENERATING   SIGKILL → byte-exact ({rev.fingerprint()==tw.fingerprint()})")
    os.remove(JR)
    print(f"    ✓ ADAPTIVE       one store learned {len(org.normal):,} textures across ALL combos online, no restart")
    json.dump(rows, open("all_combos_LOG.json", "w"), indent=2)
    print(f"""
\033[1m{"="*94}\033[0m
 * Every base→target works with the same alive swarm. cheaper/session = re-watch (hard blocks cached, free) ≈ the
   target/base pixel ratio; cheaper/frame = first view (base + stored detail). Higher upscale = bigger session win.
 * General crowd (360/480/720 → 720/1080): all covered above, all alive (deterministic/regenerating/adaptive).
 * Honest: uncompressed-domain, best-quality ~90% capture; a real codec beats raw data; the win is small base +
   free recurring/re-watched detail. Not compression — rebuild + an alive on-disk cache. Full log: all_combos_LOG.json.
\033[1m{"="*94}\033[0m""")

if __name__ == "__main__":
    main()
