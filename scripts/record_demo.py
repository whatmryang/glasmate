# -*- coding: utf-8 -*-
"""录制桌宠窗口演示GIF (3秒, 8fps)"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
from win_tool import find_windows, shot  # noqa: E402

TITLE = os.environ.get("GLASMATE_TITLE", "AI女友")
wins = [w for w in find_windows() if w[1] == TITLE and w[5] != 400 and w[7]]
if not wins:
    print("桌宠窗口未找到")
    sys.exit(1)
hwnd = wins[0][0]

from PIL import Image
frames = []
for i in range(24):  # 3秒 x 8fps
    path = os.path.join(os.environ.get("TEMP", "."), "_gif_tmp.png")
    shot(hwnd, path)
    im = Image.open(path).convert("RGB")
    # 缩到合适大小
    w, h = im.size
    nw = 320
    im = im.resize((nw, int(h * nw / w)))
    frames.append(im)
    time.sleep(0.125)

out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "demo.gif")
frames[0].save(out, save_all=True, append_images=frames[1:],
               duration=125, loop=0, optimize=True)
import os
print("saved", out, os.path.getsize(out) // 1024, "KB")
