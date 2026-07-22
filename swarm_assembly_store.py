#!/usr/bin/env python3
"""
SWARM ASSEMBLY STORE — an always-on swarm of alive observers makes it EASY for any device to assemble content.

The honest role (same principle as city_observer, applied to data/media): the organism does NOT compress a movie
(see movie_storage.py). Installed as an always-on swarm across devices, it is a coordinator-free, deduped,
regenerating shared CONTENT STORE + membership index. A device does not re-download or re-compute what the swarm
already holds — it assembles from the shared material and fetches only what is genuinely MISSING. The organism
makes assembly easier; the device does the assembly.

Measured on the real organism (complete_alive_organism.AliveOrganism), self-verifying:
  [1] SHARED STORE dedup: N devices hold overlapping content -> each unique block stored ONCE across the swarm.
  [2] EASY ASSEMBLY: a device assembling a POPULAR item fetches ~0 from origin (the swarm already has it); a RARE
      item still costs full fetch (honest — sharing, not compression).
  [3] REGENERATING / resilient: a device crash loses no material (other holders + byte-exact revive).
  [4] ALIVE: the store ingests NEW content online (a frozen store cannot).

HONEST: the saving is CROSS-DEVICE SHARING (redundancy), NOT per-item compression; unique/rare content gets no
benefit; the organism is exact-key (already-compressed distinct data does not dedup unless shared); and it does
NOT decode/assemble the content — it is the membership + missing-block decider; the device assembles.
Run: python3 swarm_assembly_store.py
"""
import os, sys, json, random, subprocess, signal, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from complete_alive_organism import AliveOrganism
from vital_signs import check_alive

ok = lambda b: "\033[92m✓\033[0m" if b else "\033[91m✗\033[0m"
JR = "/tmp/_assembly.journal"


def run_selftest():
    print("=" * 92)
    print(" SWARM ASSEMBLY STORE — an always-on alive swarm makes it easy for any device to assemble content")
    print("=" * 92)
    check_alive()                     # LAUNCH-TIME LIVENESS: symptoms + abort if the organism went static
    rng = random.Random(9)
    M, N, BLK = 20, 12, 150                                 # 20 content items, 12 devices, 150 blocks/item
    item_blocks = {i: [f"item{i}_blk{j}" for j in range(BLK)] for i in range(M)}
    pop = [1.0/(i+1) for i in range(M)]                     # Zipf popularity: item 0 most popular

    # each device holds a weighted-random subset of items (popular items land on many devices -> overlap)
    devices = []
    for _ in range(N):
        held = set(rng.choices(range(M), weights=pop, k=6))
        org = AliveOrganism(confirm=1)
        for it in held:
            for b in item_blocks[it]: org.observe(b)
        devices.append((held, org))

    # [1] SHARED STORE dedup
    naive_total = sum(len(it_org[1].normal) for it_org in devices)      # sum of each device's stored blocks
    swarm = AliveOrganism()
    for _, org in devices: swarm.merge(org)                             # coordinator-free CRDT union
    swarm_unique = len(swarm.normal)
    print(f"\n  [1] SHARED STORE: {N} devices store {naive_total:,} blocks total (with duplication) -> swarm holds {swarm_unique:,} unique "
          f"({naive_total/swarm_unique:.1f}x less) — a popular item held by many devices is stored ONCE, coordinator-free.")
    assert swarm_unique < naive_total

    # [2] EASY ASSEMBLY — a new device assembles items; it fetches from origin ONLY the blocks the swarm lacks
    from collections import Counter
    held_count = Counter(it for held, _ in devices for it in held)
    popular_item = held_count.most_common(1)[0][0]                     # the actually-most-held item (in the swarm)
    rare_blocks = [f"brand_new_unseen_blk{j}" for j in range(BLK)]     # a fresh item NO device holds
    origin_fetch = lambda blks: sum(1 for b in blks if b not in swarm.normal)
    fp, fr = origin_fetch(item_blocks[popular_item]), origin_fetch(rare_blocks)
    print(f"  [2] EASY ASSEMBLY (a new device wants an item = {BLK} blocks):")
    print(f"        POPULAR item (held by {held_count[popular_item]} devices) -> fetch {fp}/{BLK} from origin "
          f"({(1-fp/BLK)*100:.0f}% assembled from the swarm, ~free)  {ok(fp==0)}")
    print(f"        RARE/new item (held by none) -> fetch {fr}/{BLK} from origin (nothing shared to reuse) — HONEST: sharing helps, uniqueness doesn't.")
    assert fp == 0 and fr == BLK

    # [3] REGENERATING / resilient — a device crash loses no material; the store revives byte-exact
    holders_of_pop = [i for i, (held, _) in enumerate(devices) if popular_item in held]
    survivors = AliveOrganism()
    for i, (_, org) in enumerate(devices):
        if i != holders_of_pop[0]: survivors.merge(org)                # one holder crashes; others still have it
    still_available = all(b in survivors.normal for b in item_blocks[popular_item])
    if os.path.exists(JR): os.remove(JR)
    child = ("import sys;sys.path.insert(0,%r);from complete_alive_organism import AliveOrganism;"
             "o=AliveOrganism(confirm=1,journal=%r);i=0\nwhile True:\n o.observe('blk'+str(i%%500));i+=1"
             % (os.path.dirname(os.path.abspath(__file__)), JR))
    ch = subprocess.Popen([sys.executable, "-c", child]); time.sleep(0.4)
    os.kill(ch.pid, signal.SIGKILL); rc = ch.wait()
    rev = AliveOrganism.revive(JR, confirm=1); tw = AliveOrganism(confirm=1)
    ks = [json.loads(l) for l in open(JR) if l.endswith("\n")]
    for k in ks:
        if k not in tw.normal: tw._adopt_step(k)
    regen = rev.fingerprint() == tw.fingerprint(); os.remove(JR)
    print(f"  [3] RESILIENT: a device holding a popular item crashes -> still fully available from other holders {ok(still_available)}; "
          f"and a node revives byte-exact after a real SIGKILL ({len(ks):,} obs) {ok(regen)} (no re-download).")
    assert still_available and regen

    # [4] ALIVE — the store ingests NEW content online; a frozen store cannot
    alive = AliveOrganism(confirm=1); frozen = AliveOrganism(confirm=10**9)
    a = alive.observe("brand_new_release_blk0")["novel"]; a2 = alive.observe("brand_new_release_blk0")["novel"]
    f0 = [frozen.observe("brand_new_release_blk0")["novel"] for _ in range(3)]
    print(f"  [4] ALIVE: the store ingests a NEW release online (novel={a} then held={not a2}); a frozen store flags it forever "
          f"({sum(f0)}/3, never stores)  {ok(a and not a2 and all(f0))}")
    assert a and not a2 and all(f0)

    print(f"""
{"="*92}
 VERDICT — the swarm makes assembly easier (the honest role, tested):
 * TRUE: an always-on swarm is a coordinator-free, deduped, regenerating shared STORE. {N} devices' {naive_total:,} stored
   blocks collapse to {swarm_unique:,} unique ({naive_total/swarm_unique:.1f}x); a new device assembling a POPULAR item fetches {fp}/{BLK} from
   origin (assembled almost entirely from the swarm), crashes lose no material, and the store ingests new content
   online. That is exactly the city-observer principle applied to data/media.
 * HONEST: this is CROSS-DEVICE SHARING, not compression — a RARE/unique item still costs a full {fr}/{BLK} fetch
   (see [2]), and a single already-compressed movie does not shrink (see movie_storage.py). The organism does NOT
   decode or assemble the content; it is the membership + missing-block decider + regenerating store; the device
   does the computing/assembly. The life just makes it easier — it does not do the codec's or the device's job.
{"="*92}""")


if __name__ == "__main__":
    run_selftest()
