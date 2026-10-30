# -*- coding: utf-8 -*-
"""一键换装: 停LiveTalking -> GPU重建avatar -> 重启服务 -> 等就绪(桌宠自动重连)
用法: python apply_outfit.py <服装名>
"""
import glob
import os
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gm_config as C

BASE = C.REPO_ROOT
LT = C.LT_HOME
PY = C.lt_python()
WARDROBE = C.WARDROBE
AVATAR_ID = C.AVATAR_ID
PERSONA = C.PERSONA


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def kill_livetalking():
    try:
        out = subprocess.check_output(
            ["wmic", "process", "where", "name='python.exe'",
             "get", "ProcessId,CommandLine", "/format:csv"],
            text=True, errors="replace")
        for line in out.splitlines():
            if "app.py" in line and "LiveTalking" in line:
                pid = line.strip().split(",")[-1]
                subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True)
                log(f"已停止LiveTalking pid={pid}")
    except Exception as e:
        log(f"kill异常(可忽略): {e}")
    time.sleep(3)


def start_livetalking():
    env = os.environ.copy()
    env["LLM_SYSTEM_PROMPT"] = PERSONA
    logp = open(os.path.join(BASE, "logs", "livetalking.log"), "w", encoding="utf-8")
    proc = subprocess.Popen(
        [PY, "app.py", "--transport", "webrtc", "--model", "wav2lip",
         "--avatar_id", AVATAR_ID, "--llm_provider", "ollama", "--tts", "edgetts"],
        cwd=LT, env=env, stdout=logp, stderr=subprocess.STDOUT,
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
    log(f"LiveTalking已启动 pid={proc.pid}")
    for _ in range(90):
        time.sleep(3)
        try:
            urllib.request.urlopen("http://127.0.0.1:8010/", timeout=3)
            log("服务就绪(8010)")
            return True
        except Exception:
            pass
    log("服务启动超时")
    return False


def ensure_ollama():
    try:
        urllib.request.urlopen("http://127.0.0.1:11434/api/version", timeout=5)
        return
    except Exception:
        pass
    ollama_exe = os.environ.get(
        "OLLAMA_EXE",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama\ollama app.exe"))
    flags = subprocess.DETACHED_PROCESS if os.name == "nt" else 0
    subprocess.Popen(ollama_exe.split() if isinstance(ollama_exe, str) else ollama_exe,
                     creationflags=flags)
    log("已拉起Ollama")
    for _ in range(30):
        time.sleep(2)
        try:
            urllib.request.urlopen("http://127.0.0.1:11434/api/version", timeout=5)
            return
        except Exception:
            pass


def rebuild(outfit_name):
    d = os.path.join(WARDROBE, "outfits", outfit_name)
    final = os.path.join(d, "final.png")
    if not os.path.exists(final):
        # 兼容中文路径: 复制到ASCII路径
        ascii_src = os.path.join(BASE, "assets", "greenscreen.png")
        raise RuntimeError(f"找不到 {final}")
    ascii_src = os.path.join(BASE, "assets", "greenscreen.png")
    import shutil
    shutil.copy(final, ascii_src)
    video = os.path.join(BASE, "assets", "green_avatar.mp4")
    if os.path.exists(video):
        os.remove(video)
    log("生成微动视频...")
    r = subprocess.run([PY, os.path.join(BASE, "img2avatar_video.py"),
                        ascii_src, video, "200"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if not os.path.exists(video):
        raise RuntimeError(f"微动视频失败: {r.stderr[-300:]}")
    log("genavatar(GPU)...")
    r = subprocess.run([PY, "-m", "avatars.wav2lip.genavatar",
                        "--video_path", video, "--img_size", "256",
                        "--avatar_id", AVATAR_ID],
                       cwd=LT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    out_dir = os.path.join(LT, "data", "avatars", AVATAR_ID)
    n = len(glob.glob(os.path.join(out_dir, "face_imgs", "*.png")))
    if n == 0:
        raise RuntimeError(f"genavatar失败: {r.stdout[-300:]} {r.stderr[-300:]}")
    log(f"avatar重建完成 face_imgs={n}")


def main():
    if len(sys.argv) < 2:
        names = [os.path.basename(p) for p in
                 glob.glob(os.path.join(WARDROBE, "outfits", "*"))]
        print("服装库:", names)
        print("用法: python apply_outfit.py <服装名>")
        sys.exit(1)
    outfit = sys.argv[1]
    log(f"===== 一键换装: {outfit} =====")
    kill_livetalking()          # 先停服务腾显存
    rebuild(outfit)             # GPU重建
    ensure_ollama()
    if not start_livetalking():
        sys.exit(2)
    log("===== 换装完成, 桌宠将自动重连 =====")


if __name__ == "__main__":
    main()
