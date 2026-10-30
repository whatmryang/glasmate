# -*- coding: utf-8 -*-
"""分镜合成演示GIF: 标题卡 + JK说话 + 衣橱面板 + 换装完成展示"""
from PIL import Image, ImageDraw, ImageFont
import glob, os

W, H = 288, 587

def load_font(size):
    for fp in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf"):
        if os.path.exists(fp):
            return ImageFont.truetype(fp, size)
    return ImageFont.load_default()

def title_card(text, sub=""):
    im = Image.new("RGB", (W, H), (18, 18, 24))
    d = ImageDraw.Draw(im)
    f1 = load_font(24)
    f2 = load_font(13)
    bb = d.textbbox((0, 0), text, font=f1)
    d.text(((W - (bb[2] - bb[0])) // 2, H // 2 - 40), text, font=f1, fill=(255, 255, 255))
    if sub:
        bb2 = d.textbbox((0, 0), sub, font=f2)
        d.text(((W - (bb2[2] - bb2[0])) // 2, H // 2 + 8), sub, font=f2, fill=(150, 150, 170))
    return im

def fit(im):
    w0, h0 = im.size
    im = im.resize((W, int(h0 * W / w0)))
    if im.size != (W, H):
        c = Image.new("RGB", (W, H), (0, 0, 0))
        c.paste(im, ((W - im.width) // 2, (H - im.height) // 2))
        im = c
    return im

def load_frames(dirp, step, maxn):
    fs = sorted(glob.glob(os.path.join(dirp, "s_*.png")))
    out = []
    for fp in fs[::step][:maxn]:
        out.append(fit(Image.open(fp).convert("RGB")))
    return out

def static_frames(img_path, count):
    im = fit(Image.open(img_path).convert("RGB"))
    return [im.copy() for _ in range(count)]

frames = []
# 幕1: 说话
frames += [title_card("陪她说话", "本地LLM · 实时语音 · 口型同步")] * 7
frames += load_frames(r"D:\ai-companion\_seg_jk", step=6, maxn=30)
# 幕2: 衣橱
frames += [title_card("打开衣橱", "AI生成任意服装 · 一键换上")] * 7
frames += static_frames(r"D:\ai-companion\wardrobe_panel.png", 10)
# 幕3: 换装完成
frames += [title_card("换装完成", "红裙 → JK制服 · 全自动2分钟")] * 7
jk2 = load_frames(r"D:\ai-companion\_seg_jk", step=5, maxn=24)
frames += jk2[-14:]

q = [f.quantize(colors=64, method=Image.MEDIANCUT) for f in frames]
out = r"D:\GlasMate\docs\demo.gif"
q[0].save(out, save_all=True, append_images=q[1:], duration=180, loop=0, optimize=True)
print(f"saved {out}: {len(frames)} frames, {os.path.getsize(out)//1024}KB, ~{len(frames)*0.18:.0f}s")
