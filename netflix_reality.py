#!/usr/bin/env python3
"""
netflix_reality.py — the HONEST Netflix test: does the swarm save a streamer bandwidth vs what they ship TODAY?

    python3 netflix_reality.py      # needs ffmpeg (with libx265). Auto-uses the sample video.

The seductive pitch: "a popular movie is re-watched millions of times, so store the 4K detail ONCE and reuse it —
huge server-side saving." The catch this script exposes: Netflix ALREADY encodes a movie ONCE, edge-caches it, and
serves the SAME compressed bytes to every viewer. "Store once, serve many" is the status quo. So the real question
is NOT swarm-vs-raw (where the swarm looks great) but swarm-vs-the-codec-stream-they-actually-ship.

It measures, on a real 4K segment:
  A) NETFLIX TODAY  : an H.265 4K encode (what one cached stream costs; encoded once, reused by everyone).
  B) SWARM          : a small H.265 base + the hard-block side-channel needed to rebuild ~4K.
If B >= A, the swarm SAVES NOTHING server-side — it re-invents encode-once-cache-serve, but with an uncompressed
side-channel a codec already beats. Reports the honest verdict either way.
"""
import os, sys, glob, subprocess, hashlib, shutil
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from complete_alive_organism import AliveOrganism
from vital_signs import check_alive

BS = 8; BASE = (1280, 720); TGT = (3840, 2160); SECS = 2
def arr(im): return np.asarray(im.convert("RGB"), dtype=np.int16)

def get_video():
    dst = "/tmp/_rvp_sample.mp4"
    if os.path.exists(dst) and os.path.getsize(dst) > 10000: return dst
    try:
        subprocess.run(["curl", "-fsSL", "--max-time", "90", "-o", dst,
            "https://test-videos.co.uk/vids/bigbuckbunny/mp4/h264/1080/Big_Buck_Bunny_1080_10s_5MB.mp4"], check=True)
        return dst if os.path.getsize(dst) > 10000 else None
    except Exception: return None

def enc(vid, wh, secs, crf, extra=()):
    out = f"/tmp/_nfx_{wh[1]}.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", vid, "-t", str(secs), "-vf", f"scale={wh[0]}:{wh[1]}",
                    "-c:v", "libx265", "-crf", str(crf), "-an", *extra, out], check=False)
    return os.path.getsize(out) if os.path.exists(out) else 0

def main():
    print("\033[1m🎬 NETFLIX REALITY — does the swarm beat the codec stream they ACTUALLY ship? (real video)\033[0m")
    check_alive()
    if not shutil.which("ffmpeg"): print("  need ffmpeg: brew install ffmpeg"); return
    vid = get_video()
    if not vid: print("  offline — need the sample"); return

    # A) what NETFLIX ships today: one H.265 4K stream (encoded ONCE, edge-cached, served to millions)
    a_4k = enc(vid, TGT, SECS, 24)
    # B) the swarm alternative: a small H.265 720p base + the hard-block side-channel
    b_base = enc(vid, BASE, SECS, 24)

    # side-channel: the true 4K hard blocks the base can't recover (uncompressed true pixels; that's what must ship)
    W = "/tmp/_nfx"; os.makedirs(W, exist_ok=True)
    for p in glob.glob(f"{W}/*.png"): os.remove(p)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", vid, "-t", str(SECS), "-vf", f"scale={TGT[0]}:{TGT[1]},fps=24",
                    f"{W}/f%03d.png"], check=False)
    frames = sorted(glob.glob(f"{W}/*.png"))
    org = AliveOrganism(confirm=1); store = {}
    for fp in frames:
        im = Image.open(fp).convert("RGB"); true = arr(im)
        bic = arr(im.resize(BASE, Image.BICUBIC).resize(TGT, Image.BICUBIC))
        bmax = np.abs(true-bic).max(axis=2).reshape(TGT[1]//BS, BS, TGT[0]//BS, BS).max(axis=(1, 3))
        hy, hx = np.where(bmax > 12)
        for by, bx in zip(hy.tolist(), hx.tolist()):
            blk = true[by*BS:by*BS+BS, bx*BS:bx*BS+BS].astype(np.uint8)
            k = hashlib.blake2b(blk.tobytes(), digest_size=10).hexdigest()
            org.observe(k)
            if k not in store: store[k] = blk.tobytes()
    side_raw = len(store)*BS*BS*3
    # be generous to the swarm: try to compress the side-channel losslessly (it's true pixels -> compresses poorly)
    import zlib
    side_z = len(zlib.compress(b"".join(store.values()), 9))

    mb = lambda b: b/1e6
    print(f"\n  real 4K segment: {len(frames)} frames ({SECS}s at {TGT[0]}×{TGT[1]})\n")
    print(f"  \033[1mA) NETFLIX TODAY — one H.265 4K stream (encoded once, cached, served to all):\033[0m  \033[92m{mb(a_4k):.2f} MB\033[0m")
    print(f"  \033[1mB) SWARM — H.265 720p base + hard-block side-channel:\033[0m")
    print(f"       720p base (H.265)         : {mb(b_base):.2f} MB")
    print(f"       side-channel (raw pixels) : {mb(side_raw):.1f} MB   ({len(store):,} unique 4K hard blocks)")
    print(f"       side-channel (zlib'd)     : {mb(side_z):.1f} MB   (true pixels barely compress)")
    swarm_total = b_base + side_z
    print(f"       \033[1mswarm total (base + zlib side)\033[0m : \033[91m{mb(swarm_total):.1f} MB\033[0m")

    ratio = swarm_total / a_4k if a_4k else 0
    verdict_win = swarm_total < a_4k
    print(f"\n  \033[1mVERDICT\033[0m")
    if verdict_win:
        print(f"    swarm {mb(swarm_total):.1f} MB  <  Netflix's H.265 4K {mb(a_4k):.2f} MB  → it WOULD save (surprising — re-check).")
    else:
        print(f"    swarm {mb(swarm_total):.1f} MB  is  \033[91m{ratio:.0f}× LARGER\033[0m than Netflix's H.265 4K stream ({mb(a_4k):.2f} MB).")
        print(f"    → \033[91mNO server-side saving.\033[0m Netflix already encodes ONCE + edge-caches + serves the same")
        print(f"      compressed bytes to millions. The swarm's 'store once, re-watch free' is that SAME idea — but")
        print(f"      its side-channel is uncompressed true pixels, which a codec (H.265/AV1) already beats by {ratio:.0f}×.")
    print(f"""
\033[1m{"="*94}\033[0m
 HONEST BOTTOM LINE (Netflix / any streamer, server side):
 * "Store the movie once, reuse on millions of re-watches" is NOT a new saving — it is exactly what encode-once +
   CDN edge-cache already does. Every viewer already streams the same cached compressed file.
 * The swarm's re-watch multiples (9x, 36x) are measured vs RAW uncompressed video, which nobody ships. Against the
   H.265/AV1 stream they DO ship, the base + hard-block side-channel is far larger (measured above).
 * So the server-side Netflix pitch does not hold. Where the alive swarm is genuinely different is NOT compression:
   it's determinism, bit-exact crash-recovery, and coordinator-free (CRDT) peer sharing — sell those, not bandwidth.
\033[1m{"="*94}\033[0m""")

if __name__ == "__main__":
    main()
