# -*- coding: utf-8 -*-
"""用ComfyUI birefnet抠图 -> 合成纯绿幕, 输出 assets/greenscreen.png
解决: 原素材是渐变灰影棚背景, 客户端色差抠像不干净; 换成纯绿幕后抠像完美。
"""
import json, os, time, urllib.request, uuid

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gm_config as C
C.ensure_dirs()
COMFY = C.COMFY
SRC = os.path.join(C.ASSETS, "selected.png")
OUT = os.path.join(C.ASSETS, "greenscreen.png")

def upload(path, name):
    boundary = uuid.uuid4().hex
    data = open(path, "rb").read()
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; "
            f"filename=\"{name}\"\r\nContent-Type: image/png\r\n\r\n").encode() + data + \
           f"\r\n--{boundary}--\r\n".encode()
    r = urllib.request.Request(f"{COMFY}/upload/image", data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    return json.load(urllib.request.urlopen(r, timeout=30))["name"]

def main():
    upname = upload(SRC, "selected.png")
    print("uploaded:", upname)

    wf = {
      "1": {"class_type": "LoadImage", "inputs": {"image": upname}},
      "2": {"class_type": "LoadBackgroundRemovalModel",
            "inputs": {"bg_removal_name": "birefnet.safetensors"}},
      "3": {"class_type": "RemoveBackground",
            "inputs": {"bg_removal_model": ["2", 0], "image": ["1", 0]}},
      # 纯绿底 EmptyImage: color 0x00FF00 = 65280
      "4": {"class_type": "EmptyImage",
            "inputs": {"width": 768, "height": 1344, "batch_size": 1, "color": 65280}},
      "5": {"class_type": "ImageCompositeMasked",
            "inputs": {"source": ["1", 0], "destination": ["4", 0],
                       "x": 0, "y": 0, "resize_source": False, "mask": ["3", 0]}},
      "6": {"class_type": "SaveImage", "inputs": {"filename_prefix": "greenscreen", "images": ["5", 0]}},
    }
    payload = json.dumps({"prompt": wf}).encode()
    r = urllib.request.Request(f"{COMFY}/prompt", data=payload,
        headers={"Content-Type": "application/json"})
    res = json.load(urllib.request.urlopen(r, timeout=30))
    pid = res["prompt_id"]
    print("queued:", pid)

    t0 = time.time()
    while time.time() - t0 < 600:
        time.sleep(5)
        q = json.load(urllib.request.urlopen(f"{COMFY}/queue", timeout=10))
        if not [x for x in q["queue_running"] if x[1]==pid] and \
           not [x for x in q["queue_pending"] if x[1]==pid]:
            break
    h = json.load(urllib.request.urlopen(f"{COMFY}/history/{pid}", timeout=10))
    for node in h.get(pid, {}).get("outputs", {}).values():
        for img in node.get("images", []):
            if img["filename"].startswith("greenscreen"):
                u = f"{COMFY}/view?filename={img['filename']}&subfolder={img.get('subfolder','')}&type={img['type']}"
                open(OUT, "wb").write(urllib.request.urlopen(u, timeout=30).read())
                print("saved:", OUT)
                return
    print("未找到输出!")

if __name__ == "__main__":
    main()
