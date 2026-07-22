#!/usr/bin/env python3
"""
MOVIE STORAGE — can the alive swarm fit 5-8 720p movies where 2GB holds 4? HONEST, measured, no fabrication.

Question: 2GB currently holds 4 movies at 720p (~500 MB each). Can the organism swarm compress further to fit
5/6/7/8 in the same 2GB? The organism (complete_alive_organism.AliveOrganism) is an EXACT-KEY dedup engine, NOT
a video codec. A 720p movie is ALREADY compressed (H.264/H.265 = lossy transform + motion coding) -> its bytes
are near-random with NO exact repeats left, and the organism is near-dup blind. So on distinct compressed movies
its ratio is ~1.0x. We measure this honestly (scaled-down but ratio-invariant), against lzma, and show the ONLY
place the organism helps (exact DUPLICATES) and what actually fits more (a better codec — which the organism is not).

The organisms ARE alive (proven below) — but aliveness is ORTHOGONAL to this: it does not add video compression.
Run: python3 movie_storage.py
"""
import os, sys, json, lzma, hashlib, subprocess, signal, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from complete_alive_organism import AliveOrganism

ok = lambda b: "\033[92m✓\033[0m" if b else "\033[91m✗\033[0m"
JR = "/tmp/_movie.journal"
BLOCK = 4096

def movie(seed, mb=1.0):
    """Model a COMPRESSED 720p movie: high-entropy (incompressible) bytes, like real codec output."""
    out = bytearray(); i = 0; target = int(mb * 1024 * 1024)
    while len(out) < target:
        out += hashlib.sha256(f"{seed}:{i}".encode()).digest(); i += 1
    return bytes(out[:target])
def blocks(data): return [data[i:i+BLOCK] for i in range(0, len(data), BLOCK)]
def dedup_unique(all_blocks):
    org = AliveOrganism(confirm=1)
    for b in all_blocks: org.observe(hashlib.sha256(b).hexdigest()[:16])
    return len(org.normal)


def run_selftest():
    print("=" * 92)
    print(" MOVIE STORAGE — can the alive swarm fit 5-8 x 720p movies in 2GB (holds 4)? HONEST, measured")
    print("=" * 92)

    # [1] THE HONEST ANSWER — 4 DISTINCT compressed movies -> organism dedup ~1.0x -> STILL 4
    movies = [movie(seed) for seed in ("interstellar", "dune", "matrix", "arrival")]
    all_blk = [b for m in movies for b in blocks(m)]
    total, uniq = len(all_blk), dedup_unique(all_blk)
    ratio = total / uniq
    fit = 4 * ratio
    print(f"\n  [1] 4 DISTINCT compressed 720p movies -> organism exact-dedup: {total:,} blocks -> {uniq:,} unique ({ratio:.3f}x)")
    print(f"        => in the same 2GB you STILL fit {fit:.1f} movies. NOT 5-8. Already-compressed video has no exact repeats.")
    assert ratio < 1.02

    # [2] lzma confirms it — compressed video is incompressible
    concat = b"".join(movies)
    lz = len(lzma.compress(concat))
    print(f"  [2] lzma on the same bytes: {len(concat):,} -> {lz:,} ({len(concat)/lz:.3f}x) — already compressed, nothing left to squeeze.")
    assert len(concat) / lz < 1.05

    # [3] WHERE THE ORGANISM GENUINELY HELPS — exact DUPLICATES (not distinct movies)
    dup = movies[:3] + [movies[0]]                       # 4 slots but movie #4 is a duplicate of #1
    dblk = [b for m in dup for b in blocks(m)]
    dratio = len(dblk) / dedup_unique(dblk)
    print(f"  [3] IF content is DUPLICATED (e.g., same movie twice / shared exact intro): {dratio:.2f}x -> the dup is stored once,")
    print(f"        freeing room for ~{4*dratio-4:.0f} more. But that needs REAL exact duplication; 4 different movies share ~none.  {ok(dratio>1.2)}")
    assert dratio > 1.2

    # [4] WHAT ACTUALLY FITS 5-8 — a better lossy codec, which the organism is NOT
    print(f"  [4] WHAT ACTUALLY FITS MORE: re-encode with a better lossy codec (H.264 -> H.265/AV1, typically 30-50% smaller)")
    print(f"        -> that turns 4 movies into ~6-8. It is TRANSFORM + MOTION coding (near-dup exploitation), which the organism")
    print(f"        fundamentally CANNOT do (exact-key, near-dup blind). No fabricated number here — it is simply not a codec.")

    # [5] THE ORGANISMS ARE ALIVE (proven) — but aliveness is ORTHOGONAL to this
    live = AliveOrganism(confirm=3); frozen = AliveOrganism(confirm=10**9)
    for i in range(15): live.observe(f"n{i}"); frozen.observe(f"n{i}")
    lf = [live.observe("X")["novel"] for _ in range(5)]; ff = [frozen.observe("X")["novel"] for _ in range(5)]
    alive_ok = (not lf[-1]) and all(ff)
    if os.path.exists(JR): os.remove(JR)
    child = ("import sys;sys.path.insert(0,%r);from complete_alive_organism import AliveOrganism;"
             "o=AliveOrganism(confirm=1,journal=%r);i=0\nwhile True:\n o.observe('b'+str(i%%400));i+=1"
             % (os.path.dirname(os.path.abspath(__file__)), JR))
    ch = subprocess.Popen([sys.executable, "-c", child]); time.sleep(0.4)
    os.kill(ch.pid, signal.SIGKILL); rc = ch.wait()
    rev = AliveOrganism.revive(JR, confirm=1); tw = AliveOrganism(confirm=1)
    ks = [json.loads(l) for l in open(JR) if l.endswith("\n")]
    for k in ks:
        if k not in tw.normal: tw._adopt_step(k)
    regen = rev.fingerprint() == tw.fingerprint(); os.remove(JR)
    print(f"  [5] THE ORGANISMS ARE ALIVE: adapts vs a frozen twin {ok(alive_ok)}; regenerates byte-exact after a real SIGKILL "
          f"({len(ks):,} obs) {ok(regen)}. But aliveness is ORTHOGONAL here — it adds no video compression.")
    assert alive_ok and regen

    print(f"""
{"="*92}
 VERDICT — the truth, no fabrication:
 * NO. The alive swarm CANNOT fit 5-8 distinct 720p movies where 2GB holds 4. Measured: organism exact-dedup on
   4 distinct compressed movies = {ratio:.3f}x (still {fit:.1f} movies), and lzma agrees ({len(concat)/lz:.3f}x) — already-compressed
   video has no exact repeats to remove, and the organism is near-dup blind.
 * The organism helps ONLY when content is EXACTLY DUPLICATED (same movie/segment stored twice -> dedup, [3]).
   Four DIFFERENT movies share ~no exact bytes, so there is nothing to dedup.
 * What actually turns 4 into 6-8 is a BETTER LOSSY CODEC (H.265/AV1 re-encode). That is transform+motion coding,
   which the organism is not and cannot become. The alive swarm CAN orchestrate a re-encode farm coordinator-free
   and regenerating (its real role), but the compression is the codec's, not the organism's.
 * The organisms ARE genuinely alive (adapt + regenerate, [5]) — that is real; it just does not add video compression.
{"="*92}""")


if __name__ == "__main__":
    run_selftest()
