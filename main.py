import os
import json
import asyncio
import threading
import websockets
import base64
import math
import random

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.widget import Widget
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.graphics import (
    Color, Ellipse, Rectangle, Line, RoundedRectangle
)
from kivy.properties import (
    StringProperty, BooleanProperty,
    NumericProperty, ColorProperty
)
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.metrics import dp, sp
from kivy.utils import platform

# ── Android permissions ────────────────────────────────────────────────────
if platform == 'android':
    from android.permissions import request_permissions, Permission
    request_permissions([Permission.INTERNET, Permission.RECORD_AUDIO])

# ══════════════════════════════════════════════════════════════════════════════
# CONFIG & MEMORY
# ══════════════════════════════════════════════════════════════════════════════

API_KEY     = "AIzaSyA1LZ62408EQv54cQki_gTC5wMGEu2MHjw"
WS_URL      = (
    "wss://generativelanguage.googleapis.com/ws/"
    "google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent"
    "?key=" + API_KEY
)
MODEL       = "models/gemini-2.0-flash-live-001"
MEMORY_FILE = "mpro_memory.json"

SYSTEM_PROMPT = (
    "Tu MPro hai — ek smart, fast aur helpful AI voice assistant. "
    "Hinglish mein baat kar. Short aur clear replies de. "
    "User ko feel ho ki tu unka personal AI assistant hai."
)

def get_memory_local():
    if not os.path.exists(MEMORY_FILE):
        return []
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_memory_local(text: str):
    memories = get_memory_local()
    memories.append(text)
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(memories, f, indent=2, ensure_ascii=False)

def frame(obj: dict) -> bytes:
    return json.dumps(obj).encode("utf-8")

# ── Window ─────────────────────────────────────────────────────────────────
Window.clearcolor = (0.035, 0.039, 0.055, 1)

# ══════════════════════════════════════════════════════════════════════════════
# STATUS CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════

STATUS_IDLE       = "idle"
STATUS_CONNECTING = "connecting"
STATUS_LISTENING  = "listening"
STATUS_THINKING   = "thinking"
STATUS_SPEAKING   = "speaking"
STATUS_ERROR      = "error"

STATUS_META = {
    STATUS_IDLE:       {"text": "Idle",        "sub": "Tap to connect",          "color": [0.4,  0.4,  0.5,  1]},
    STATUS_CONNECTING: {"text": "Connecting…", "sub": "Linking to Gemini API",   "color": [0.2,  0.6,  1.0,  1]},
    STATUS_LISTENING:  {"text": "Listening…",  "sub": "Speak your command",      "color": [0.0,  0.9,  1.0,  1]},
    STATUS_THINKING:   {"text": "Thinking…",   "sub": "Processing with Gemini",  "color": [0.2,  0.5,  1.0,  1]},
    STATUS_SPEAKING:   {"text": "Speaking",    "sub": "MPro is responding",      "color": [0.0,  1.0,  0.7,  1]},
    STATUS_ERROR:      {"text": "Error",       "sub": "Check connection/API key","color": [1.0,  0.3,  0.3,  1]},
}

# ══════════════════════════════════════════════════════════════════════════════
# CUSTOM WIDGETS
# ══════════════════════════════════════════════════════════════════════════════

class PulseRing(Widget):
    ring_color  = ColorProperty([0.0, 0.85, 1.0, 0.6])
    active      = BooleanProperty(False)
    pulse_speed = NumericProperty(1.4)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._rings = []
        self._time  = 0.0
        Clock.schedule_interval(self._tick, 1 / 60)

    def _tick(self, dt):
        if not self.active:
            self._rings = []
            self.canvas.clear()
            return
        self._time += dt * self.pulse_speed
        spawn_interval = 0.55 / self.pulse_speed
        if not self._rings or self._time - self._rings[-1][2] >= spawn_interval:
            self._rings.append([1.0, 0.0, self._time])
        alive = []
        for ring in self._rings:
            age   = (self._time - ring[2]) * self.pulse_speed
            frac  = age / 1.6
            alpha = max(0.0, 1.0 - frac)
            if alpha > 0.01:
                ring[0] = alpha
                ring[1] = frac
                alive.append(ring)
        self._rings = alive
        self._redraw()

    def _redraw(self):
        self.canvas.clear()
        cx, cy = self.center
        max_r  = min(self.width, self.height) * 0.52
        with self.canvas:
            for ring in self._rings:
                alpha, frac, _ = ring
                r = max_r * frac
                rc, gc, bc, _ = self.ring_color
                Color(rc, gc, bc, alpha * 0.55)
                Line(circle=(cx, cy, r), width=dp(1.8))


class WaveformBars(Widget):
    active    = BooleanProperty(False)
    bar_color = ColorProperty([0.0, 0.85, 1.0, 1.0])
    bar_count = NumericProperty(18)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._time   = 0.0
        self._phases = [random.uniform(0, math.pi * 2) for _ in range(30)]
        self._speeds = [random.uniform(2.5, 4.5)       for _ in range(30)]
        Clock.schedule_interval(self._tick, 1 / 60)

    def _tick(self, dt):
        self._time += dt
        self._redraw()

    def _redraw(self):
        self.canvas.clear()
        if not self.active:
            return
        n     = int(self.bar_count)
        w, h  = self.width, self.height
        gap   = dp(3)
        bar_w = max((w - gap * (n - 1)) / n, dp(3))
        r, g, b, a = self.bar_color
        with self.canvas:
            for i in range(n):
                t    = self._time
                wave = (
                    math.sin(t * self._speeds[i]       + self._phases[i])       * 0.35 +
                    math.sin(t * self._speeds[i] * 1.7 + self._phases[i] * 0.7) * 0.20 +
                    0.45
                )
                wave  = max(0.08, min(wave, 1.0))
                bar_h = h * wave
                x     = i * (bar_w + gap)
                y     = (h - bar_h) / 2
                dist  = abs(i - n / 2) / (n / 2)
                Color(r, g, b, a * (1.0 - dist * 0.35))
                RoundedRectangle(pos=(x, y), size=(bar_w, bar_h), radius=[dp(2)])

# ══════════════════════════════════════════════════════════════════════════════
# ROOT SCREEN
# ══════════════════════════════════════════════════════════════════════════════

class MPROScreen(FloatLayout):
    status_key    = StringProperty(STATUS_IDLE)
    status_text   = StringProperty("Idle")
    status_sub    = StringProperty("Tap to connect")
    status_color  = ColorProperty([0.4, 0.4, 0.5, 1])
    connected     = BooleanProperty(False)
    duration_text = StringProperty("00:00")
    exchange_text = StringProperty("0")

    def setup(self, app):
        self._app = app

    def set_status(self, key: str):
        meta = STATUS_META.get(key, STATUS_META[STATUS_IDLE])
        self.status_key  = key
        self.status_text = meta["text"]
        self.status_sub  = meta["sub"]
        Clock.schedule_once(lambda dt: setattr(self, "status_color", meta["color"]), 0)

    def on_mic_press(self):
        if not self.connected:
            self.connected = True
            self.set_status(STATUS_CONNECTING)
            self._app.start_session()
        else:
            self.connected = False
            self.set_status(STATUS_IDLE)
            self._app.end_session()

# ══════════════════════════════════════════════════════════════════════════════
# KV LAYOUT
# ══════════════════════════════════════════════════════════════════════════════

KV = """
#:import dp  kivy.metrics.dp
#:import sp  kivy.metrics.sp

<MPROScreen>:
    canvas.before:
        Color:
            rgba: 0.035, 0.039, 0.055, 1
        Rectangle:
            pos: self.pos
            size: self.size
        Color:
            rgba: 0.0, 0.45, 0.75, 0.07
        Ellipse:
            pos: -self.width * 0.3, self.height * 0.45
            size: self.width * 0.9, self.width * 0.9
        Color:
            rgba: 0.0, 0.7, 0.6, 0.05
        Ellipse:
            pos: self.width * 0.4, -self.height * 0.15
            size: self.width * 0.8, self.width * 0.8

    BoxLayout:
        orientation: "vertical"
        pos: root.pos
        size: root.size
        padding: [dp(20), dp(48), dp(20), dp(36)]
        spacing: 0

        # ── HEADER ──────────────────────────────────────────────────────
        BoxLayout:
            orientation: "vertical"
            size_hint_y: None
            height: dp(90)
            spacing: dp(2)

            BoxLayout:
                orientation: "horizontal"
                size_hint_y: None
                height: dp(56)
                spacing: dp(10)

                Widget:
                    size_hint: None, None
                    size: dp(4), dp(36)
                    pos_hint: {"center_y": 0.5}
                    canvas:
                        Color:
                            rgba: 0.0, 0.85, 1.0, 1
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [dp(2)]

                Label:
                    text: "MPro"
                    font_size: sp(36)
                    bold: True
                    color: 0.96, 0.97, 1.0, 1
                    size_hint_x: None
                    width: self.texture_size[0]
                    halign: "left"
                    valign: "middle"

                Widget:

                BoxLayout:
                    size_hint: None, None
                    size: dp(90), dp(26)
                    pos_hint: {"center_y": 0.5}
                    padding: [dp(8), dp(4)]
                    spacing: dp(6)
                    canvas.before:
                        Color:
                            rgba: (0.0, 0.85, 1.0, 0.12) if root.connected else (0.3, 0.3, 0.35, 0.12)
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [dp(13)]
                        Color:
                            rgba: (0.0, 0.85, 1.0, 0.5) if root.connected else (0.4, 0.4, 0.45, 0.5)
                        Line:
                            rounded_rectangle: [self.x, self.y, self.width, self.height, dp(13)]
                            width: dp(0.8)
                    Widget:
                        size_hint: None, None
                        size: dp(8), dp(8)
                        pos_hint: {"center_y": 0.5}
                        canvas:
                            Color:
                                rgba: (0.0, 1.0, 0.6, 1) if root.connected else (0.45, 0.45, 0.5, 1)
                            Ellipse:
                                pos: self.pos
                                size: self.size
                    Label:
                        text: "LIVE" if root.connected else "OFF"
                        font_size: sp(11)
                        color: (0.0, 0.9, 0.7, 1) if root.connected else (0.5, 0.5, 0.55, 1)
                        bold: True
                        halign: "left"

            Label:
                text: "Real-time AI Voice Assistant"
                font_size: sp(12)
                color: 0.4, 0.48, 0.58, 1
                halign: "left"
                size_hint_y: None
                height: dp(20)
                text_size: self.width, None

        # Divider
        Widget:
            size_hint_y: None
            height: dp(1)
            canvas:
                Color:
                    rgba: 0.0, 0.85, 1.0, 0.12
                Line:
                    points: [self.x, self.center_y, self.right, self.center_y]
                    width: dp(0.8)

        Widget:
            size_hint_y: None
            height: dp(16)

        # ── STATUS CARD ─────────────────────────────────────────────────
        BoxLayout:
            size_hint_y: None
            height: dp(260)
            canvas.before:
                Color:
                    rgba: 0.06, 0.07, 0.11, 0.85
                RoundedRectangle:
                    pos: self.pos
                    size: self.size
                    radius: [dp(24)]
                Color:
                    rgba: root.status_color[:3] + [0.25]
                Line:
                    rounded_rectangle: [self.x, self.y, self.width, self.height, dp(24)]
                    width: dp(1.0)

            PulseRing:
                active: root.connected
                ring_color: root.status_color
                size_hint: None, None
                size: dp(220), dp(220)
                pos_hint: {"center_x": 0.5, "center_y": 0.5}

            BoxLayout:
                orientation: "vertical"
                padding: [dp(16), dp(20)]
                spacing: dp(8)

                Widget:
                    size_hint_y: 0.6

                Widget:
                    size_hint: None, None
                    size: dp(72), dp(72)
                    pos_hint: {"center_x": 0.5}
                    canvas:
                        Color:
                            rgba: root.status_color[:3] + [0.18]
                        Ellipse:
                            pos: [self.center_x - dp(40), self.center_y - dp(40)]
                            size: [dp(80), dp(80)]
                        Color:
                            rgba: root.status_color[:3] + [0.22]
                        Ellipse:
                            pos: self.pos
                            size: self.size
                        Color:
                            rgba: root.status_color
                        Line:
                            circle: [self.center_x, self.center_y, dp(35)]
                            width: dp(1.6)
                        Color:
                            rgba: root.status_color
                        RoundedRectangle:
                            pos: [self.center_x - dp(7), self.center_y - dp(12)]
                            size: [dp(14), dp(22)]
                            radius: [dp(7)]
                        Line:
                            points: [self.center_x, self.center_y - dp(12), self.center_x, self.center_y - dp(19)]
                            width: dp(2)
                        Line:
                            points: [self.center_x - dp(8), self.center_y - dp(19), self.center_x + dp(8), self.center_y - dp(19)]
                            width: dp(2)

                Widget:
                    size_hint_y: None
                    height: dp(8)

                Label:
                    text: root.status_text
                    font_size: sp(22)
                    bold: True
                    color: root.status_color
                    halign: "center"
                    size_hint_y: None
                    height: dp(32)

                Label:
                    text: root.status_sub
                    font_size: sp(13)
                    color: 0.45, 0.52, 0.62, 1
                    halign: "center"
                    size_hint_y: None
                    height: dp(22)

                WaveformBars:
                    size_hint_y: None
                    height: dp(34)
                    active: root.status_key in ("listening", "speaking", "thinking")
                    bar_color: root.status_color
                    bar_count: 22

                Widget:
                    size_hint_y: 0.4

        Widget:
            size_hint_y: None
            height: dp(18)

        # ── STATS ROW ───────────────────────────────────────────────────
        GridLayout:
            cols: 3
            size_hint_y: None
            height: dp(64)
            spacing: dp(10)

            BoxLayout:
                orientation: "vertical"
                padding: [dp(10), dp(8)]
                canvas.before:
                    Color:
                        rgba: 0.06, 0.07, 0.11, 0.9
                    RoundedRectangle:
                        pos: self.pos
                        size: self.size
                        radius: [dp(14)]
                    Color:
                        rgba: 0.0, 0.85, 1.0, 0.08
                    Line:
                        rounded_rectangle: [self.x, self.y, self.width, self.height, dp(14)]
                        width: dp(0.8)
                Label:
                    text: root.duration_text
                    font_size: sp(16)
                    bold: True
                    color: 0.0, 0.85, 1.0, 1
                    halign: "center"
                Label:
                    text: "Duration"
                    font_size: sp(10)
                    color: 0.4, 0.48, 0.58, 1
                    halign: "center"

            BoxLayout:
                orientation: "vertical"
                padding: [dp(10), dp(8)]
                canvas.before:
                    Color:
                        rgba: 0.06, 0.07, 0.11, 0.9
                    RoundedRectangle:
                        pos: self.pos
                        size: self.size
                        radius: [dp(14)]
                    Color:
                        rgba: 0.0, 0.85, 1.0, 0.08
                    Line:
                        rounded_rectangle: [self.x, self.y, self.width, self.height, dp(14)]
                        width: dp(0.8)
                Label:
                    text: root.exchange_text
                    font_size: sp(16)
                    bold: True
                    color: 0.0, 0.85, 1.0, 1
                    halign: "center"
                Label:
                    text: "Exchanges"
                    font_size: sp(10)
                    color: 0.4, 0.48, 0.58, 1
                    halign: "center"

            BoxLayout:
                orientation: "vertical"
                padding: [dp(10), dp(8)]
                canvas.before:
                    Color:
                        rgba: 0.06, 0.07, 0.11, 0.9
                    RoundedRectangle:
                        pos: self.pos
                        size: self.size
                        radius: [dp(14)]
                    Color:
                        rgba: 0.0, 0.85, 1.0, 0.08
                    Line:
                        rounded_rectangle: [self.x, self.y, self.width, self.height, dp(14)]
                        width: dp(0.8)
                Label:
                    text: "HD"
                    font_size: sp(16)
                    bold: True
                    color: 0.0, 1.0, 0.65, 1
                    halign: "center"
                Label:
                    text: "Quality"
                    font_size: sp(10)
                    color: 0.4, 0.48, 0.58, 1
                    halign: "center"

        Widget:
            size_hint_y: 1

        # ── BOTTOM ACTION AREA ──────────────────────────────────────────
        BoxLayout:
            orientation: "vertical"
            size_hint_y: None
            height: dp(160)
            spacing: dp(12)

            BoxLayout:
                orientation: "horizontal"
                size_hint_y: None
                height: dp(32)
                spacing: dp(8)

                Widget:
                    size_hint_x: 1

                BoxLayout:
                    size_hint: None, None
                    size: dp(80), dp(30)
                    padding: [dp(10), dp(5)]
                    canvas.before:
                        Color:
                            rgba: 0.0, 0.85, 1.0, 0.09
                        RoundedRectangle:
                            pos: self.pos
                  
