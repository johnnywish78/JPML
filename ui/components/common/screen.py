"""Shared screen base.

Every screen has four mutually exclusive views on a QStackedWidget:
loading (skeleton), empty, error, and a *content container* that the
screen fills in itself. This keeps INITIAL/LOADING/READY/EMPTY/ERROR
consistent across the whole app without duplicated layout code.

Subclass contract:
    load()        -> pull data and then show_content/show_empty/show_error
    _on_data_ready(payload) -> render widgets into the content container
"""
from __future__ import annotations

import logging
from typing import Callable

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QLabel,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ui.app.view_model import UiContext
from ui.components.common.empty_state import EmptyState, ErrorState
from ui.components.common.skeleton import RowSkeleton
from ui.themes.tokens import Spacing, Typography

log = logging.getLogger("jpml.ui.screen")


class _DataWorker(QThread):
    """One-shot background load; results hop back to the UI thread.

    IMPORTANT: the frozen backend opens SQLite connections that are
    bound to the thread that created them (backend is immutable).
    Therefore the worker builds a *fresh* service composition via the
    frozen build_services() factory and runs the gather function with
    it. Mutations always stay on the UI thread.
    """

    done = pyqtSignal(object)
    failed = pyqtSignal(object)

    def __init__(self, fn: Callable[[], object], parent=None) -> None:
        super().__init__(parent)
        self._fn = fn

    def run(self) -> None:  # noqa: D102
        try:
            result = self._fn()
            self.done.emit(result)
        except Exception as exc:  # noqa: BLE001 — surfaced as ERROR state
            log.warning("screen data load failed", exc_info=True)
            try:
                self.failed.emit(exc)
            except RuntimeError:
                pass  # C++ object already destroyed (app shutting down)


class BaseScreen(QWidget):
    def __init__(self, context: UiContext, *, scrollable: bool = True) -> None:
        self._scrollable = scrollable  # must exist before super().__init__()
        super().__init__()
        self.context = context
        self._worker: _DataWorker | None = None
        self._loaded = False
        self._watching_scan = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self._stack = QStackedWidget()
        outer.addWidget(self._stack)

        self._content_widget = self._build_content()
        self._skeleton_widget = self._build_skeleton()
        self._empty_widget = self._build_empty()
        self._error_widget = self._build_error()
        self._scanning_widget = self._build_scanning()
        self._stack.addWidget(self._content_widget)
        self._stack.addWidget(self._skeleton_widget)
        self._stack.addWidget(self._empty_widget)
        self._stack.addWidget(self._error_widget)
        self._stack.addWidget(self._scanning_widget)
        self._stack.setCurrentWidget(self._skeleton_widget)

        # content widget reference for rendering
        self.container = self._content_widget

    # -- state switching -----------------------------------------------------

    def show_loading(self) -> None:
        self._stack.setCurrentWidget(self._skeleton_widget)

    def show_content(self) -> None:
        self._stack.setCurrentWidget(self._content_widget)

    def show_empty(self) -> None:
        self._stack.setCurrentWidget(self._empty_widget)

    def show_error(self) -> None:
        self._stack.setCurrentWidget(self._error_widget)

    def show_scanning(self, message: str = "") -> None:
        if message:
            self._scanning_sublabel.setText(message)
        self._stack.setCurrentWidget(self._scanning_widget)

    def state(self) -> str:
        current = self._stack.currentWidget()
        if current is self._content_widget:
            return "ready"
        if current is self._empty_widget:
            return "empty"
        if current is self._error_widget:
            return "error"
        if current is self._scanning_widget:
            return "scanning"
        return "loading"

    # -- scan awareness ----------------------------------------------------------

    def _scan_in_progress(self) -> bool:
        from PyQt6.QtWidgets import QApplication

        from ui.app import library_flow

        return library_flow.scan_in_progress(QApplication.instance())

    def _begin_watch_scan(self) -> None:
        if self._watching_scan:
            return
        from PyQt6.QtWidgets import QApplication

        from ui.app import library_flow

        worker = library_flow.current_scan_worker(QApplication.instance())
        if worker is None:
            return
        self._scan_worker_ref = worker
        worker.done.connect(self._on_scan_finished)
        worker.failed.connect(lambda _exc: self._on_scan_finished())
        self._watching_scan = True

    def _stop_watching_scan(self) -> None:
        if not self._watching_scan:
            return
        worker = getattr(self, "_scan_worker_ref", None)
        if worker is not None:
            try:
                worker.done.disconnect(self._on_scan_finished)
            except (TypeError, RuntimeError):
                pass
        self._scan_worker_ref = None
        self._watching_scan = False

    def _on_scan_finished(self, *_args) -> None:
        self._stop_watching_scan()
        # Only refresh if this screen is the visible one; otherwise the
        # next activation will reload it.
        if self._stack.currentWidget() is self._scanning_widget:
            self.load()

    # -- content ---------------------------------------------------------------

    def _build_content(self) -> QWidget:
        container = QWidget()
        if self._scrollable:
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setStyleSheet("QScrollArea { border: none; }")
            scroll.viewport().setAutoFillBackground(False)
            inner = QWidget()
            inner_layout = QVBoxLayout(inner)
            inner_layout.setContentsMargins(0, 0, 0, 0)
            scroll.setWidget(inner)
            container_layout.addWidget(scroll)
            self._inner = inner
            self._inner_layout = inner_layout
        else:
            self._inner = container
            self._inner_layout = QVBoxLayout(container)
            self._inner_layout.setContentsMargins(0, 0, 0, 0)
        return container

    def clear_content(self) -> None:
        """Remove all widgets previously rendered into the content area."""
        layout = self._inner_layout
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def add_to_content(self, widget, stretch: int = 0, alignment=None):
        if alignment is None:
            self._inner_layout.addWidget(widget, stretch)
        else:
            self._inner_layout.addWidget(widget, stretch, alignment)

    # -- lifecycle ---------------------------------------------------------------

    def on_activated(self) -> None:
        if self._scan_in_progress():
            self._begin_watch_scan()
            self.show_scanning("Scanning your library…")
            return
        self._stop_watching_scan()
        self.load()

    def load(self) -> None:
        raise NotImplementedError

    def start_async_load(self, gather: Callable[["Services"], object]) -> None:
        """Run *gather(services)* off the UI thread.

        The frozen backend opens SQLite connections that are bound to the
        thread that created them, so a fresh service composition is built
        on the worker thread, the read is executed, and every connection
        is closed before the thread returns. The payload (plain Python
        data) is then delivered to ``handle_data(payload)`` on the UI
        thread on success; on failure the screen shows the ERROR state.
        """
        self.show_loading()
        if self._worker is not None and self._worker.isRunning():
            self._worker.wait(500)

        def _fetch():
            from ui.app.composition import build_services, close_services

            services = build_services()
            try:
                return gather(services)
            finally:
                close_services(services)

        worker = _DataWorker(_fetch, parent=self)
        self._worker = worker
        worker.done.connect(self._on_data_ready)
        worker.failed.connect(self._on_data_failed)
        worker.start()

    def _on_data_ready(self, payload) -> None:
        self._worker = None
        self.handle_data(payload)

    def _on_data_failed(self, exc) -> None:
        self._worker = None
        self.show_error()

    def handle_data(self, payload) -> None:
        raise NotImplementedError

    # -- empty / error ---------------------------------------------------------

    def _build_empty(self) -> QWidget:
        widget: EmptyState = EmptyState(
            self.empty_title(),
            self.empty_subtitle(),
            self.empty_action(),
            secondary_text=self.empty_secondary_action(),
        )
        action = getattr(widget, "action_button", None)
        if action is not None:
            action.clicked.connect(self._empty_action)
        secondary = getattr(widget, "action_button_secondary", None)
        if secondary is not None:
            secondary.clicked.connect(self._empty_secondary_action)
        return widget

    def _empty_action(self) -> None:
        hook = getattr(self, "empty_action_clicked", None)
        if callable(hook):
            hook()
        else:
            self.load()

    def _empty_secondary_action(self) -> None:
        hook = getattr(self, "empty_secondary_action_clicked", None)
        if callable(hook):
            hook()
        else:
            self.load()

    def _build_error(self) -> QWidget:
        widget = ErrorState()
        widget.retry_button.clicked.connect(self.load)
        return widget

    def empty_title(self) -> str:
        return "Nothing here yet"

    def empty_subtitle(self) -> str:
        return ""

    def empty_action(self) -> str | None:
        return None

    def empty_secondary_action(self) -> str | None:
        return None

    def _build_scanning(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(
            Spacing.XXL3, Spacing.XXL4 * 2, Spacing.XXL3, Spacing.XXL4
        )
        layout.setSpacing(Spacing.M)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon = QLabel("⟳")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet("font-size: 40px; color: #6F7480; background: transparent;")
        title = QLabel("Scanning your library…")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            f"font-size: {Typography.SECTION_PX}px; font-weight: 600; "
            "background: transparent;"
        )
        self._scanning_sublabel = QLabel(
            "Looking for movie, TV and music files."
        )
        self._scanning_sublabel.setObjectName("SecondaryLabel")
        self._scanning_sublabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._scanning_sublabel.setWordWrap(True)
        self._scanning_sublabel.setStyleSheet("background: transparent;")

        layout.addStretch(1)
        layout.addWidget(icon)
        layout.addWidget(title)
        layout.addWidget(self._scanning_sublabel)
        layout.addStretch(1)
        return widget

    # -- skeleton ------------------------------------------------------------------

    def _build_skeleton(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        for _ in range(3):
            layout.addWidget(RowSkeleton(card_width=160, count=6))
            layout.addSpacing(Spacing.M)
        layout.addStretch(1)
        return widget

    # -- theme / keyboard -----------------------------------------------------------

    def refresh_theme(self) -> None:
        pass

    def handle_escape(self) -> bool:
        return False

    def shutdown(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.wait(500)
