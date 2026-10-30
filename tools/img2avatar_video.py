# -*- coding: utf-8 -*-
"""绿幕静图 -> 微动循环视频 (LiveTalking avatar素材)
用法: python img2avatar_video.py <输入png> <输出mp4> [帧数]
原理: 对静图施加缓慢的呼吸缩放+微小水平漂移，生成平滑循环视频
要求: 输入为绿幕全身像, 输出 25fps
"""
import sys, os
import cv2
import numpy as np

def main():
    src, dst = sys.argv[1], sys.argv[2]
    n_frames = int(sys.argv[3]) if len(sys.argv) > 3 else 200  # 25fps x 8s
    fps = 25

    img = cv2.imread(src)
    assert img is not None, f"读不到 {src}"
    H, W = img.shape[:2]

    # 输出尺寸：保持纵横比，长边对齐960（够桌宠窗口用，控制显存/体积）
    scale = 960.0 / max(H, W)
    OW, OH = int(W * scale) // 2 * 2, int(H * scale) // 2 * 2
    img = cv2.resize(img, (OW, OH))

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    vw = cv2.VideoWriter(dst, fourcc, fps, (OW, OH))
    assert vw.isOpened(), "VideoWriter打不开"

    cx, cy = OW / 2.0, OH / 2.0
    for i in range(n_frames):
        t = i / n_frames
        # 呼吸缩放: 1.00 <-> 1.012 正弦循环（首尾相接无缝）
        s = 1.0 + 0.012 * np.sin(2 * np.pi * t)
        # 微小水平漂移 ±3px
        dx = 3.0 * np.sin(2 * np.pi * t + 1.0)
        # 微小垂直漂移 ±2px
        dy = 2.0 * np.sin(2 * np.pi * t + 2.0)
        M = cv2.getRotationMatrix2D((cx, cy), 0, s)
        M[0, 2] += dx
        M[1, 2] += dy
        frame = cv2.warpAffine(img, M, (OW, OH),
                               flags=cv2.INTER_LINEAR,
                               borderMode=cv2.BORDER_REPLICATE)
        vw.write(frame)

    vw.release()
    print(f"DONE {dst} frames={n_frames} size={OW}x{OH} fps={fps}")

if __name__ == "__main__":
    main()
