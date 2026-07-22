# ⚡ How to activate the alive swarm

There are two levels: **run it now on your machine** (works today), and **deploy it into a real watching
pipeline** (product integration). Both are described honestly — no "flip a switch and YouTube upscales" magic.

---

## Level 1 — Activate NOW on your Mac/PC (works today, one command each)

```bash
git clone git@github.com:devkancheti4-design/720p-movies.git && cd 720p-movies
pip3 install pillow numpy          # for the image/video tools; brew install ffmpeg for video

# activate on a REAL video (ingest → rebuild → PLAY a side-by-side):
python3 activate.py                             # built-in sample, rebuild to 1080p
python3 activate.py --video myclip.mp4 --to 4k  # YOUR video, rebuild to 4K
python3 activate.py --video myclip.mp4 --to 1440

# see it on a photo (opens before/after on screen):
python3 mac_live_proof.py                        # or --image yours.jpg

# measure everything:
python3 cost_of_watching.py        # total cost 1440p/4K, ~90% capture, real hardware fps
python3 transform_720_to_4k.py     # 720p→4K, how much captured, full byte logs
python3 watch_2gb.py               # what 2GB gets you (cache + rebuild)
```

`activate.py` runs the real pipeline: makes a 720p base, the **alive organism** stores the hard blocks (dialed
to ~90% capture), rebuilds the frames, and opens a **plain-upscale vs alive-swarm** video so you watch the
difference. It prints capture %, rebuild ms/frame, data in/out, and the deterministic fingerprint.

---

## Level 2 — Deploy it for real watching (the honest architecture)

The system is 3 pieces, all of which already exist on every device:
- **the organism** (~30 lines: a set + counter + journal) — deterministic, no ML, no GPU;
- **the hard-block store** (a small key→pixels cache + journal file);
- **upscale + paste** — plain bilinear, which **every GPU does in hardware** (Metal / Vulkan / WebGL / WebGPU).

**Where you plug it in (pick your surface):**
| Surface | How to activate | Effort |
|---|---|---|
| **Desktop player** | a VLC / mpv plugin that intercepts decoded frames and runs upscale+paste on the GPU; organism as a small native/WASM lib | medium |
| **Browser** | a WebGPU extension on the `<video>` element (works on non-DRM streams; DRM streams are controlled by the platform) | medium |
| **Phone** | an SDK inside a video app; upscale on Metal/Vulkan; organism as a few-KB native lib | medium |
| **TV / set-top** | feed the stored hard blocks to the TV's existing upscaler chip (firmware / TV-app integration) | partner-level |
| **Server / CDN** | run the ingest once over the master to produce `360p/720p base + hard store` (deterministic, shardable) | easy |

**The killer property when you activate across devices:** because the organism is deterministic + CRDT-mergeable
+ regenerating, one hard-block store **syncs across your phone / laptop / TV coordinator-free**, and popular
content's blocks are shared across users (see `swarm_assembly_store.py`, `streaming_rebuild.py`).

---

## What activates today vs what is product-work (no overselling)

**Today (measured, runnable):** rebuild any video/photo to a higher resolution capturing ~90% of the detail;
on-device storage of more distinct content; instant re-paste of recurring/cached content; full byte + hardware
logs; alive (deterministic / regenerating / adaptive) — all provable with the commands above.

**Product-work (real, but not a switch you flip):** hooking into **YouTube/Netflix's own DRM player** live is a
platform integration (browser extension / player plugin / OS framework, or a platform partnership). And it is
**not a codec** — it runs *alongside* the H.264/H.265 decoder + the GPU upscaler, not instead of them. On real
motion film it improves **quality** and helps **cached/recurring** content, not first-view unique-detail storage
(a codec still wins there — see `RESULTS_MAP.md`).

**Bottom line:** to *activate it now*, run `python3 activate.py --video yourfile.mp4 --to 4k`. To *ship it*, wrap
the same three pieces (organism + store + GPU upscale-paste) into your target surface above.
