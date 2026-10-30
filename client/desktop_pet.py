#!/usr/bin/env python3
"""
AI女友透明桌面客户端 v2
- 思考云朵输入气泡(右上), 回复云朵字幕(视频下方)
- 精致换装菜单(卡片网格+新装生成)
- WebRTC收流 + 抠像 + 缩放 + 自动重连 + 音频播放
"""
import argparse
import asyncio
import glob
import json
import os
import queue as pyqueue
import subprocess
import sys
import threading
import time

import numpy as np
import cv2

from PySide6.QtCore import Qt, QTimer, Signal, QObject, QPoint
from PySide6.QtGui import QImage, QPixmap, QFont
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QFrame, QScrollArea, QGridLayout,
)

BASE_DIR = os.environ.get("GLASSMATE_HOME_ROOT") or \
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WARDROBE_DIR = os.environ.get(
    "GLASSMATE_WARDROBE", os.path.join(BASE_DIR, "wardrobe", "outfits"))


class Bridge(QObject):
    subtitle = Signal(str)
    status = Signal(str)


class RTCClient:
    """WebRTC: 视频帧队列 + 音频播放 + SSE字幕 + 自动重连"""

    def __init__(self, server, avatar, frame_q, bridge):
        self.server = server.rstrip('/')
        self.avatar = avatar
        self.frame_q = frame_q
        self.bridge = bridge
        self.session_id = None
        self._stop = threading.Event()
        threading.Thread(target=self._run, daemon=True).start()

    def stop(self):
        self._stop.set()

    def _run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        backoff = 2
        while not self._stop.is_set():
            try:
                loop.run_until_complete(self._main())
                backoff = 2
            except Exception as e:
                if self._stop.is_set():
                    break
                self.bridge.status.emit(f"reconnecting: {e}")
            self.bridge.status.emit("disconnected")
            waited = 0
            while waited < backoff and not self._stop.is_set():
                time.sleep(1)
                waited += 1
            backoff = min(backoff * 2, 30)

    async def _main(self):
        import aiohttp
        from aiortc import RTCPeerConnection, RTCSessionDescription

        pc = RTCPeerConnection()
        pc.addTransceiver("video", direction="recvonly")
        pc.addTransceiver("audio", direction="recvonly")

        video_track = []

        @pc.on("track")
        def on_track(track):
            if track.kind == "video":
                video_track.append(track)
            elif track.kind == "audio":
                threading.Thread(target=self._play_audio, args=(track,), daemon=True).start()

        offer = await pc.createOffer()
        await pc.setLocalDescription(offer)
        for _ in range(60):
            if pc.iceGatheringState == "complete" or self._stop.is_set():
                break
            await asyncio.sleep(0.05)

        payload = {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
        if self.avatar:
            payload["avatar"] = self.avatar

        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.server}/offer", json=payload) as r:
                resp = await r.json()
            self.session_id = resp.get("sessionid", "")
            await pc.setRemoteDescription(
                RTCSessionDescription(sdp=resp["sdp"], type=resp["type"]))
            self.bridge.status.emit("connected")
            threading.Thread(target=self._sse, daemon=True).start()

            while not self._stop.is_set():
                if video_track:
                    try:
                        frame = await asyncio.wait_for(video_track[0].recv(), timeout=2)
                        img = frame.to_ndarray(format="bgr24")
                        while not self.frame_q.empty():
                            try: self.frame_q.get_nowait()
                            except pyqueue.Empty: break
                        self.frame_q.put_nowait(img)
                    except asyncio.TimeoutError:
                        continue
                else:
                    await asyncio.sleep(0.05)
                if pc.connectionState in ("failed", "closed", "disconnected"):
                    break
        await pc.close()

    def _play_audio(self, track):
        import sounddevice as sd
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        stream = None
        async def consume():
            nonlocal stream
            while not self._stop.is_set():
                try:
                    frame = await asyncio.wait_for(track.recv(), timeout=2)
                    arr = frame.to_ndarray()
                    sr = frame.sample_rate
                    if stream is None or stream.samplerate != sr:
                        if stream: stream.close()
                        stream = sd.RawOutputStream(samplerate=sr,
                                                    channels=arr.shape[0],
                                                    dtype='int16')
                        stream.start()
                    data = (arr.T.astype(np.int16)).tobytes()
                    stream.write(data)
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    self.bridge.status.emit(f"audio-error: {e}")
                    return
        try:
            loop.run_until_complete(consume())
        finally:
            if stream: stream.close()

    def _sse(self):
        import urllib.request
        url = f"{self.server}/sse?sessionid={self.session_id}"
        while not self._stop.is_set():
            try:
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=300) as r:
                    for raw in r:
                        line = raw.decode('utf-8', errors='ignore').strip()
                        if not line.startswith('data:'):
                            continue
                        try:
                            d = json.loads(line[5:].strip())
                        except Exception:
                            continue
                        if isinstance(d, dict):
                            txt = d.get('text', '')
                            st = d.get('status', '')
                            if st == 'start' and txt:
                                self.bridge.subtitle.emit(txt)
                            elif st == 'end':
                                self.bridge.subtitle.emit('')
            except Exception:
                time.sleep(2)


class BgMatte:
    """通用纯色背景抠像: 绿幕用绿色主导判定, 其他纯色用色差"""

    def __init__(self, tolerance=42, feather=2, corner=40):
        self.tol = tolerance
        self.feather = feather
        self.corner = corner
        self.k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))

    def _sample_bg(self, bgr):
        h, w = bgr.shape[:2]
        c = self.corner
        patches = [bgr[0:c, 0:c], bgr[0:c, w-c:w], bgr[h-c:h, 0:c], bgr[h-c:h, w-c:w]]
        px = np.concatenate([p.reshape(-1, 3) for p in patches], axis=0).astype(np.float32)
        return px.mean(axis=0)

    def apply(self, bgr):
        bg = self._sample_bg(bgr)
        f = bgr.astype(np.float32)
        b, g, r = f[:, :, 0], f[:, :, 1], f[:, :, 2]
        is_green_bg = bool(bg[1] > bg[0] + 30 and bg[1] > bg[2] + 30)
        if is_green_bg:
            bg_bool = (g > r + 25) & (g > b + 25) & (g > 40)
        else:
            diff = np.linalg.norm(f - bg, axis=2)
            bg_bool = diff < self.tol
        bg_mask = bg_bool.astype(np.uint8) * 255
        alpha = cv2.bitwise_not(bg_mask)
        alpha = cv2.morphologyEx(alpha, cv2.MORPH_OPEN, self.k)
        alpha = cv2.morphologyEx(alpha, cv2.MORPH_CLOSE, self.k)
        n, labels, stats, _ = cv2.connectedComponentsWithStats((alpha > 127).astype(np.uint8))
        if n > 1:
            keep = np.zeros_like(alpha)
            for i in range(1, n):
                if stats[i, cv2.CC_STAT_AREA] > alpha.size * 0.002:
                    keep[labels == i] = 255
            alpha = keep
        alpha = cv2.erode(alpha, self.k, iterations=1)
        if self.feather:
            fk = self.feather * 2 + 1
            alpha = cv2.GaussianBlur(alpha, (fk, fk), 0)
        img = f
        if is_green_bg:
            b2, g2, r2 = img[:, :, 0], img[:, :, 1], img[:, :, 2]
            cap = (b2 + r2) / 2.0
            g2 = np.minimum(g2, cap)
            img = np.dstack([b2, g2, r2])
        out = img.clip(0, 255).astype(np.uint8)
        return out, alpha


CLOUD_IN_QSS = """
QFrame#cloudIn {
  background: rgba(255, 255, 255, 240);
  border-radius: 20px;
  border: 1px solid rgba(255,255,255,255);
}
QLineEdit {
  background: transparent; border: 0; color: #333;
  font-size: 13px; padding: 2px 4px;
}
QLineEdit::placeholder { color: #aaa; }
QPushButton#sendBtn {
  background: #6d5df6; color: white; border: 0; border-radius: 13px;
  font-size: 12px; padding: 4px 12px;
}
QPushButton#sendBtn:hover { background: #8274ff; }
QPushButton#iconBtn {
  background: transparent; border: 0; font-size: 15px; color: #777;
}
QPushButton#iconBtn:hover { color: #6d5df6; }
"""

CLOUD_SUB_QSS = """
QLabel#cloudSub {
  background: rgba(255, 255, 255, 235);
  color: #333;
  border-radius: 16px;
  padding: 8px 14px;
  font-size: 13px;
}
"""


class WardrobePanel(QWidget):
    """换装菜单: 无边框深色圆角面板, 卡片网格 + 新装生成"""
    apply_requested = Signal(str)
    generate_requested = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent, Qt.Window | Qt.FramelessWindowHint |
                         Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(400, 560)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        panel = QFrame()
        panel.setObjectName("panel")
        panel.setStyleSheet("""
QFrame#panel { background: #1c1c26; border-radius: 16px; border: 1px solid #33333f; }
QLabel { color: #eee; background: transparent; }
QLineEdit {
  background: #26262f; color: #fff; border: 1px solid #3a3a48;
  border-radius: 8px; padding: 7px 10px; font-size: 12px;
}
QPushButton {
  border: 0; border-radius: 8px; font-size: 12px; padding: 7px 0;
}
QPushButton#gen { background: #6d5df6; color: #fff; }
QPushButton#gen:hover { background: #8274ff; }
QPushButton#gen:disabled { background: #444; color: #888; }
QPushButton#pick { background: #2e2e3a; color: #cfc8ff; }
QPushButton#pick:hover { background: #6d5df6; color: #fff; }
QPushButton#pick:disabled { color: #666; }
QFrame#card { background: #23232e; border: 1px solid #33333f; border-radius: 12px; }
QFrame#card:hover { border: 1px solid #6d5df6; }
QScrollArea { border: 0; background: transparent; }
""")
        outer.addWidget(panel)
        v = QVBoxLayout(panel)
        v.setContentsMargins(16, 14, 16, 14)
        v.setSpacing(10)

        title_row = QHBoxLayout()
        title = QLabel("衣 橱")
        title.setStyleSheet("font-size:16px;font-weight:600;letter-spacing:4px;")
        title_row.addWidget(title, 1, Qt.AlignLeft)
        close_btn = QPushButton("×")
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet("background:transparent;color:#888;border:0;font-size:16px;")
        close_btn.clicked.connect(self.hide)
        title_row.addWidget(close_btn)
        v.addLayout(title_row)

        # 新装生成区
        gen_row = QHBoxLayout()
        self.gen_input = QLineEdit()
        self.gen_input.setPlaceholderText("描述新服装, 如: 白色JK制服, 黑色过膝袜")
        gen_row.addWidget(self.gen_input, 1)
        self.gen_btn = QPushButton("生成")
        self.gen_btn.setObjectName("gen")
        self.gen_btn.setFixedWidth(60)
        self.gen_btn.clicked.connect(self._on_generate)
        gen_row.addWidget(self.gen_btn)
        v.addLayout(gen_row)

        self.status = QLabel("")
        self.status.setStyleSheet("color:#8f8;font-size:11px;")
        self.status.setWordWrap(True)
        self.status.hide()
        v.addWidget(self.status)

        # 服装卡片网格
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        host = QWidget()
        host.setStyleSheet("background:transparent;")
        self.grid = QGridLayout(host)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(10)
        scroll.setWidget(host)
        v.addWidget(scroll, 1)
        self.reload()

    def reload(self):
        while self.grid.count():
            it = self.grid.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()
        outfits = sorted(glob.glob(os.path.join(WARDROBE_DIR, "*")))
        if not outfits:
            tip = QLabel("衣橱空空如也\n在上方描述你想要的服装, 点生成")
            tip.setAlignment(Qt.AlignCenter)
            tip.setStyleSheet("color:#888;font-size:12px;")
            self.grid.addWidget(tip, 0, 0, 1, 2)
            return
        for i, d in enumerate(outfits):
            name = os.path.basename(d)
            card = QFrame()
            card.setObjectName("card")
            card.setFixedSize(172, 280)
            cv = QVBoxLayout(card)
            cv.setContentsMargins(8, 8, 8, 8)
            cv.setSpacing(6)
            thumb = QLabel()
            thumb.setFixedSize(156, 200)
            thumb.setAlignment(Qt.AlignCenter)
            thumb.setStyleSheet("background:#14141c;border-radius:8px;")
            pv = os.path.join(d, "thumbnail.png")
            if not os.path.exists(pv):
                pv = os.path.join(d, "preview.png")
            if not os.path.exists(pv):
                pv = os.path.join(d, "final.png")
            if os.path.exists(pv):
                thumb.setPixmap(QPixmap(pv).scaled(
                    156, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            cv.addWidget(thumb)
            lab = QLabel(name)
            lab.setAlignment(Qt.AlignCenter)
            lab.setStyleSheet("font-size:12px;")
            cv.addWidget(lab)
            btn = QPushButton("换上")
            btn.setObjectName("pick")
            btn.clicked.connect(lambda _=False, n=name, b=btn: self._on_pick(n, b))
            cv.addWidget(btn)
            cv.addStretch(1)
            self.grid.addWidget(card, i // 2, i % 2, Qt.AlignTop | Qt.AlignHCenter)
        self.grid.setColumnStretch(0, 1)
        self.grid.setColumnStretch(1, 1)
        self.grid.setRowStretch(99, 1)

    def _on_pick(self, name, btn):
        btn.setEnabled(False)
        btn.setText("换装中...")
        self.status.setText(f"正在换上「{name}」, 约2-3分钟, 她会暂时离开~")
        self.status.show()
        self.apply_requested.emit(name)
        self.hide()

    def _on_generate(self):
        desc = self.gen_input.text().strip()
        if not desc:
            return
        name = desc[:10]
        self.gen_btn.setEnabled(False)
        self.gen_btn.setText("生成中")
        self.status.setText(f"AI正在缝制「{name}」... 约1-2分钟 (GPU忙碌时会排队)")
        self.status.show()
        self.generate_requested.emit(desc, name)

    def gen_done(self, ok, name):
        self.gen_btn.setEnabled(True)
        self.gen_btn.setText("生成")
        self.gen_input.clear()
        if ok:
            self.status.setText(f"「{name}」已入橱, 点卡片换上")
            self.reload()
        else:
            self.status.setText("生成失败, 看看日志 assets/outfit_*.png")
        self.status.show()


class PetWindow(QWidget):
    def __init__(self, args):
        super().__init__()
        self.args = args
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        w = args.width
        geo = QApplication.primaryScreen().availableGeometry()
        self.setGeometry(geo.width() - w - 60, geo.height() - args.height - 160,
                         w, args.height + 90)

        self.frame_q = pyqueue.Queue(maxsize=4)
        self.matte = BgMatte(tolerance=args.tolerance)
        self.sub_until = 0
        self.cur_sub = ""
        self.zoom = 1.0

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        # ---- 思考云朵输入条 (右上角) ----
        cloud_row = QHBoxLayout()
        cloud_row.addStretch(1)
        self.cloud = QFrame()
        self.cloud.setObjectName("cloudIn")
        self.cloud.setStyleSheet(CLOUD_IN_QSS)
        self.cloud.setFixedWidth(int(w * 0.94))
        ch = QHBoxLayout(self.cloud)
        ch.setContentsMargins(14, 5, 8, 5)
        ch.setSpacing(4)
        self.input = QLineEdit()
        self.input.setPlaceholderText("想一想...")
        self.input.returnPressed.connect(self.send_msg)
        ch.addWidget(self.input, 1)
        send = QPushButton("说")
        send.setObjectName("sendBtn")
        send.setFixedHeight(26)
        send.clicked.connect(self.send_msg)
        ch.addWidget(send)
        brk = QPushButton("⏸")
        brk.setObjectName("iconBtn")
        brk.setToolTip("打断")
        brk.setFixedWidth(26)
        brk.clicked.connect(self.interrupt)
        ch.addWidget(brk)
        self.btn_wardrobe = QPushButton("👗")
        self.btn_wardrobe.setObjectName("iconBtn")
        self.btn_wardrobe.setToolTip("衣橱")
        self.btn_wardrobe.setFixedWidth(28)
        self.btn_wardrobe.clicked.connect(self.open_wardrobe)
        ch.addWidget(self.btn_wardrobe)
        close_btn = QPushButton("×")
        close_btn.setObjectName("iconBtn")
        close_btn.setFixedWidth(20)
        close_btn.clicked.connect(self.close)
        ch.addWidget(close_btn)
        cloud_row.addWidget(self.cloud)
        root.addLayout(cloud_row)

        # ---- 视频 ----
        self.video_label = QLabel()
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setText("连接中...")
        self.video_label.setStyleSheet("color:#bbb;background:transparent;font-size:13px;")
        root.addWidget(self.video_label)

        # ---- 她的回复云朵 (视频下方居中) ----
        sub_row = QHBoxLayout()
        sub_row.addStretch(1)
        self.sub_label = QLabel()
        self.sub_label.setObjectName("cloudSub")
        self.sub_label.setStyleSheet(CLOUD_SUB_QSS)
        self.sub_label.setWordWrap(True)
        self.sub_label.setAlignment(Qt.AlignCenter)
        self.sub_label.setMaximumWidth(int(w * 0.9))
        self.sub_label.hide()
        sub_row.addWidget(self.sub_label)
        sub_row.addStretch(1)
        root.addLayout(sub_row)

        self.wardrobe = None
        self.bridge = Bridge()
        self.bridge.subtitle.connect(self.on_subtitle)
        self.bridge.status.connect(self.on_status)
        self.rtc = RTCClient(args.server, args.avatar, self.frame_q, self.bridge)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.render)
        self.timer.start(33)
        self._drag = None
        self.apply_zoom()

    # ----- 尺寸 -----
    def apply_zoom(self):
        w = max(160, int(self.args.width * self.zoom))
        h = max(200, int(self.args.height * self.zoom))
        self.video_label.setFixedSize(w, h)
        self.cloud.setFixedWidth(int(w * 0.94))
        self.sub_label.setMaximumWidth(int(w * 0.9))
        self.setFixedSize(w + 8, h + 110)

    def set_zoom(self, z):
        self.zoom = max(0.4, min(2.5, z))
        self.apply_zoom()

    def wheelEvent(self, e):
        delta = 1 if e.angleDelta().y() > 0 else -1
        self.set_zoom(self.zoom * (1.1 ** delta))
        e.accept()

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Plus, Qt.Key_Equal):
            self.set_zoom(self.zoom * 1.15)
        elif e.key() in (Qt.Key_Minus, Qt.Key_Underscore):
            self.set_zoom(self.zoom / 1.15)
        elif e.key() == Qt.Key_0:
            self.set_zoom(1.0)
        elif e.key() == Qt.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(e)

    # ----- 状态/字幕 -----
    def on_status(self, s):
        if s == "connected":
            if self.video_label.text() in ("连接中...", "连接断开, 自动重连中...") or \
               "换装" in self.video_label.text():
                self.video_label.setText("")
        elif s == "disconnected":
            self.video_label.setText("连接断开, 自动重连中...")
        elif s.startswith("reconnecting"):
            pass
        elif s.startswith("webrtc-error"):
            self.video_label.setText(f"连接失败\n{s}\n确认LiveTalking已启动")

    def on_subtitle(self, t):
        if t:
            self.cur_sub = t
            self.sub_until = time.time() + max(3.0, len(t) * 0.4)
            self.sub_label.setText(t)
            self.sub_label.show()
        else:
            self.cur_sub = ""
            self.sub_label.hide()

    # ----- 换装 -----
    def open_wardrobe(self):
        if self.wardrobe is None:
            self.wardrobe = WardrobePanel()
            self.wardrobe.apply_requested.connect(self.apply_outfit)
            self.wardrobe.generate_requested.connect(self.generate_outfit)
        if self.wardrobe.isVisible():
            self.wardrobe.hide()
            return
        self.wardrobe.reload()
        g = self.btn_wardrobe.mapToGlobal(QPoint(0, 0))
        x = max(20, g.x() - 360)
        y = max(20, g.y() - 560)
        self.wardrobe.move(x, y)
        self.wardrobe.show()
        self.wardrobe.raise_()
        self.wardrobe.activateWindow()

    def apply_outfit(self, name):
        self.video_label.setText("换装中, 约2-3分钟...")
        threading.Thread(target=self._run_script,
                         args=(["apply_outfit.py", name], "apply"), daemon=True).start()

    def generate_outfit(self, desc, name):
        threading.Thread(target=self._run_script,
                         args=(["change_outfit.py", desc, "--name", name], "gen"),
                         daemon=True).start()

    def _run_script(self, argv, kind):
        script = os.path.join(BASE_DIR, argv[0])
        try:
            r = subprocess.run([sys.executable, script] + argv[1:],
                               cwd=BASE_DIR, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=2400)
            ok = r.returncode == 0
            if kind == "gen":
                if self.wardrobe:
                    # 通过信号回主线程
                    QTimer.singleShot(0, lambda: self.wardrobe.gen_done(ok, argv[2]))
            else:
                if ok:
                    self.bridge.status.emit("connected")
                else:
                    self.bridge.status.emit(
                        "webrtc-error: 换装失败 " + (r.stdout or r.stderr)[-150:])
        except Exception as e:
            self.bridge.status.emit(f"webrtc-error: {e}")

    # ----- 聊天 -----
    def send_msg(self):
        text = self.input.text().strip()
        if not text:
            return
        self.input.clear()
        threading.Thread(target=self._post, args=("/human", {
            "text": text, "type": "chat", "interrupt": True,
            "sessionid": self.rtc.session_id or ""}), daemon=True).start()

    def interrupt(self):
        threading.Thread(target=self._post, args=("/interrupt_talk", {
            "sessionid": self.rtc.session_id or ""}), daemon=True).start()

    def _post(self, path, body):
        import urllib.request
        try:
            req = urllib.request.Request(
                self.args.server.rstrip('/') + path,
                data=json.dumps(body).encode('utf-8'),
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=15) as r:
                r.read()
        except Exception as e:
            self.bridge.status.emit(f"send-error: {e}")

    # ----- 渲染 -----
    def render(self):
        try:
            img = self.frame_q.get_nowait()
        except pyqueue.Empty:
            if self.cur_sub and time.time() > self.sub_until:
                self.on_subtitle("")
            return
        if self.args.chroma:
            img, alpha = self.matte.apply(img)
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            rgba = np.dstack([img, alpha])
        else:
            rgba = cv2.cvtColor(img, cv2.COLOR_BGR2RGBA)
        tw, th = self.video_label.width(), self.video_label.height()
        interp = cv2.INTER_AREA if tw < rgba.shape[1] else cv2.INTER_LANCZOS4
        rgba = cv2.resize(rgba, (tw, th), interpolation=interp)
        h, w, ch = rgba.shape
        qimg = QImage(rgba.data, w, h, ch * w, QImage.Format_RGBA8888).copy()
        self.video_label.setPixmap(QPixmap.fromImage(qimg))

    # ----- 拖动 -----
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            e.accept()

    def mouseMoveEvent(self, e):
        if self._drag and (e.buttons() & Qt.LeftButton):
            self.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, e):
        self._drag = None

    def closeEvent(self, e):
        self.rtc.stop()
        super().closeEvent(e)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", default="http://127.0.0.1:8010")
    ap.add_argument("--avatar", default="wav2lip256_green")
    ap.add_argument("--width", type=int, default=340)
    ap.add_argument("--height", type=int, default=600)
    ap.add_argument("--tolerance", type=int, default=42)
    ap.add_argument("--chroma", action="store_true", default=True)
    ap.add_argument("--no-chroma", dest="chroma", action="store_false")
    args = ap.parse_args()
    app = QApplication(sys.argv)
    app.setApplicationName("AI女友")
    win = PetWindow(args)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
