# -*- coding: utf-8 -*-
"""提交SDXL文生图: 绿幕全身御姐形象 -> ComfyUI (Juggernaut-XL_v9)"""
import json, os, sys, time, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gm_config as C
C.ensure_dirs()
COMFY = C.COMFY

POS = ("masterpiece, best quality, ultra realistic photo, 1girl, solo, 25 years old chinese woman, "
       "long straight black hair, mature elegant onee-san, tall slim figure, "
       "form-fitting dark navy dress, high heels, standing straight facing camera, "
       "full body shot, head to toe visible, arms relaxed at sides, "
       "closed mouth, gentle neutral smile, soft studio lighting on face, "
       "solid pure green screen background, chroma key green backdrop, flat even background lighting, "
       "no shadow on background, photorealistic skin texture")

NEG = ("nsfw, nude, lowres, bad anatomy, bad hands, extra fingers, missing fingers, "
       "dead eyes, blank eyes, deformed, ugly, blurry, watermark, text, logo, "
       "open mouth, teeth, side view, back view, cropped, out of frame, "
       "busy background, pattern background, shadow")

wf = {
  "1": {"class_type": "CheckpointLoaderSimple",
        "inputs": {"ckpt_name": os.environ.get("GLASMATE_CKPT", "Juggernaut-XL_v9_RunDiffusionPhoto_v2.safetensors")}},
  "2": {"class_type": "CLIPTextEncode",
        "inputs": {"text": POS, "clip": ["1", 1]}},
  "3": {"class_type": "CLIPTextEncode",
        "inputs": {"text": NEG, "clip": ["1", 1]}},
  "4": {"class_type": "EmptyLatentImage",
        "inputs": {"width": 768, "height": 1344, "batch_size": 4}},
  "5": {"class_type": "KSampler",
        "inputs": {"seed": 20261030, "steps": 30, "cfg": 4.5,
                   "sampler_name": "dpmpp_2m", "scheduler": "karras",
                   "denoise": 1.0, "model": ["1", 0],
                   "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["4", 0]}},
  "6": {"class_type": "VAEDecode",
        "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
  "7": {"class_type": "SaveImage",
        "inputs": {"filename_prefix": "green_gf", "images": ["6", 0]}},
}

payload = json.dumps({"prompt": wf}).encode()
r = urllib.request.Request(f"{COMFY}/prompt", data=payload,
                           headers={"Content-Type": "application/json"})
res = json.load(urllib.request.urlopen(r, timeout=30))
pid = res["prompt_id"]
print("queued:", pid)

t0 = time.time()
while True:
    time.sleep(10)
    q = json.load(urllib.request.urlopen(f"{COMFY}/queue", timeout=10))
    running = [x for x in q["queue_running"] if x[1] == pid]
    pending = [x for x in q["queue_pending"] if x[1] == pid]
    el = time.time() - t0
    if not running and not pending:
        print(f"done in {el:.0f}s")
        break
    print(f"[{el:.0f}s] running={bool(running)} pending={bool(pending)}", flush=True)
    if el > 3600:
        print("timeout"); break

h = json.load(urllib.request.urlopen(f"{COMFY}/history/{pid}", timeout=10))
outs = []
for node in h.get(pid, {}).get("outputs", {}).values():
    for img in node.get("images", []):
        outs.append(img)
print("outputs:", json.dumps(outs, ensure_ascii=False))
# 下载到本地
import os
os.makedirs(C.ASSETS, exist_ok=True)
for i, img in enumerate(outs):
    u = f"{COMFY}/view?filename={img['filename']}&subfolder={img.get('subfolder','')}&type={img['type']}"
    data = urllib.request.urlopen(u, timeout=30).read()
    p = os.path.join(C.ASSETS, f"green_gf_{i}.png")
    open(p, "wb").write(data)
    print("saved", p, len(data))
