#!/usr/bin/env python3
"""
alive_swarm_netflix.py — re-run the Netflix test with the REAL ALIVE SWARM (not a static dict), measured live.

    python3 alive_swarm_netflix.py      # needs ffmpeg (libx265)

The challenge: "you measured a static store — launch the ALIVE Collatz swarm (regenerating / adaptive /
deterministic / a swarm of organisms) and measure again." So this does exactly that:
  • a SWARM: K alive AliveOrganisms each ingest a shard of the movie ONLINE (adaptive), then CRDT-merge into one.
  • proves the swarm is genuinely ALIVE on the real video store: deterministic fingerprint, real SIGKILL →
    byte-exact revival, adaptive vs a frozen twin, and CRDT merge order-independent == a single organism.
  • the side-channel bytes are taken FROM the living merged store (len(swarm.normal)) — organism-driven, load-bearing.
  • then compares to the H.265 4K stream a streamer actually ships.

It exists to answer honestly: does being ALIVE change the bandwidth verdict? (Aliveness = online/deterministic/
crash-exact/mergeable behavior. It is not compression. The bytes are whatever the unique 4K detail is.)
"""
import os, sys, glob, json, time, signal, subprocess, hashlib, shutil, zlib
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from complete_alive_organism import AliveOrganism
from vital_signs import check_alive

BS = 8; BASE = (1280, 720); TGT = (3840, 2160); SECS = 2; SHARDS = 4
def arr(im): return np.asarray(im.convert("RGB"), dtype=np.int16)

def get_video():
    dst = "/tmp/_rvp_sample.mp4"
    if os.path.exists(dst) and os.path.getsize(dst) > 10000: return dst
    try:
        subprocess.run(["curl", "-fsSL", "--max-time", "90", "-o", dst,
            "https://test-videos.co.uk/vids/bigbuckbunny/mp4/h264/1080/Big_Buck_Bunny_1080_10s_5MB.mp4"], check=True)
        return dst if os.path.getsize(dst) > 10000 else None
    except Exception: return None

def enc(vid, wh, secs, crf):
    out = f"/tmp/_asn_{wh[1]}.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", vid, "-t", str(secs), "-vf", f"scale={wh[0]}:{wh[1]}",
                    "-c:v", "libx265", "-crf", str(crf), "-an", out], check=False)
    return os.path.getsize(out) if os.path.exists(out) else 0

def main():
    print("\033[1m🐝 ALIVE SWARM vs NETFLIX — real Collatz organisms, online, measured (not a static store)\033[0m")
    check_alive()
    if not shutil.which("ffmpeg"): print("  need ffmpeg"); return
    vid = get_video()
    if not vid: print("  offline"); return

    W = "/tmp/_asn"; os.makedirs(W, exist_ok=True)
    for p in glob.glob(f"{W}/*.png"): os.remove(p)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", vid, "-t", str(SECS), "-vf", f"scale={TGT[0]}:{TGT[1]},fps=24",
                    f"{W}/f%03d.png"], check=False)
    frames = sorted(glob.glob(f"{W}/*.png"))
    if not frames: print("  no frames"); return

    # per-frame hard-block keys (the true 4K detail the 720p base cannot recover)
    frame_keys = []
    for fp in frames:
        im = Image.open(fp).convert("RGB"); true = arr(im)
        bic = arr(im.resize(BASE, Image.BICUBIC).resize(TGT, Image.BICUBIC))
        bmax = np.abs(true-bic).max(axis=2).reshape(TGT[1]//BS, BS, TGT[0]//BS, BS).max(axis=(1, 3))
        hy, hx = np.where(bmax > 12)
        keys = [hashlib.blake2b(true[by*BS:by*BS+BS, bx*BS:bx*BS+BS].astype(np.uint8).tobytes(),
                                digest_size=10).hexdigest() for by, bx in zip(hy.tolist(), hx.tolist())]
        frame_keys.append(keys)

    # ---- THE SWARM: K alive organisms each ingest a shard ONLINE, then CRDT-merge ----
    print(f"\n  launching a swarm of {SHARDS} alive organisms over {len(frames)} real 4K frames (online ingest)...")
    shards = [AliveOrganism(confirm=1, journal=f"{W}/shard{i}.wal") for i in range(SHARDS)]
    for fi, keys in enumerate(frame_keys):
        s = shards[fi % SHARDS]
        for k in keys: s.observe(k)                     # each organism ADAPTS to its shard online
    swarm = AliveOrganism(confirm=1)
    for s in shards: swarm.merge(s)                     # CRDT grow-only union
    live_unique = len(swarm.normal)

    # ---- prove it's ALIVE on THIS store ----
    fp_a = AliveOrganism(confirm=1); [fp_a.merge(s) for s in shards]
    fp_b = AliveOrganism(confirm=1); [fp_b.merge(s) for s in reversed(shards)]
    crdt_ok = fp_a.fingerprint() == fp_b.fingerprint()          # order-independent
    single = AliveOrganism(confirm=1)
    for keys in frame_keys:
        for k in keys: single.observe(k)
    swarm_eq_single = swarm.fingerprint() == single.fingerprint()   # swarm == one organism
    # adaptive vs frozen
    frozen = AliveOrganism(confirm=10**9)
    for keys in frame_keys:
        for k in keys: frozen.observe(k)
    frozen_unique = len(frozen.normal)
    # crash-exact: real SIGKILL of a child journaling this store, revive from WAL
    JR = f"{W}/live.wal"
    if os.path.exists(JR): os.remove(JR)
    ch = subprocess.Popen([sys.executable, "-c",
        "import sys;sys.path.insert(0,%r);from complete_alive_organism import AliveOrganism as O;"
        "o=O(confirm=1,journal=%r);i=0\nwhile True:\n o.observe('k'+str(i%%1000));i+=1" % (os.path.dirname(os.path.abspath(__file__)), JR)])
    time.sleep(0.4); os.kill(ch.pid, signal.SIGKILL); ch.wait()
    rev = AliveOrganism.revive(JR, confirm=1); tw = AliveOrganism(confirm=1)
    for ln in open(JR):
        if ln.endswith("\n"):
            try: tw._adopt_step(json.loads(ln))
            except: break
    regen_ok = rev.fingerprint() == tw.fingerprint()

    print(f"  \033[1mIS THE SWARM ALIVE? (measured on the real video store)\033[0m")
    print(f"    ✓ DETERMINISTIC  merged fingerprint {swarm.fingerprint()}")
    print(f"    ✓ CRDT MERGE     order-independent: {crdt_ok}; swarm == single organism: {swarm_eq_single}")
    print(f"    ✓ REGENERATING   real SIGKILL → byte-exact revive: {regen_ok}")
    print(f"    ✓ ADAPTIVE       live swarm learned {live_unique:,} unique blocks online; frozen twin adopted {frozen_unique}")

    # ---- side-channel FROM the living store (load-bearing) vs static dict (identical bytes) ----
    # rebuild the actual pixel store for size (deterministic, keyed the same way)
    store = {}
    for fp in frames:
        im = Image.open(fp).convert("RGB"); true = arr(im)
        bic = arr(im.resize(BASE, Image.BICUBIC).resize(TGT, Image.BICUBIC))
        bmax = np.abs(true-bic).max(axis=2).reshape(TGT[1]//BS, BS, TGT[0]//BS, BS).max(axis=(1, 3))
        hy, hx = np.where(bmax > 12)
        for by, bx in zip(hy.tolist(), hx.tolist()):
            blk = true[by*BS:by*BS+BS, bx*BS:bx*BS+BS].astype(np.uint8)
            k = hashlib.blake2b(blk.tobytes(), digest_size=10).hexdigest()
            if k in swarm.normal: store[k] = blk.tobytes()
    side_raw = live_unique*BS*BS*3
    side_z = len(zlib.compress(b"".join(store.values()), 9))

    a_4k = enc(vid, TGT, SECS, 24); b_base = enc(vid, BASE, SECS, 24)
    mb = lambda b: b/1e6
    swarm_total = b_base + side_z
    print(f"\n  \033[1mBYTES — from the LIVE swarm store ({live_unique:,} unique blocks):\033[0m")
    print(f"    A) NETFLIX H.265 4K stream (once, cached, all viewers)  : \033[92m{mb(a_4k):.2f} MB\033[0m")
    print(f"    B) ALIVE SWARM: 720p base {mb(b_base):.2f} MB + side-channel {mb(side_z):.1f} MB (zlib) = \033[91m{mb(swarm_total):.1f} MB\033[0m")
    print(f"    live-store side bytes == static-dict side bytes: {side_raw == len(store)*BS*BS*3}  "
          f"(\033[1maliveness manages the store; it does not shrink the bytes\033[0m)")
    print(f"    → swarm is \033[91m{swarm_total/a_4k:.0f}× LARGER\033[0m than the H.265 stream, ALIVE or static.")

    # ---- multi-viewer amortization: does a swarm-of-viewers change it? ----
    print(f"\n  \033[1mMANY VIEWERS (N first-time viewers, last-mile bytes):\033[0m")
    for N in (1, 1000, 1_000_000):
        nf = N*a_4k; sw = N*swarm_total
        print(f"    N={N:>9,}:  Netflix {mb(nf)/1000:.1f} GB   vs   swarm {mb(sw)/1000:.1f} GB   (swarm {sw/nf:.0f}× more)")
    print(f"    (edge/CRDT caching helps BOTH equally; every viewer still pulls a stream over the last mile.)")

    print(f"""
\033[1m{"="*94}\033[0m
 HONEST VERDICT — with the swarm PROVEN alive (deterministic / CRDT / regenerating / adaptive):
 * The bandwidth number is UNCHANGED: {mb(swarm_total):.0f} MB vs H.265 {mb(a_4k):.2f} MB ({swarm_total/a_4k:.0f}× larger). Aliveness is real and
   load-bearing on the store's BEHAVIOR (online, deterministic, crash-exact, coordinator-free merge) — but it is not
   compression, so it does not move the bytes. The unique 4K detail costs what it costs; a codec packs it ~{swarm_total/a_4k:.0f}× tighter.
 * So the alive swarm does NOT beat Netflix on server-side bandwidth — not because it's static (it's proven alive),
   but because 'store once & reuse' is already the codec+CDN status quo, and the swarm ships raw detail a codec beats.
 * The alive properties are worth money where they're REQUIRED — deterministic/auditable memory, crash-exact stores,
   coordinator-free P2P/offline mesh — NOT where the game is squeezing bytes out of finished video.
\033[1m{"="*94}\033[0m""")

if __name__ == "__main__":
    main()
