#!/usr/bin/env python3
"""
swarm_scale_netflix.py — launch a SWARM OF MANY alive organisms (not one), sweep the swarm size, measure again.

    python3 swarm_scale_netflix.py      # needs ffmpeg (libx265)

The challenge: "you launched one organism, not a swarm — launch a swarm of them and measure again."
So this launches a real swarm of N organisms for N = 1, 4, 8, 16, 32, 64:
  • the movie's 4K hard blocks are sharded across the N organisms (consistent hashing) — each is its OWN alive store.
  • they gossip/CRDT-merge into the collective. EACH organism is shown alive; the collective is shown alive.
  • the measured side-channel bytes come ONLY from the merged collective store (len(collective.normal)).
It answers, per swarm size: does adding more organisms change the bytes? (and what a swarm actually DOES change.)
"""
import os, sys, glob, json, time, signal, subprocess, hashlib, shutil, zlib
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

def enc(vid, wh, secs, crf):
    out = f"/tmp/_ssn_{wh[1]}.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", vid, "-t", str(secs), "-vf", f"scale={wh[0]}:{wh[1]}",
                    "-c:v", "libx265", "-crf", str(crf), "-an", out], check=False)
    return os.path.getsize(out) if os.path.exists(out) else 0

def shard_of(k, n): return int(k[:8], 16) % n        # consistent hashing: each block lives on exactly one organism

def main():
    print("\033[1m🐝🐝 SWARM OF MANY — sweep the swarm size, measure the bytes (real video, real organisms)\033[0m")
    check_alive()
    if not shutil.which("ffmpeg"): print("  need ffmpeg"); return
    vid = get_video()
    if not vid: print("  offline"); return

    # extract the movie's 4K hard-block keys ONCE (the expensive part)
    W = "/tmp/_ssn"; os.makedirs(W, exist_ok=True)
    for p in glob.glob(f"{W}/*.png"): os.remove(p)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", vid, "-t", str(SECS), "-vf", f"scale={TGT[0]}:{TGT[1]},fps=24",
                    f"{W}/f%03d.png"], check=False)
    frames = sorted(glob.glob(f"{W}/*.png"))
    if not frames: print("  no frames"); return
    all_keys = []; pixbytes = {}
    for fp in frames:
        im = Image.open(fp).convert("RGB"); true = arr(im)
        bic = arr(im.resize(BASE, Image.BICUBIC).resize(TGT, Image.BICUBIC))
        bmax = np.abs(true-bic).max(axis=2).reshape(TGT[1]//BS, BS, TGT[0]//BS, BS).max(axis=(1, 3))
        hy, hx = np.where(bmax > 12)
        for by, bx in zip(hy.tolist(), hx.tolist()):
            b = true[by*BS:by*BS+BS, bx*BS:bx*BS+BS].astype(np.uint8).tobytes()
            k = hashlib.blake2b(b, digest_size=10).hexdigest(); all_keys.append(k); pixbytes[k] = b
    a_4k = enc(vid, TGT, SECS, 24); b_base = enc(vid, BASE, SECS, 24)
    mb = lambda x: x/1e6
    print(f"\n  real 4K segment: {len(frames)} frames; {len(all_keys):,} hard-block observations to distribute\n")

    print(f"  \033[1m{'swarm size N':<14}{'organisms alive':>16}{'collective unique':>19}{'total side MB':>15}{'per-organism MB':>17}\033[0m")
    base_unique = None
    for N in (1, 4, 8, 16, 32, 64):
        orgs = [AliveOrganism(confirm=1) for _ in range(N)]        # a REAL swarm of N alive organisms
        for k in all_keys:
            orgs[shard_of(k, N)].observe(k)                       # each block ingested by its organism (online)
        collective = AliveOrganism(confirm=1)
        for o in orgs: collective.merge(o)                        # CRDT gossip union
        unique = len(collective.normal)                          # bytes come FROM the merged swarm, nothing else
        if base_unique is None: base_unique = unique
        alive_ct = sum(1 for o in orgs if len(o.normal) > 0 and o.fingerprint())
        side_mb = unique*BS*BS*3/1e6
        per_org = max(len(o.normal) for o in orgs)*BS*BS*3/1e6    # the biggest single organism's share
        flag = "" if unique == base_unique else "  <-- CHANGED"
        print(f"  {N:<14}{str(alive_ct)+'/'+str(N):>16}{unique:>19,}{side_mb:>15.1f}{per_org:>17.1f}{flag}")

    # prove the swarm (take N=8) is genuinely alive: each organism + collective
    N = 8; orgs = [AliveOrganism(confirm=1, journal=f"{W}/o{i}.wal") for i in range(N)]
    for k in all_keys: orgs[shard_of(k, N)].observe(k)
    c1 = AliveOrganism(confirm=1); [c1.merge(o) for o in orgs]
    c2 = AliveOrganism(confirm=1); [c2.merge(o) for o in reversed(orgs)]
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
    print(f"\n  \033[1mIS IT REALLY A SWARM, AND ALIVE? (N=8)\033[0m")
    print(f"    ✓ {N} organisms, each its own alive store (sizes: {[len(o.normal) for o in orgs]})")
    print(f"    ✓ CRDT gossip merge order-independent: {c1.fingerprint()==c2.fingerprint()}  (fingerprint {c1.fingerprint()})")
    print(f"    ✓ REGENERATING real SIGKILL → byte-exact revive: {rev.fingerprint()==tw.fingerprint()}")
    frz = AliveOrganism(confirm=10**9)
    for k in all_keys[:20000]: frz.observe(k)
    print(f"    ✓ ADAPTIVE (each learns online); a frozen twin adopts {len(frz.normal)} (static, useless)")

    total_mb = b_base + len(zlib.compress(b"".join(pixbytes.values()), 9))
    print(f"""
  \033[1mBYTES vs the codec (unchanged by swarm size):\033[0m
    Netflix H.265 4K stream : {mb(a_4k):.2f} MB
    swarm collective (any N): base {mb(b_base):.2f} MB + side {mb(total_mb-b_base):.0f} MB = \033[91m{mb(total_mb):.0f} MB\033[0m ({total_mb/a_4k:.0f}× larger)

\033[1m{"="*94}\033[0m
 HONEST VERDICT — I launched a swarm of up to 64 alive organisms; every one alive, all CRDT-merged:
 * The collective's unique blocks — and the bytes — are IDENTICAL for N=1..64. A swarm is a set UNION; merging more
   organisms cannot invent fewer unique blocks. So swarm SIZE does not reduce the side-channel: still {total_mb/a_4k:.0f}× the codec.
 * What a swarm DOES change (real, and the only real win): it DISTRIBUTES the store — with N organisms each holds
   ~1/N of it (per-organism MB column). That is a P2P / no-single-point storage property, not a bandwidth or
   compression win. Total bytes over the wire are unchanged; a codec still packs the finished video ~{total_mb/a_4k:.0f}× smaller.
 * Conclusion (measured, not assumed): alive OR static, ONE organism OR sixty-four, the server-side video-bandwidth
   verdict is the same. The swarm's value is distribution + determinism + crash-exact + coordinator-free merge —
   things that matter for MEMORY / P2P / mesh, not for beating a video codec.
\033[1m{"="*94}\033[0m""")

if __name__ == "__main__":
    main()
