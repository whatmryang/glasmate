# -*- coding: utf-8 -*-
"""桌宠窗口工具: 找窗口/截图/点击 (供测试复用)"""
import ctypes
import ctypes.wintypes as wt
import sys
import time

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
P = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)


class BIH(ctypes.Structure):
    _fields_ = [("biSize", wt.DWORD), ("biWidth", ctypes.c_long), ("biHeight", ctypes.c_long),
                ("biPlanes", wt.WORD), ("biBitCount", wt.WORD), ("biCompression", wt.DWORD),
                ("biSizeImage", wt.DWORD), ("biXPelsPerMeter", ctypes.c_long),
                ("biYPelsPerMeter", ctypes.c_long), ("biClrUsed", wt.DWORD), ("biClrImportant", wt.DWORD)]


def find_windows():
    """返回所有Qt窗口: (hwnd, title, class, l, t, w, h, visible)"""
    wins = []

    def cb(h, l):
        n = user32.GetWindowTextLengthW(h)
        b = ctypes.create_unicode_buffer(n + 1)
        if n:
            user32.GetWindowTextW(h, b, n + 1)
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(h, cls, 256)
        if 'Qt' in cls.value:
            r = wt.RECT()
            user32.GetWindowRect(h, ctypes.byref(r))
            wins.append((h, b.value, cls.value, r.left, r.top,
                         r.right - r.left, r.bottom - r.top,
                         bool(user32.IsWindowVisible(h))))
        return True
    user32.EnumWindows(P(cb), 0)
    return wins


def shot(hwnd, path):
    r = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    w, h = r.right - r.left, r.bottom - r.top
    hdc = user32.GetDC(0)
    mem = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    gdi32.SelectObject(mem, bmp)
    user32.PrintWindow(hwnd, mem, 2)
    bmi = BIH()
    bmi.biSize = ctypes.sizeof(BIH)
    bmi.biWidth, bmi.biHeight = w, -h
    bmi.biPlanes, bmi.biBitCount = 1, 32
    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(mem, bmp, 0, h, buf, ctypes.byref(bmi), 0)
    from PIL import Image
    img = Image.frombuffer('RGBA', (w, h), buf, 'raw', 'BGRA', 0, 1)
    img.convert('RGB').save(path)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mem)
    user32.ReleaseDC(0, hdc)
    return w, h


def click(x, y):
    user32.SetCursorPos(int(x), int(y))
    time.sleep(0.25)
    user32.mouse_event(0x0002, 0, 0, 0, 0)
    time.sleep(0.05)
    user32.mouse_event(0x0004, 0, 0, 0, 0)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "list":
        for w in find_windows():
            print(w)
    elif cmd == "shot":
        hwnd = int(sys.argv[2])
        out = sys.argv[3]
        print(shot(hwnd, out))
    elif cmd == "click":
        click(float(sys.argv[2]), float(sys.argv[3]))
        print("clicked")
