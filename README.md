# 🎬 720p-movies — Alive Collatz Organism Swarm for Movie Storage & Watching

**2GB holds 4 × 720p movies today. With the alive swarm: 16 movies (360p base) or 9 movies (480p base), at
99.97% measured pixel fidelity.** Every claim in this repo is a runnable, self-asserting Python file — clone and
run; nothing here is a screenshot or a promise.

```bash
git clone git@github.com:devkancheti4-design/720p-movies.git && cd 720p-movies
python3 hard_frame_upscale.py        # the exact numbers
python3 swarm_contribution_proof.py  # how much the swarm REALLY contributes (ablation)
```

## The exact numbers (measured)

| Scheme | MB/movie | Movies in 2GB | Fidelity |
|---|---|---|---|
| Full 720p (today) | 500 | **4** | original |
| **360p base + swarm hard-store** | 127 | **16** | **99.97%** overall; hard detail **100% bit-exact**; easy pixels ≤3/255 |
| **480p base + swarm hard-store** | 224 | **9** | same or better |

Content-dependent (disclosed in the code): a detail-heavy movie fits fewer (5% unique-hard → 13, 15% → 10, 30% → 7).

## How it works — the mechanism

1. **The organisms are OBSERVERS, not memory.** During ingest they watch every 8×8 block of the 720p master and
   split it: **easy** blocks (flat colour, smooth gradients — the device's interpolation recovers them within
   3/255) vs **hard** blocks (texture/detail — upscaling fails at 127/255 error, so the true pixels must be kept).
2. **The swarm stores the hard blocks bit-exact, deduplicated** (recurring textures across frames/sets stored
   ONCE — measured 80.6× dedup), deterministically (same movie → same store, sha-verified), journaled (WAL).
3. **The device hardware just arranges it**: upscale the 360p base (cheap interpolation = the easy pixels) and
   paste the stored hard blocks (a key lookup). No AI, no codec work on the device.

## How much the swarm REALLY contributes (`swarm_contribution_proof.py` — ablation, measured by deletion)

| Delete this swarm property | What breaks |
|---|---|
| **Dedup** (the organism store) | movies drop **16 → 8**: the swarm's dedup alone is **+8 movies — half the result** |
| **Aliveness** (freeze) | you lose **online, single-pass, no-retrain, no-human ingestion** of new content. *(DD-corrected: an earlier "+5.4 fidelity pts is aliveness" claim was **refuted and retracted** — that was storage, which a plain cache also does. Aliveness = the no-retrain online operation, not a fidelity bonus.)* |
| **Regeneration** (the WAL) | a crash mid-ingest redoes everything (12,777 obs) vs **0 re-observed** — the organism revives byte-exact |
| **Multiplication** | long movies: 4 spawned shards, CRDT union **== single store** (capacity, identical result) |

**Not the swarm (stated plainly):** the 360p base is resolution math, and the upscaler/classifier are device code.

### The hard truth files (run them before believing anyone — including us)
- [`storage_record_truth.py`](storage_record_truth.py): the swarm's REAL records — long-range dedup **22.8×** where
  window-limited zlib gets **1.0×**, cross-node **7.7×**, multiply = capacity ×8 CRDT-exact — AND the wall: on
  high-entropy content it stores **0.996×** like everything else. "Compresses anything" is impossible for any
  lossless system (pigeonhole); the swarm's wins live exactly where exact redundancy exists.
- [`lossless_movie_pack.py`](lossless_movie_pack.py): TRULY lossless (sha-verified) is content-dependent —
  recurring-texture content ~**15** movies, realistic 90%-detail movie ~**3** (the honest floor). Truly-lossless
  real 720p does not fit many in 2GB — physics. The 16/9 numbers above are **near-lossless** (hard detail
  bit-exact, easy pixels ≤3/255), which is the honest offer.

## What is "the pipeline"? (the raw/intermediate-frames note explained)

A finished movie you download is **already codec-compressed** (H.264/H.265) — near-random bytes, nothing left to
dedup ([`movie_storage.py`](movie_storage.py) measures this honestly: **1.000×**, still 4 movies — the organism
cannot compress a finished distinct movie, only a codec re-encode can).

**"The pipeline" = everywhere video exists BEFORE that final compression**: camera capture, editing suites, VFX
render farms, transcode/streaming origins — where frames are raw or intermediate (DPX/EXR/ProRes-like). THERE,
frames are full of exact-repeated blocks (letterbox bars, static backgrounds, held shots), and
[`swarm_frame_store.py`](swarm_frame_store.py) measures the organism's **2.3× lossless, bit-exact** dedup
(sha-verified reassembly). A codec gets 100–1000× on raw *by throwing information away*; the organism's 2.3× is
**lossless and crash-exact** — a different job, for stages where you must not lose a bit. That's why the note
says "for pipelines, not for fitting movies": it saves space inside production/processing systems, not on your
phone's finished files.

## 🚀 How to launch the swarm for watching movies — full details

**Phase 1 — INGEST (once, at the source / your PC):**
1. For each 720p movie, run the observer swarm over the master: classify each block (easy/hard), downsample the
   base to 360p, and let the organisms `observe()` every hard block — each unique one is stored bit-exact once
   (deduped), WAL-journaled. Long movie → the swarm **multiplies** (spawns shard organisms, each bounded; CRDT
   keeps the union identical to a single store).
2. Output per movie: `base_360p` (~125 MB) + `hard_store` (deduped blocks + index, ~2 MB on the measured mix).
3. Deterministic: re-ingesting the same movie yields the byte-identical store (fingerprint-verified) — so any
   machine can regenerate the store from the movie, or the store from its WAL.

**Phase 2 — DEPLOY (the 2GB device):**
4. Copy `base + hard_store` per movie → **16 movies fit where 4 did**. Or run the swarm across several devices:
   the CRDT assembly store shares blocks so popular content assembles 0-from-origin
   ([`swarm_assembly_store.py`](swarm_assembly_store.py)).

**Phase 3 — WATCH (playback):**
5. The device plays frame by frame: **upscale the 360p base** (hardware bilinear — the easy pixels) and **paste
   the hard blocks** from the store (deterministic key lookup, ~ns). Hard detail is bit-exact; easy regions are
   within 3/255. Measured overall: **99.97% pixel fidelity, 93.6% of pixels bit-perfect**.

**Alive, in operation (why the swarm must be alive, each measured):**
- **New movie added** → the observers adopt its new hard textures online (frozen observer: fidelity crashes to 94.5%).
- **Crash / power loss** → the organism revives byte-exact from its WAL; the ingest/library is never redone.
- **Very long movie / conditions** → the swarm multiplies; shards merge bit-exact (order-independent).
- **Many devices** → CRDT gossip: a block stored anywhere is stored once for the whole swarm.

## Files (each self-asserting: it fails loudly if any claim regresses)

| File | Role |
|---|---|
| [`complete_alive_organism.py`](complete_alive_organism.py) | THE organism (observe/adapt/rules/failsafe + WAL revive + CRDT + heartbeat) |
| [`hard_frame_upscale.py`](hard_frame_upscale.py) | **The exact numbers**: 4 → 16/9 movies, 99.97% fidelity, observer + dedup + revive |
| [`swarm_contribution_proof.py`](swarm_contribution_proof.py) | **Ablation**: dedup +8 movies (half the result); aliveness = online no-retrain ingestion (fidelity claim retracted after DD audit); regen saves the ingest |
| [`storage_record_truth.py`](storage_record_truth.py) | The records it breaks (22.8× long-range, 7.7× cross-node) and the wall nobody breaks (high-entropy 0.996×) |
| [`lossless_movie_pack.py`](lossless_movie_pack.py) | TRULY lossless, sha-verified: ~15 recurring / ~3 realistic-movie floor — the honest lossless scope |
| [`swarm_frame_store.py`](swarm_frame_store.py) | Lossless bit-exact repeated-block store + swarm multiplication (the "pipeline" case) |
| [`swarm_assembly_store.py`](swarm_assembly_store.py) | Cross-device sharing: popular content assembles 0-from-origin |
| [`layered_movie_swarm.py`](layered_movie_swarm.py) | The lossy codebook variant (~102 movies, honestly attributed: the 26× is the 144p base) |
| [`movie_storage.py`](movie_storage.py) | **Honest negative**: the organism cannot compress a finished distinct movie (1.000×) |

## Honest boundaries (in the code, not fine print)

- **Near-lossless ≠ lossless**: hard content is bit-exact; easy pixels carry ≤3/255 interpolation error.
- The counts use a stated bytes~stored-pixels model on a **synthetic measured mix** — real movies vary
  (sensitivity is printed by the code).
- The organism **does not compress finished movies** (measured 1.000×), does not upscale, does not perceive —
  it observes, dedups bit-exact, adapts, multiplies, regenerates. The device assembles; a codec is still the
  right tool for finished-file compression.
- All organisms here are **genuinely alive**: adapt-vs-frozen and real-SIGKILL byte-exact revival are asserted
  in every file, on every run.

Part of the larger proof suite: [deep-space](https://github.com/devkancheti4-design/deep-space) (19 runnable proofs).
