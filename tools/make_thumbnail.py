# -*- coding: utf-8 -*-
"""从final.png(绿幕)生成深色底缩略图 thumbnail.png, 供衣橱卡片显示。纯CPU。"""
import glob, os, sys
import cv2
import numpy as np


def green_matte(bgr):
    f = bgr.astype(np.float32)
    b, g, r = f[:, :, 0], f[:, :, 1], f[:, :, 2]
    bg_bool = (g > r + 25) & (g > b + 25) & (g > 40)
    bg_mask = bg_bool.astype(np.uint8) * 255
    alpha = cv2.bitwise_not(bg_mask)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    alpha = cv2.morphologyEx(alpha, cv2.MORPH_OPEN, k)
    alpha = cv2.morphologyEx(alpha, cv2.MORPH_CLOSE, k)
    n, labels, stats, _ = cv2.connectedComponentsWithStats((alpha > 127).astype(np.uint8))
    if n > 1:
        keep = np.zeros_like(alpha)
        for i in range(1, n):
            if stats[i, cv2.CC_STAT_AREA] > alpha.size * 0.002:
                keep[labels == i] = 255
        alpha = keep
    alpha = cv2.erode(alpha, k, iterations=1)
    alpha = cv2.GaussianBlur(alpha, (5, 5), 0)
    cap = (b + r) / 2.0
    g2 = np.minimum(g, cap)
    out = np.dstack([b, g2, r]).clip(0, 255).astype(np.uint8)
    return out, alpha


def make_thumb(final_png, out_png, thumb_w=156, thumb_h=200):
    # cv2读不了中文路径, 用imdecode
    data = np.fromfile(final_png, dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        return False
    rgb, alpha = green_matte(img)
    # 按人物包围盒裁剪(去掉大片空绿), 留5%边距
    ys, xs = np.where(alpha > 40)
    if len(xs) and len(ys):
        x0, x1 = xs.min(), xs.max()
        y0, y1 = ys.min(), ys.max()
        bw, bh = x1 - x0, y1 - y0
        x0 = max(0, x0 - int(bw * 0.05)); x1 = min(alpha.shape[1], x1 + int(bw * 0.05))
        y0 = max(0, y0 - int(bh * 0.05)); y1 = min(alpha.shape[0], y1 + int(bh * 0.05))
        rgb = rgb[y0:y1, x0:x1]
        alpha = alpha[y0:y1, x0:x1]
    # 深色卡片底 #23232e (BGR)
    bg = np.zeros_like(rgb)
    bg[:] = (0x2e, 0x23, 0x23)
    a3 = alpha[:, :, None] / 255.0
    comp = (rgb * a3 + bg * (1 - a3)).astype(np.uint8)
    # contain模式: 全图缩放贴到深色底, 不裁头
    H, W = comp.shape[:2]
    scale = min(thumb_w / W, thumb_h / H)
    nW, nH = int(W * scale), int(H * scale)
    resized = cv2.resize(comp, (nW, nH), interpolation=cv2.INTER_AREA)
    canvas = np.zeros((thumb_h, thumb_w, 3), dtype=np.uint8)
    canvas[:] = (0x2e, 0x23, 0x23)
    x0 = (thumb_w - nW) // 2
    y0 = (thumb_h - nH) // 2
    canvas[y0:y0 + nH, x0:x0 + nW] = resized
    comp = canvas
    # cv2写不了中文路径, 用imencode
    ok, buf = cv2.imencode('.png', comp)
    if ok:
        buf.tofile(out_png)
    return ok


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import gm_config as C
    dirs = sys.argv[1:] or sorted(glob.glob(
        os.path.join(C.WARDROBE, "outfits", "*")))
    for d in dirs:
        final = os.path.join(d, "final.png")
        thumb = os.path.join(d, "thumbnail.png")
        if os.path.exists(final):
            ok = make_thumb(final, thumb)
            print(("OK " if ok else "FAIL ") + thumb)
