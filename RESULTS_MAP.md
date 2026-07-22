# 🗺️ Full results map — 720p → 1080p / 1440p / 4K, data saved, across domains

All numbers measured on real pixels on a Mac (`resolution_domain_map.py` + a 300-frame real-video test). Nothing
synthetic is presented as real; nothing is fabricated. Run it yourself: `python3 resolution_domain_map.py`.

## Data saved GROWS with target resolution (average across domains)

| 720p base → | Data saved (avg) |
|---|---|
| **1080p** | **1.41×** |
| **1440p** | **2.07×** |
| **4K** | **3.11×** |

**Why it grows:** the 720p base is 44% of a 1080p frame but only **11% of a 4K frame** — so at 4K you store a
tiny base + only the hard blocks, and the easy pixels rebuild free. **≥1.5× in 13 of 21 (domain×resolution) cases.**

## Per-domain map (data saved / quality gain)

| Domain | 1080p | 1440p | 4K | Quality (swarm vs upscale) |
|---|---|---|---|---|
| photo · landscape | 2.17× | 3.68× | **6.06×** | +1 to +1.5 dB |
| photo · portrait | 1.90× | 2.99× | **5.01×** | +6 to +7.6 dB |
| photo · city (detailed) | 1.26× | 1.57× | 1.96× | +7 to +10 dB |
| synthetic · animation | 1.71× | 2.51× | **4.57×** | +18 to +28 dB |
| synthetic · screen/UI | 1.32× | 2.04× | 2.18× | +7 to +19 dB |
| synthetic · gaming (busy) | 0.79× | 0.93× | 1.08× | +30 to +49 dB |
| synthetic · texture (worst) | 0.69× | 0.80× | 0.90× | +77 to +87 dB |

**Read this honestly:**
- **Flat / smooth / repetitive content wins big** (photos, animation, UI) — 1.5× to 6× and climbing with resolution.
- **Dense-detail content saves little or nothing** (busy games, pure texture) — because almost every block is
  "hard," so base+hard is *bigger* than the full frame. That's the honest floor: **there is no free lunch on
  content that is detail everywhere.**
- **Quality always improves** — but that's because the swarm pastes the *true* hard detail it stored. It is **not
  super-resolution** (it invents nothing); the huge dB gains on synthetic content just mean the upscaler failed
  there and the swarm had the real pixels.

## The real-motion-video test (300 frames of Big Buck Bunny, 1080p, on the Mac)

| Metric | Result | Meaning |
|---|---|---|
| Quality (swarm vs bicubic) | **+5.6 dB**, all 300 frames | the rebuild is genuinely sharper |
| **Temporal dedup** | **1.01×** | the hard detail is **unique every frame** — exact-key can't dedup real motion |
| Storage on motion | **no saving** (371 MB / 12 s uncompressed) | vs a real H.265 codec, this loses badly |

**So on real film there is NO storage win** — the earlier amortization/1.5× curve was *synthetic recurring*
content. Real motion has no exact repeats. A `comparison.mp4` was rendered so you can watch bicubic-vs-swarm-vs-true.

## 720p → 4K: how much of 4K is captured? (`transform_720_to_4k.py`, real 4K photo, on the Mac)

The honest core: **the swarm does not invent 4K detail** — it captures 4K only by *storing* the true 4K
hard-blocks. Measured on a real 4K frame:

| Method | PSNR | 4K detail captured | Data |
|---|---|---|---|
| **720p ALONE → 4K** (plain upscale) | 34.3 dB | the base only — real 4K detail **isn't in the 720p** | 720p base |
| **720p + alive-swarm** (stored hard blocks) | **44.0 dB** | **89% of the detail plain-upscale loses** | base + hard store |

**The knob (quality ⇄ data) — capture more by storing more:**

| Threshold | 4K detail captured | Blocks stored | Smaller than raw 4K |
|---|---|---|---|
| 6 | **97%** | 22% | 3.0× |
| 16 | 89% | 11% | 4.4× |
| 40 | 48% | 2% | 7.4× |

**Full byte log (one 4K frame):** raw 4K **24.9 MB** → 720p base **2.8 MB** + hard store **~2 MB** = **~5 MB
(≈4.4× smaller than raw, uncompressed)**. Honest: a real H.265 codec still beats that on data — the swarm is a
rebuilder + cache, not a codec.

## Alive — proven live on the real store (not static)

- **Deterministic** — same store → same fingerprint.
- **Regenerating** — real SIGKILL mid-run → revived byte-exact.
- **Adaptive** — ONE store learned **527,848 hard textures across 7 domains online**, no restart; a **frozen store
  adopts 0** (static = useless the moment a new domain arrives). *This is the load-bearing role of aliveness: it is
  not what creates the data saving (that is structural), it is what lets one store serve every domain, survive
  crashes, and reproduce bit-exact — the operational moat.*

## Bottom line (what's real, no overselling)

1. **Data saving ≥ 1.5× is real and grows with resolution** for flat/typical content (photos, animation, UI) —
   *uncompressed domain*; it does **not** beat a codec, and it does **not** help dense-detail or real-motion video.
2. **Quality-from-a-small-base is real** — but it needs the true hard detail stored/sent; it is not invented.
3. **The alive swarm's genuine, unbreakable value** is the operational bundle: one deterministic, crash-exact,
   coordinator-free, adaptive store across all resolutions and domains, feeding the device's GPU the hard blocks
   to paste. The pixels are the GPU's; the detail is the swarm's; the magic upscaling would need an AI it isn't.
