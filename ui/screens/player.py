"""Immersive Player screen.

Talks ONLY to PlayerController (frozen) — the screen does not care
whether the backend is VLC, MPV or Mock. Progress, seek, volume,
mute, fullscreen and back are all driven off PlayerController state
through a low-frequency QTimer poll (no duplicated playback state).

Missing-file behavior: if the file no longer exists the screen shows
the unavailable state; it never pretends playback succeeded.
"""
from __future__ import annotations

import os

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QSizePolicy,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ui.app.view_model import UiContext
from ui.models import EntityRef
from ui.themes.tokens import Spacing, Typography


class PlayerScreen(QWidget):
    """Full-window playback surface."""

    def __init__(self, context: UiContext, backend_name: str = "vlc") -> None:
        super().__init__()
        self.context = context
        self._backend_name = backend_name
        self._controller = None
        self._params: dict = {}
        self._ref: EntityRef | None = None
        self._seeking = False
        self._show_controls = True
        self._poll = QTimer(self)
        self._poll.setInterval(500)
        self._poll.timeout.connect(self._poll_state)
        self._build()

    # ------------------------------------------------------------------ #
    # Shell plumbing                                                      #
    # ------------------------------------------------------------------ #

    def on_activated(self) -> None:
        route = self.context.navigation.current_route
        if route:
            self._params = dict(route.params)
        self._setup()

    def shutdown(self) -> None:
        self._stop_polling()
        controller = self._controller
        if controller is not None:
            try:
                controller.save_position()
            except Exception:
                pass
            try:
                controller.release()
            except Exception:
                pass
            self._controller = None

    def handle_escape(self) -> bool:
        # Player owns Escape while controls are up (acts as back)
        if self._controller is not None:
            self.context.navigation.back()
            return True
        return False

    def refresh_theme(self) -> None:
        self.update()

    # ------------------------------------------------------------------ #
    # Setup                                                               #
    # ------------------------------------------------------------------ #

    def _setup(self) -> None:
        kind = str(self._params.get("kind", "movie"))
        entity_id = int(self._params.get("entity_id", 0))
        title = str(self._params.get("title", ""))
        file_path = self._params.get("file_path")

        self._ref = EntityRef(kind=kind, entity_id=entity_id, title=title)

        if not file_path or not os.path.isfile(str(file_path)):
            self._show_unavailable("The media file is not available.")
            return

        self._show_playing(str(file_path))

    def _controller_for(self, file_path: str):
        from app.bootstrap import create_player_controller

        return create_player_controller(
            backend_name=self._backend_name,
            event_bus=self.context.services.event_bus,
        )

    # ------------------------------------------------------------------ #
    # Views                                                               #
    # ------------------------------------------------------------------ #

    def _build(self) -> None:
        self.setObjectName("AppBackground")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._views = _ViewStack(self)
        layout.addWidget(self._views, 1)

        self._unavailable_widget = self._make_unavailable_widget()
        self._missing_widget = self._make_missing_widget()
        self._show_area = _ShowArea()

        self._views.addWidget(self._unavailable_widget)
        self._views.addWidget(self._missing_widget)
        self._views.addWidget(self._show_area)
        self._views.setCurrentWidget(self._unavailable_widget)

        self._wire_controls()

    # --- placeholder builders (real state widgets) --------------------- #

    def _make_unavailable_widget(self) -> QWidget:
        box = QWidget()
        lay = _centered(box)
        icon = QLabel("")
        icon.setStyleSheet(
            "font-size: 48px; color: #6F7480; background-color: #0B0D12;"
        )
        title = QLabel("Player")
        title.setStyleSheet(
            "font-size: 28px; font-weight: 700; color: #F5F5F7; "
            "background-color: #0B0D12;"
        )
        sub = QLabel("Open a title from your library to start playback.")
        sub.setStyleSheet(
            "font-size: 14px; color: #A7ABB5; background-color: #0B0D12;"
        )
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setWordWrap(True)
        lay.addWidget(icon)
        lay.addWidget(title)
        lay.addWidget(sub)
        return box

    def _make_missing_widget(self) -> QWidget:
        box = QWidget()
        box.setAutoFillBackground(True)
        lay = _centered(box)
        icon = QLabel("?")
        icon.setStyleSheet(
            "font-size: 56px; color: #6F7480;"
            "background-color: #0B0D12; border-radius: 28px; padding: 12px;"
        )
        lay.addWidget(icon)
        title = QLabel("Media Not Available")
        title.setStyleSheet(
            "font-size: 24px; font-weight: 700; color: #F5F5F7; "
            "background-color: #0B0D12;"
        )
        lay.addWidget(title)
        self._missing_msg = QLabel("")
        self._missing_msg.setWordWrap(True)
        self._missing_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._missing_msg.setStyleSheet(
            "font-size: 14px; color: #A7ABB5; background-color: #0B0D12;"
        )
        lay.addWidget(self._missing_msg)
        back = QPushButton("Back")
        back.setObjectName("GhostButton")
        back.setCursor(Qt.CursorShape.PointingHandCursor)
        back.clicked.connect(lambda: self.context.navigation.back())
        lay.addWidget(back)
        return box

    # --- show area (video surface + controls) --------------------------- #

    def _show_playing(self, file_path: str) -> None:
        self._views.setCurrentWidget(self._show_area)
        self._show_area.set_entity_title(self._ref.title if self._ref else "Playing")
        host = self._video_host()
        self._show_area.set_video_host(host)

        try:
            controller = self._controller_for(file_path)
            controller.open(
                self._ref.kind if self._ref else "movie",
                self._ref.entity_id if self._ref else 0,
                file_path,
                backend_used=self._backend_name,
            )
            self._controller = controller
            if self._ref is not None:
                self._attach_video()
        except Exception as exc:  # noqa: BLE001 — surface friendly state
            self._show_unavailable(str(exc.__class__.__name__))
            return

        self._show_controls = True
        self._show_area.show_controls()
        self._poll.start()

    def _video_host(self) -> QWidget:
        """A host widget that can be embedded by the backend.

        VLC uses set_video_window_id(winId) and MPV can embed via
        the host. The backend is agnostic here; we expose the host and
        let PlayerController attach.
        """
        host = QWidget()
        host.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._video_host_widget = host
        return host

    def _attach_video(self) -> None:
        controller = self._controller
        host = getattr(self, "_video_host_widget", None)
        if controller is None or host is None:
            return
        try:
            controller.set_video_widget(host)
        except Exception:
            # Backends without embedding just no-op; the player still
            # drives audio + state. Video may open in its own window.
            pass

    def _show_unavailable(self, message: str) -> None:
        self._views.setCurrentWidget(self._missing_widget)
        self._missing_msg.setText(message)

    # ------------------------------------------------------------------ #
    # Controls wiring (on _ShowArea)                                       #
    # ------------------------------------------------------------------ #

    def _wire_controls(self) -> None:
        controls = self._show_area.controls
        controls.play_pause.clicked.connect(self._play_pause)
        controls.seek_slider.sliderMoved.connect(self._seeking_changed)
        controls.seek_slider.sliderReleased.connect(self._seek_commit)
        controls.volume_slider.valueChanged.connect(self._volume_changed)
        controls.mute.clicked.connect(self._toggle_mute)
        controls.back.clicked.connect(lambda: self.context.navigation.back())
        controls.fullscreen.clicked.connect(self._toggle_fullscreen)

    def _poll_state(self) -> None:
        c = self._controller
        if c is None:
            self._stop_polling()
            return
        try:
            pos = c.get_position()
            dur = c.get_duration()
            paused = c.is_paused()
        except Exception:
            return
        if not self._seeking:
            self._show_area.controls.set_progress(pos, dur)
        self._show_area.controls.set_play_pause_icon("▶" if paused else "⏸")
        if not c.is_open():
            self._stop_polling()

    def _play_pause(self) -> None:
        if self._controller is None:
            return
        try:
            self._controller.toggle_pause()
        except Exception:
            pass

    def _seeking_changed(self) -> None:
        self._seeking = True
        pos = (self._show_area.controls.seek_slider.value() / 1000.0)
        dur = self._show_area.controls.duration
        value = (pos / 1000.0) * dur if dur > 0 else 0
        self._show_area.controls.set_position_preview(value)

    def _seek_commit(self) -> None:
        self._seeking = False
        c = self._controller
        if c is None:
            return
        dur = self._show_area.controls.duration
        value = (self._show_area.controls.seek_slider.value() / 1000.0) * dur
        try:
            c.seek(max(0.0, value))
        except Exception:
            pass

    def _volume_changed(self, value: int) -> None:
        c = self._controller
        if c is None:
            return
        try:
            c.set_volume(value / 100.0)
        except Exception:
            pass

    def _toggle_mute(self) -> None:
        c = self._controller
        if c is None:
            return
        try:
            if c.is_muted():
                c.unmute()
            else:
                c.mute()
        except Exception:
            pass
        self._sync_mute()

    def _toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()
        self._show_controls = True
        self._show_area.show_controls()
        self.update()

    def _sync_mute(self) -> None:
        c = self._controller
        if c is None:
            return
        try:
            self._show_area.controls.set_mute_icon(
                "🔇" if c.is_muted() else "🔊"
            )
        except Exception:
            pass

    def _stop_polling(self) -> None:
        self._poll.stop()

    # ------------------------------------------------------------------ #


class _ViewStack(QWidget):
    """Simple QStackedWidget wrapper for the player views."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._stack = QStackedWidget(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._stack)

    def addWidget(self, widget) -> None:
        self._stack.addWidget(widget)

    def setCurrentWidget(self, widget) -> None:
        self._stack.setCurrentWidget(widget)


class _ControlsBar(QWidget):
    """Bottom control bar: back, play/pause, seek, time, volume, FS."""

    def __init__(self) -> None:
        super().__init__(None)
        self.setObjectName("PlayerControls")
        self._duration = 0.0
        self._position = 0.0
        self._paused = True
        self._muted = False
        self._build()

    def _build(self) -> None:
        lay = QHBoxLayout(self)
        lay.setContentsMargins(Spacing.L, Spacing.S, Spacing.L, Spacing.S)
        lay.setSpacing(Spacing.M)

        self.back = QPushButton("←")
        self.back.setObjectName("IconButton")
        self.back.setCursor(Qt.CursorShape.PointingHandCursor)

        self.play_pause = QPushButton("▶")
        self.play_pause.setObjectName("PrimaryButton")
        self.play_pause.setFixedWidth(44)
        self.play_pause.setFixedHeight(36)
        self.play_pause.setCursor(Qt.CursorShape.PointingHandCursor)

        lay.addWidget(self.back)
        lay.addWidget(self.play_pause)

        self.seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setRange(0, 1000)
        self.seek_slider.setFixedWidth(420)
        lay.addWidget(self.seek_slider, 1)

        self.time_label = QLabel("0:00 / 0:00")
        self.time_label.setObjectName("ProgressLabel")
        self.time_label.setFixedWidth(120)
        lay.addWidget(self.time_label)

        self.mute = QPushButton("🔊")
        self.mute.setObjectName("IconButton")
        self.mute.setCursor(Qt.CursorShape.PointingHandCursor)
        lay.addWidget(self.mute)

        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(100)
        self.volume_slider.setObjectName("VolumeSlider")
        self.volume_slider.setFixedWidth(100)
        lay.addWidget(self.volume_slider)

        self.fullscreen = QPushButton("⛶")
        self.fullscreen.setObjectName("IconButton")
        self.fullscreen.setCursor(Qt.CursorShape.PointingHandCursor)
        lay.addWidget(self.fullscreen)

    # --- state setters --------------------------------------------------- #

    @property
    def duration(self) -> float:
        return self._duration

    @property
    def position(self) -> float:
        return self._position

    def set_progress(self, position: float, duration: float) -> None:
        self._position = position
        self._duration = duration
        self.seek_slider.setRange(0, 1000)
        frac = 0
        if duration > 0:
            frac = max(0.0, min(1.0, position / duration))
        self.seek_slider.setValue(int(frac * 1000))
        from ui.utils.formatting import format_seconds

        self.time_label.setText(
            f"{format_seconds(position)} / {format_seconds(duration)}"
        )

    def set_position_preview(self, seconds: float) -> None:
        from ui.utils.formatting import format_seconds

        dur = self._duration
        self.time_label.setText(
            f"{format_seconds(seconds)} / {format_seconds(dur)}"
        )

    def set_play_pause_icon(self, icon: str) -> None:
        self.play_pause.setText(icon)

    def set_mute_icon(self, icon: str) -> None:
        self.mute.setText(icon)

    def set_muted(self, muted: bool) -> None:
        self._muted = muted
        self.set_mute_icon("🔇" if muted else "🔊")


class _ShowArea(QWidget):
    """Video host + floating title + control bar."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("AppBackground")
        self._controls_visible = True
        self._title = QLabel("")
        self._title.setStyleSheet(
            "font-size: 20px; font-weight: 700; color: #F5F5F7; "
            "background: rgba(8,9,12,0.8); padding: 10px 18px; "
            "border-radius: 8px;"
        )
        self._title.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._controls = _ControlsBar()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._title_wrap = QWidget()
        title_lay = QHBoxLayout(self._title_wrap)
        title_lay.setContentsMargins(Spacing.L, Spacing.M, 0, 0)
        title_lay.addWidget(self._title)
        title_lay.addStretch(1)
        self._content_layout.addWidget(self._title_wrap)
        self._video_host_wrap = QWidget()
        self._video_host_wrap.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._video_host_lay = QVBoxLayout(self._video_host_wrap)
        self._video_host_lay.setContentsMargins(0, 0, 0, 0)
        self._content_layout.addWidget(self._video_host_wrap, 1)
        self._content_layout.addWidget(self._controls)
        outer.addWidget(self._content, 1)

    @property
    def controls(self) -> _ControlsBar:
        return self._controls

    def set_entity_title(self, title: str) -> None:
        self._title.setText(title)

    def set_video_host(self, host: QWidget) -> None:
        # Remove any previous host
        while self._video_host_lay.count():
            item = self._video_host_lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
        host.setParent(self._video_host_wrap)
        self._video_host_lay.addWidget(host, 1)
        self._video_host = host

    def show_controls(self) -> None:
        self._controls.show()
        self._title_wrap.show()
        self._controls_visible = True

    def hide_controls(self) -> None:
        self._controls.hide()
        self._title_wrap.hide()
        self._controls_visible = False


def _centered(widget: QWidget) -> QVBoxLayout:
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.setSpacing(Spacing.M)
    return layout
