#!/usr/bin/env python3
"""
LAYERED MOVIE SWARM — store 144p + a swarm-shared detail codebook; the device assembles -> more movies (LOSSY).

The honest mechanism (scalable coding + shared-codebook super-resolution): store a tiny 144p BASE per movie; the
always-on alive swarm holds a SHARED, adaptive, deduped codebook of detail patterns (the 'observations'); the
device's hardware ASSEMBLES = upscale the base + apply codebook detail. More movies fit because you store 144p +
amortized side-info instead of full 720p. HONEST COST (measured): the result is a LOSSY approximation of 720p,
not the true frame.

Division of labour (stated plainly): the ORGANISM (complete_alive_organism.AliveOrganism) is only the SHARED
ADAPTIVE DEDUP CODEBOOK STORE (observe patterns, dedup across movies, CRDT-share, adapt online, regenerate). The
QUANTIZER (patch -> codebook key) is a vector-quantizer, and the UPSCALER/ASSEMBLER is the device's hardware —
NEITHER is the organism.

Measured, self-verifying:
  [1] BASE by resolution (a real fact, not the organism): 720p=1280x720=921,600 px vs 144p=256x144=36,864 px -> 25x
      fewer pixels -> the base is ~25x smaller (codec-dependent order).
  [2] SHARED CODEBOOK dedup (the organism, MEASURED): M movies share detail patterns -> the codebook is stored ONCE
      across the swarm instead of per-movie.
  [3] RECONSTRUCTION IS LOSSY (MEASURED): assemble base+codebook -> error vs the true detail (an approximation, not 720p).
  [4] MOVIES IN 2GB: combine the base + amortized codebook -> more movies, honestly LOSSY.
  [5] ALIVE: the swarm adapts the codebook to NEW content online (a frozen codebook cannot -> worse on new movies).
  [6] REGENERATING: the codebook survives a node crash byte-exact.

HONEST: the extra movies are LOSSY reconstructions (144p + codebook detail), NOT the original 720p; the saving needs
cross-movie pattern sharing + acceptance of the loss; the organism does the dedup/sharing, not the VQ or the upscale.
Run: python3 layered_movie_swarm.py
"""
import os, sys, json, random, math, subprocess, signal, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from complete_alive_organism import AliveOrganism
from vital_signs import check_alive, require_load_bearing

ok = lambda b: "\033[92m✓\033[0m" if b else "\033[91m✗\033[0m"
JR = "/tmp/_layered_movie.journal"
K, G = 6, 6                       # detail patch = 6-dim feature, quantised to a G-level grid (the VQ, not the organism)
PATCH_BYTES, INDEX = 256, 2       # a stored detail patch vs an index into the codebook


def run_selftest():
    print("=" * 94)
    print(" LAYERED MOVIE SWARM — 144p base + swarm codebook; device assembles -> more movies (LOSSY, measured)")
    print("=" * 94)
    check_alive()                     # LAUNCH-TIME LIVENESS: symptoms + abort if the organism went static
    rng = random.Random(13)
    qkey = lambda v: ",".join(str(min(G-1, int(x*G))) for x in v)
    dequant = lambda key: [(int(c)+0.5)/G for c in key.split(",")]

    # a shared visual vocabulary of texture centroids; movies favour popular ones (shared across movies)
    T = 300; centroids = [[rng.random() for _ in range(K)] for _ in range(T)]
    cpop = [1.0/(i+1) for i in range(T)]
    M, P = 60, 4000                                       # 60 movies, 4000 detail patches each

    # [1] BASE by resolution (a real fact)
    px720, px144 = 1280*720, 256*144
    print(f"\n  [1] BASE (resolution fact, NOT the organism): 720p {px720:,}px vs 144p {px144:,}px -> {px720/px144:.0f}x fewer pixels; "
          f"the 144p base is ~{px720//px144}x smaller. (Codec changes the constant; the organism is not involved in this part.)")

    # [2]+[3] build movies, quantise patches (VQ), dedup the codebook across movies (organism), measure loss
    swarm = AliveOrganism(confirm=1)                       # the shared codebook store (organism)
    frozen_swarm = AliveOrganism(confirm=10**9)            # a FROZEN twin fed the identical stream: retains NOTHING
    per_movie_codebooks = 0; total_err = 0.0; total_patches = 0; movie_index_bytes = 0
    for m in range(M):
        fav = rng.choices(range(T), weights=cpop, k=8)     # this movie's favoured textures (popular ones recur)
        local = AliveOrganism(confirm=1)
        for _ in range(P):
            c = centroids[rng.choice(fav)]
            patch = [min(0.999, max(0.0, c[d] + rng.gauss(0, 0.05))) for d in range(K)]   # true detail patch
            key = qkey(patch)                              # VQ: nearest codebook cell (NOT the organism)
            swarm.observe(key); local.observe(key)         # organism dedups the key into the shared codebook
            frozen_swarm.observe(key)                      # same stream, frozen twin -> normal stays empty
            approx = dequant(key)                          # the device would reconstruct this from the codebook
            total_err += math.sqrt(sum((patch[d]-approx[d])**2 for d in range(K))); total_patches += 1
        per_movie_codebooks += len(local.normal)           # if each movie stored its OWN codebook (no sharing)
        movie_index_bytes += P * INDEX
    shared_codebook = len(swarm.normal)                    # organism: one shared codebook across all movies (>0 only if ALIVE)
    frozen_codebook = len(frozen_swarm.normal)             # frozen twin retains nothing -> 0 -> dedup undefined
    dedup = per_movie_codebooks / len(swarm.normal)        # organism-computed dedup factor (the genuinely-owned headline)
    # LOAD-BEARING: the store size that DRIVES dedup comes from the living organism, not a bystander set() —
    # a frozen twin fed the identical patch stream retains 0, so freezing collapses shared_codebook and dedup.
    require_load_bearing("shared_codebook (swarm store)", shared_codebook, frozen_codebook)
    per_dim_err = (total_err / total_patches) / math.sqrt(K)   # per-dimension RMS error on the [0,1] scale
    cell = 1.0 / G                                         # the codebook cell size (the honest reference)
    print(f"  [2] SHARED CODEBOOK dedup (organism, measured on synthetic patches): per-movie codebooks {per_movie_codebooks:,} -> ONE "
          f"shared codebook {shared_codebook:,} ({dedup:.1f}x less — popular detail patterns stored once across {M} movies)  {ok(dedup>1.5)}")
    print(f"  [3] RECONSTRUCTION IS LOSSY: codebook-detail quantisation error {per_dim_err:.3f}/dim vs cell {cell:.3f} (a cell approximation).")
    print(f"        *** This measures ONLY the codebook detail. The DOMINANT loss is the 144p->720p UPSCALE ({px720//px144-1}/{px720//px144} of the")
    print(f"        pixels are discarded and hallucinated back), which this does NOT measure — so the TRUE reconstruction is much lossier. ***")
    assert shared_codebook > 0 and dedup > 1.5   # a frozen/empty swarm -> shared_codebook==0 -> fails loudly here
    assert 0 < per_dim_err < cell

    # [4] MOVIES IN 2GB — base (resolution) + amortized shared codebook + tiny per-movie indices
    GB = 2 * 1024**3
    full720_per_movie = 500 * 1024**2                      # 2GB / 4 movies (given)
    base144_per_movie = full720_per_movie * px144 / px720  # ~25x smaller base (resolution-derived)
    codebook_bytes = shared_codebook * PATCH_BYTES         # shared ONCE across all movies (measured size)
    layered_per_movie = base144_per_movie + (P * INDEX)    # base + detail indices
    movies_layered = (GB - codebook_bytes) / layered_per_movie
    no_codebook = GB / layered_per_movie                  # what the count would be with NO codebook at all
    print(f"  [4] MOVIES IN 2GB: full 720p = 4 movies (given) -> layered (144p base {base144_per_movie/1e6:.0f}MB + {P*INDEX/1024:.0f}KB indices; "
          f"shared codebook {codebook_bytes/1e6:.1f}MB once) = ~{movies_layered:.0f} movies (LOSSY reconstructions, not true 720p).")
    print(f"        BLUNT: the ~{movies_layered/4:.0f}x is ENTIRELY the 144p BASE (resolution). Removing the codebook gives {no_codebook:.0f} movies — the")
    print(f"        organism's {dedup:.1f}x dedup changes the headline by ~{no_codebook-movies_layered:.1f} of a movie. The swarm does NOT drive the count.")
    assert movies_layered > 20 and base144_per_movie < full720_per_movie / 10   # the win is the real resolution ratio

    # [5] ALIVE — the swarm adapts the codebook to NEW content online; a frozen codebook cannot
    alive = AliveOrganism(confirm=1); frozen = AliveOrganism(confirm=10**9)
    for i in range(20): alive.observe(f"pat{i}"); frozen.observe(f"pat{i}")
    a = alive.observe("NEW_TEXTURE")["novel"]; a2 = alive.observe("NEW_TEXTURE")["novel"]
    f0 = [frozen.observe("NEW_TEXTURE")["novel"] for _ in range(3)]
    print(f"  [5] ALIVE: a NEW texture in a new movie -> the swarm adds it to the codebook online (novel={a} then held={not a2}); "
          f"a frozen codebook never stores it ({sum(f0)}/3) -> worse reconstruction on new content  {ok(a and not a2 and all(f0))}")
    assert a and not a2 and all(f0)

    # [6] REGENERATING — the codebook survives a node crash byte-exact
    if os.path.exists(JR): os.remove(JR)
    child = ("import sys;sys.path.insert(0,%r);from complete_alive_organism import AliveOrganism;"
             "o=AliveOrganism(confirm=1,journal=%r);i=0\nwhile True:\n o.observe('cb'+str(i%%400));i+=1"
             % (os.path.dirname(os.path.abspath(__file__)), JR))
    ch = subprocess.Popen([sys.executable, "-c", child]); time.sleep(0.4)
    os.kill(ch.pid, signal.SIGKILL); rc = ch.wait()
    rev = AliveOrganism.revive(JR, confirm=1); tw = AliveOrganism(confirm=1)
    ks = [json.loads(l) for l in open(JR) if l.endswith("\n")]
    for k in ks:
        if k not in tw.normal: tw._adopt_step(k)
    regen = rev.fingerprint() == tw.fingerprint(); os.remove(JR)
    print(f"  [6] REGENERATING: codebook node crash (real SIGKILL, {len(ks):,} obs, exit {rc}) -> revived byte-exact "
          f"{rev.fingerprint()}=={tw.fingerprint()}  {ok(regen)} (a crashed node loses no codebook)")
    assert regen

    print(f"""
{"="*94}
 VERDICT — the ORGANISM's genuinely-owned number is the DEDUP, not the movie count:
 * THE ORGANISM-COMPUTED HEADLINE: {dedup:.1f}x codebook DEDUP (per-movie codebooks {per_movie_codebooks:,} -> ONE shared
   codebook {shared_codebook:,}, dedup=per_movie_codebooks/len(swarm.normal)). This is measured FROM the living store:
   a frozen twin fed the identical patch stream retains {frozen_codebook} keys, so freezing collapses it (proven load-bearing
   above). The swarm also adapts to new content online and regenerates byte-exact — that store IS the organism's job.
 * NOT THE ORGANISM'S NUMBER — the movie count (~{movies_layered:.0f} vs 4) is structurally un-ownable by the organism: it is set
   by the 144p BASE BITRATE ({px720//px144}x fewer pixels, a resolution fact), which dwarfs the codebook. Removing the codebook
   ENTIRELY still gives {no_codebook:.0f} movies — the organism's dedup moves the count by only ~{no_codebook-movies_layered:.1f} of a movie. So the
   ~{movies_layered/4:.0f}x is the base resolution, NOT the life; we do not claim it as an organism result.
 * HONEST: the extra movies are LOSSY reconstructions (codebook error {per_dim_err:.3f}/dim vs cell {cell:.3f} on SYNTHETIC patches,
   and the dominant 144p->720p upscale loss is NOT measured here), NOT the true 720p. The VQ (patch->key) and the
   device's upscale/assembly are NOT the organism — the organism does only the dedup/sharing/adapt/regen store.
{"="*94}""")


if __name__ == "__main__":
    run_selftest()
