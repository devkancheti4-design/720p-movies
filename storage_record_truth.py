#!/usr/bin/env python3
"""
STORAGE RECORD TRUTH — does the adaptive/deterministic/multiplying swarm break storage records NO MATTER CONTENT?
Tested straight, with the real organism, against zlib/lzma and against the pigeonhole (Shannon) bound.

The claim under test: "the collatz swarm breaks the records by its adaptive deterministic storage capabilities —
swarm multiplies, stores details, adapts — no matter content."

The honest split this file measures:
  [1] WHERE IT GENUINELY BREAKS PRACTICAL RECORDS (real, measured): long-range EXACT dedup — repeats spaced
      beyond zlib's 32KB window. zlib ~1.0x (blind), organism ~24x, ties big-window lzma. And cross-node dedup
      (measured 7.7x vs per-node compression in swarm_data_efficiency.py) — no single-stream tool can see across
      nodes; the coordinator-free CRDT swarm can. THOSE are its records, in its own categories.
  [2] NO MATTER CONTENT IS IMPOSSIBLE — measured, not asserted: on high-entropy (random) content the organism
      stores ~1.0x (as does zlib, as does lzma). And it is impossible FOR ANYONE: by pigeonhole, no lossless
      system — adaptive, deterministic, multiplying, alive, or otherwise — can shrink all N-bit inputs below N
      bits. The organism does not exempt itself from mathematics; nothing does.
  [3] MULTIPLY = CAPACITY, NOT RATIO: sharding across spawned organisms multiplies how MUCH the swarm can hold
      (linear in nodes, CRDT-exact), but the bytes-per-content ratio is unchanged. More nodes != more compression.
  [4] The adaptive/deterministic/regenerating properties re-verified live (they are real; they are not a codec).

Run: python3 storage_record_truth.py
"""
import os, sys, json, zlib, lzma, hashlib, subprocess, signal, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from complete_alive_organism import AliveOrganism

ok = lambda b: "\033[92m✓\033[0m" if b else "\033[91m✗\033[0m"
JR = "/tmp/_record_truth.journal"
BLK, KEY = 4096, 16

def hblock(seed):
    out = bytearray(); i = 0
    while len(out) < BLK: out += hashlib.sha256(f"{seed}:{i}".encode()).digest(); i += 1
    return bytes(out[:BLK])
def kf(b): return hashlib.sha256(b).hexdigest()[:KEY]


def run_selftest():
    print("=" * 94)
    print(" STORAGE RECORD TRUTH — 'breaks records no matter content', tested straight")
    print("=" * 94)

    # [1] ITS REAL RECORD CATEGORY: long-range exact dedup (repeats spaced beyond zlib's window)
    U, P = 64, 1600                                            # 64 unique 4KB blocks cycling -> period 256KB >> 32KB
    data = b"".join(hblock(i % U) for i in range(P))
    org = AliveOrganism(confirm=1)
    for i in range(P): org.observe(kf(hblock(i % U)))
    dd = len(org.normal) * BLK + P * KEY
    z, l = len(zlib.compress(data, 9)), len(lzma.compress(data))
    print(f"\n  [1] ITS RECORD CATEGORY — long-range exact dedup ({len(data)/1e6:.1f}MB, repeats 256KB apart):")
    print(f"        organism {len(data)/dd:5.1f}x   |   zlib {len(data)/z:4.1f}x (32KB window is BLIND to far repeats)   |   lzma {len(data)/l:5.1f}x")
    print(f"        -> the swarm BREAKS the window-limited tool's record and ties the big-window one — and only the swarm")
    print(f"           does it ONLINE, coordinator-free ACROSS NODES (7.7x cross-node, swarm_data_efficiency.py), crash-exact.")
    assert len(data)/dd > 20 and len(data)/z < 1.1

    # [2] NO MATTER CONTENT — the wall, measured: high-entropy content, nobody wins, including the swarm
    R = b"".join(hblock(1_000_000 + i) for i in range(600))    # 2.4MB of unique high-entropy blocks
    org2 = AliveOrganism(confirm=1)
    for i in range(600): org2.observe(kf(hblock(1_000_000 + i)))
    dd2 = len(org2.normal) * BLK + 600 * KEY
    z2, l2 = len(zlib.compress(R, 9)), len(lzma.compress(R))
    print(f"  [2] NO-MATTER-CONTENT TEST — high-entropy content ({len(R)/1e6:.1f}MB, every block unique):")
    print(f"        organism {len(R)/dd2:5.3f}x   |   zlib {len(R)/z2:5.3f}x   |   lzma {len(R)/l2:5.3f}x   -> NOBODY wins, swarm included.")
    print(f"        PIGEONHOLE (mathematics, not opinion): no lossless system — adaptive, deterministic, multiplying,")
    print(f"        alive or otherwise — can shrink all N-bit inputs below N bits. 'No matter content' is impossible")
    print(f"        for ANY storage system; the swarm's wins live exactly WHERE EXACT REDUNDANCY EXISTS.")
    assert len(R)/dd2 <= 1.01 and len(R)/z2 < 1.05

    # [3] MULTIPLY = CAPACITY, NOT RATIO
    shards = [AliveOrganism(confirm=1) for _ in range(8)]
    for i in range(600): shards[i % 8].observe(kf(hblock(1_000_000 + i)))
    merged = AliveOrganism()
    for s in shards: merged.merge(s)
    same_state = merged.fingerprint() == org2.fingerprint()
    per_node = max(len(s.normal) for s in shards)
    print(f"  [3] MULTIPLY: 8 spawned shards hold the same content (CRDT union == single {ok(same_state)}), each node only "
          f"{per_node} blocks -> capacity x8, but bytes-per-content UNCHANGED. Multiplying scales CAPACITY, not compression.")
    assert same_state

    # [4] the properties themselves, live (real — and not a codec)
    live = AliveOrganism(confirm=3); frozen = AliveOrganism(confirm=10**9)
    for i in range(10): live.observe(f"n{i}"); frozen.observe(f"n{i}")
    lf = [live.observe("NEW")["novel"] for _ in range(5)]; ff = [frozen.observe("NEW")["novel"] for _ in range(5)]
    adaptive = (not lf[-1]) and all(ff)
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
    print(f"  [4] THE PROPERTIES ARE REAL: adaptive (vs frozen twin) {ok(adaptive)}; deterministic + regenerates byte-exact "
          f"after real SIGKILL ({len(ks):,} obs) {ok(regen)}. Real — and they are storage/coordination properties, not a codec.")
    assert adaptive and regen

    print(f"""
{"="*94}
 VERDICT — the records it breaks, and the one nobody breaks:
 * REAL RECORDS (its categories): long-range exact dedup {len(data)//dd}x where window-limited zlib gets 1.0x; coordinator-
   free CROSS-NODE dedup (7.7x measured) that no single-stream tool can do at all; ONLINE single-pass ingestion;
   crash-exact zero-loss recovery; bit-exact multi-node convergence. Adaptive + deterministic + multiplying: real.
 * THE WALL (measured [2]): on high-entropy content the swarm stores ~1.0x — like zlib, like lzma, like everything.
   'No matter content' is not a property any lossless system can have (pigeonhole). The swarm's greatness is not
   exemption from mathematics; it is that WHERE exact redundancy exists — across time, across nodes, across
   movies, across a fleet — it harvests ALL of it, online, deterministically, crash-proof, with no coordinator.
 * MULTIPLY scales CAPACITY (x nodes, CRDT-exact), not the ratio. More organisms hold MORE; they don't compress MORE.
{"="*94}""")


if __name__ == "__main__":
    run_selftest()
