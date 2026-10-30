# -*- coding: utf-8 -*-
"""分段录制工具: 录制当前桌宠状态的若干动作片段到指定目录
用法: python record_seg.py <输出目录> <动作序列>
动作序列用逗号分隔: talk:文本=录说话, wardrobe=开衣橱录面板, pick:名称=触发换装录提示, wait=纯录当前画面
"""
import ctypes
import ctypes.wintypes as wt
import os
import sys
import time

sys.path.insert(0, r"D:\ai-companion")
from win_tool import find_windows, shot  # noqa: E402
from PIL import Image  # noqa: E402

TRIGGER_DIR = r"D:\ai-companion\assets"


def main_hwnd():
    for w in find_windows():
        if w[1] == 'AI女友' and w[5] != 400 and w[7]:
            return w[0]
    return None


def panel_hwnd():
    for w in find_windows():
        if w[1] in ('GlassMate衣橱', 'AI女友') and w[5] == 400 and w[7]:
            return w[0]
    return None


def trigger(name, arg=""):
    open(os.path.join(TRIGGER_DIR, f"_trigger_{name}"), "w", encoding="utf-8").write(arg)
    time.sleep(1.0)


class Recorder:
    def __init__(self, outdir):
        self.outdir = outdir
        os.makedirs(outdir, exist_ok=True)
        self.n = 0

    def grab(self, hwnd):
        p = os.path.join(self.outdir, f"s_{self.n:04d}.png")
        shot(hwnd, p)
        self.n += 1
        return p

    def record(self, hwnd, seconds, fps=6):
        for _ in range(int(seconds * fps)):
            t0 = time.time()
            self.grab(hwnd)
            dt = time.time() - t0
            if dt < 1.0 / fps:
                time.sleep(1.0 / fps - dt)


def main():
    outdir = sys.argv[1]
    actions = sys.argv[2].split(",") if len(sys.argv) > 2 else []
    hwnd = main_hwnd()
    assert hwnd, "桌宠窗口未找到"
    rec = Recorder(outdir)
    print(f"window={hwnd} outdir={outdir}")

    for act in actions:
        if act.startswith("talk:"):
            text = act[5:]
            trigger("send", text)
            print(f"  talk '{text}' 录24s")
            rec.record(hwnd, 24, 6)
        elif act == "wardrobe":
            trigger("wardrobe")
            time.sleep(1.5)
            ph = panel_hwnd()
            if ph:
                print("  录衣橱面板3s")
                rec.record(ph, 3, 6)
                trigger("wardrobe_close")
                time.sleep(0.8)
            else:
                print("  衣橱面板未找到")
        elif act.startswith("pick:"):
            name = act[5:]
            trigger("pick", name)
            print(f"  触发换装 '{name}' 录提示4s")
            rec.record(hwnd, 4, 4)
        elif act == "wait":
            print("  录当前画面6s")
            rec.record(hwnd, 6, 6)
        else:
            print(f"  未知动作 {act}")

    print(f"完成, 共{rec.n}帧 -> {outdir}")


if __name__ == "__main__":
    main()
