# -*- coding: utf-8 -*-
"""AI女友换装脚本 (路线A)
用法:
  python change_outfit.py "红色修身连衣裙,黑色丝袜" --name 红裙 [--apply]
  python change_outfit.py --use 红裙            # 从服装库直接套用
流程: Qwen-Image-Edit指令换装 -> birefnet抠绿幕 -> 存服装库 -> (--apply)重建avatar+提示重连
"""
import argparse, glob, json, os, shutil, subprocess, sys, time, urllib.request, uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gm_config as C
C.ensure_dirs()
COMFY = C.COMFY
BASE_DIR = C.REPO_ROOT
WARDROBE = C.WARDROBE
BODY = os.path.join(WARDROBE, "base", "body.png")
PY_LT = C.lt_python()


def upload(path):
    boundary = uuid.uuid4().hex
    fn = os.path.basename(path)
    data = open(path, "rb").read()
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; "
            f"filename=\"{fn}\"\r\nContent-Type: image/png\r\n\r\n").encode() + data + \
           f"\r\n--{boundary}--\r\n".encode()
    r = urllib.request.Request(f"{COMFY}/upload/image", data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    return json.load(urllib.request.urlopen(r, timeout=30))["name"]


def run_comfy(wf, prefix, timeout=1800):
    payload = json.dumps({"prompt": wf}).encode()
    r = urllib.request.Request(f"{COMFY}/prompt", data=payload,
        headers={"Content-Type": "application/json"})
    pid = json.load(urllib.request.urlopen(r, timeout=30))["prompt_id"]
    print("queued:", pid, flush=True)
    t0 = time.time()
    while time.time() - t0 < timeout:
        time.sleep(8)
        q = json.load(urllib.request.urlopen(f"{COMFY}/queue", timeout=10))
        if not [x for x in q["queue_running"] if x[1] == pid] and \
           not [x for x in q["queue_pending"] if x[1] == pid]:
            break
        print(f"  [{int(time.time()-t0)}s] generating...", flush=True)
    h = json.load(urllib.request.urlopen(f"{COMFY}/history/{pid}", timeout=10))
    hist = h.get(pid)
    if not hist:
        raise RuntimeError("任务无history(可能被中断)")
    status = hist.get("status", {})
    if status.get("status_str") == "error":
        raise RuntimeError("ComfyUI执行报错: " + json.dumps(status)[:500])
    outs = []
    for node in hist.get("outputs", {}).values():
        for img in node.get("images", []):
            outs.append(img)
    files = []
    for img in outs:
        u = f"{COMFY}/view?filename={img['filename']}&subfolder={img.get('subfolder','')}&type={img['type']}"
        dst = os.path.join(BASE_DIR, "assets", f"{prefix}_{img['filename']}")
        open(dst, "wb").write(urllib.request.urlopen(u, timeout=60).read())
        files.append(dst)
    return files


def edit_outfit(desc, seed):
    """Qwen-Image-Edit 指令换装"""
    upname = upload(BODY)
    prompt = (f"把图中女性的衣服换成：{desc}。"
              f"严格保持原图的一切：正面朝向镜头的脸、五官、黑长直发型、身材、双臂下垂双腿交叉的站姿、"
              f"居中构图、纯绿色背景。画面中只有一个人物，不要出现副本或重影。只更换服装，"
              f"服装合身自然，光影与原图一致，写实照片质感。")
    wf = {
      "1": {"class_type": "UNETLoader",
            "inputs": {"unet_name": "qwen_image_2.1_int8_convrot.safetensors",
                       "weight_dtype": "default"}},
      "2": {"class_type": "CLIPLoader",
            "inputs": {"clip_name": "qwen3vl_8b_int8_convrot.safetensors",
                       "type": "qwen_image", "device": "default"}},
      "3": {"class_type": "VAELoader",
            "inputs": {"vae_name": "qwen_image_2.1_vae_bf16.safetensors"}},
      "4": {"class_type": "LoadImage", "inputs": {"image": upname}},
      "5": {"class_type": "TextEncodeQwenImage21",
            "inputs": {"clip": ["2", 0], "prompt": prompt,
                       "negative_prompt": "变形, 多余手指, 模糊, 低质量, 脸部改变, 换脸",
                       "resolution": 1024, "images": [["4", 0]],
                       "vae": ["3", 0]}},
      "8": {"class_type": "ModelSamplingAuraFlow",
            "inputs": {"model": ["1", 0], "shift": 3.1}},
      "9": {"class_type": "KSampler",
            "inputs": {"seed": seed, "steps": 20, "cfg": 2.5,
                       "sampler_name": "euler", "scheduler": "simple",
                       "denoise": 1.0, "model": ["8", 0],
                       "positive": ["5", 0], "negative": ["5", 1],
                       "latent_image": ["5", 2]}},
      "10": {"class_type": "VAEDecode",
             "inputs": {"samples": ["9", 0], "vae": ["3", 0]}},
      "11": {"class_type": "SaveImage",
             "inputs": {"filename_prefix": "outfit", "images": ["10", 0]}},
    }
    return run_comfy(wf, "outfit")


def to_greenscreen(src, dst):
    """birefnet抠图 -> 纯绿幕合成 (复用make_greenscreen逻辑)"""
    upname = upload(src)
    wf = {
      "1": {"class_type": "LoadImage", "inputs": {"image": upname}},
      "2": {"class_type": "LoadBackgroundRemovalModel",
            "inputs": {"bg_removal_name": "birefnet.safetensors"}},
      "3": {"class_type": "RemoveBackground",
            "inputs": {"bg_removal_model": ["2", 0], "image": ["1", 0]}},
      "4": {"class_type": "EmptyImage",
            "inputs": {"width": 768, "height": 1344, "batch_size": 1, "color": 65280}},
      "5": {"class_type": "ImageCompositeMasked",
            "inputs": {"source": ["1", 0], "destination": ["4", 0],
                       "x": 0, "y": 0, "resize_source": False, "mask": ["3", 0]}},
      "6": {"class_type": "SaveImage",
            "inputs": {"filename_prefix": "gs", "images": ["5", 0]}},
    }
    files = run_comfy(wf, "gs")
    shutil.copy(files[0], dst)
    return dst


def rebuild_avatar(gs_png):
    """绿幕图 -> 微动视频 -> genavatar (全程ASCII路径, cv2读不了中文路径)"""
    assets = os.path.join(BASE_DIR, "assets")
    ascii_src = os.path.join(assets, "greenscreen.png")
    shutil.copy(gs_png, ascii_src)
    video = os.path.join(assets, "green_avatar.mp4")
    if os.path.exists(video):
        os.remove(video)
    r = subprocess.run([PY_LT, os.path.join(BASE_DIR, "img2avatar_video.py"),
                        ascii_src, video, "200"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    print(r.stdout[-300:], r.stderr[-300:])
    assert os.path.exists(video), f"微动视频生成失败: {r.stderr[-300:]}"
    r = subprocess.run([PY_LT, "-m", "avatars.wav2lip.genavatar",
                        "--video_path", video, "--img_size", "256",
                        "--avatar_id", "wav2lip256_green"],
                       cwd=os.path.join(BASE_DIR, "LiveTalking"),
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(r.stdout[-500:], r.stderr[-300:])
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("desc", nargs="?", help="服装描述")
    ap.add_argument("--name", default=None, help="服装名(存库用)")
    ap.add_argument("--apply", action="store_true", help="生成后直接重建avatar")
    ap.add_argument("--use", default=None, help="直接从服装库套用")
    ap.add_argument("--seed", type=int, default=20261030)
    args = ap.parse_args()

    if args.use:
        d = os.path.join(WARDROBE, "outfits", args.use)
        final = os.path.join(d, "final.png")
        assert os.path.exists(final), f"服装库没有 {args.use}"
        print(f"套用服装库: {args.use}")
        rebuild_avatar(final)
        print("DONE: 重启LiveTalking服务或让桌宠重连即可生效")
        return

    assert args.desc, "需要服装描述或 --use"
    name = args.name or args.desc[:12]
    d = os.path.join(WARDROBE, "outfits", name)
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "prompt.txt"), "w", encoding="utf-8").write(args.desc)

    print(f"== 生成换装: {args.desc} ==")
    files = edit_outfit(args.desc, args.seed)
    preview = os.path.join(d, "preview.png")
    shutil.copy(files[0], preview)
    print("预览图:", preview)

    print("== 抠像合成绿幕 ==")
    final = os.path.join(d, "final.png")
    to_greenscreen(preview, final)
    print("绿幕终图:", final)

    # 自动生成衣橱缩略图(用LiveTalking venv的python, 系统python可能无cv2)
    try:
        r = subprocess.run(
            [PY_LT, os.path.join(BASE_DIR, "tools", "make_thumbnail.py"), d],
            capture_output=True, text=True, encoding="utf-8", errors="replace")
        print("缩略图:", r.stdout.strip() or r.stderr.strip()[:200])
    except Exception as e:
        print("缩略图生成失败(不影响):", e)

    if args.apply:
        print("== 重建avatar ==")
        rebuild_avatar(final)
        print("DONE: 重启LiveTalking服务或让桌宠重连即可生效")
    else:
        print(f"已入库。查看预览后运行: python change_outfit.py --use {name} --apply")


if __name__ == "__main__":
    main()
