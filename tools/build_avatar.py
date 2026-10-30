# -*- coding: utf-8 -*-
"""绿幕形象 -> LiveTalking avatar 全流程
前提: assets/green_gf_*.png 已由 gen_green_img.py 生成
步骤: 1) 挑图(人工可替换 selected.png) 2) 静图->微动视频 3) genavatar 4) 完成提示
"""
import glob, os, shutil, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gm_config as C
C.ensure_dirs()

BASE = C.REPO_ROOT
LT = C.LT_HOME
PY = C.lt_python()
ASSETS = C.ASSETS
SELECTED = os.path.join(ASSETS, "selected.png")
VIDEO = os.path.join(ASSETS, "green_avatar.mp4")
AVATAR_ID = C.AVATAR_ID

def main():
    # 0) 优先用绿幕合成版(抠像干净)
    gs = os.path.join(ASSETS, "greenscreen.png")
    if os.path.exists(gs):
        shutil.copy(gs, SELECTED)
        print("使用绿幕合成版 greenscreen.png")
    # 1) 选图: 若用户已放 selected.png 就用它, 否则用第一张
    elif not os.path.exists(SELECTED):
        cands = sorted(glob.glob(os.path.join(ASSETS, "green_gf_*.png")))
        assert cands, "assets目录下没有 green_gf_*.png, 先运行 gen_green_img.py"
        shutil.copy(cands[0], SELECTED)
        print(f"自动选择 {cands[0]} -> selected.png (可手动替换后重跑)")

    # 2) 静图 -> 微动视频
    r = subprocess.run([PY, os.path.join(BASE, "img2avatar_video.py"),
                        SELECTED, VIDEO, "200"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    print(r.stdout, r.stderr)
    assert os.path.exists(VIDEO), "视频生成失败"

    # 3) genavatar (GPU任务, 检测人脸生成full_imgs/face_imgs/coords.pkl)
    cmd = [PY, "-m", "avatars.wav2lip.genavatar",
           "--video_path", VIDEO, "--img_size", "256",
           "--avatar_id", AVATAR_ID]
    print("运行:", " ".join(cmd))
    r = subprocess.run(cmd, cwd=LT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    print(r.stdout[-3000:] if r.stdout else "")
    print(r.stderr[-3000:] if r.stderr else "", file=sys.stderr)

    out_dir = os.path.join(LT, "data", "avatars", AVATAR_ID)
    n_full = len(glob.glob(os.path.join(out_dir, "full_imgs", "*.png")))
    n_face = len(glob.glob(os.path.join(out_dir, "face_imgs", "*.png")))
    print(f"avatar生成结果: full_imgs={n_full} face_imgs={n_face}")
    assert n_full > 0 and n_face > 0, "genavatar未产出图片, 检查上面报错"
    print(f"DONE avatar_id={AVATAR_ID}")

if __name__ == "__main__":
    main()
