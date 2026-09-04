"""Library management — locations, add-and-scan flow, scan status.

The screen is a plain management panel (always READY-style): it lists
the frozen backend's library locations, offers the Add Library Location
flow (QFileDialog → confirm path → add + scan), and mirrors the real
scan state: SCANNING with live phase/count updates, a completion
summary, or an actionable error with retry.
"""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ui.app import library_flow
from ui.app.view_model import UiContext
from ui.components.common.button import (
    GhostButton,
    IconButton,
    PrimaryButton,
)
from ui.components.common.page_header import PageHeader
from ui.themes.tokens import Radius, Spacing, Typography


def _section_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("SectionLabel")
    return label


class _StatusCard(QFrame):
    """Centered state card: icon, title, message, optional extra lines."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("CardFrame")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            Spacing.XXL2, Spacing.XXL3, Spacing.XXL2, Spacing.XXL2
        )
        layout.setSpacing(Spacing.S)
        layout.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)

        self._icon = QLabel("")
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon.setStyleSheet("font-size: 40px; background: transparent;")
        self._title = QLabel("")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title.setStyleSheet(
            f"font-size: {Typography.SECTION_PX}px; font-weight: 600; "
            "background: transparent;"
        )
        self._message = QLabel("")
        self._message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._message.setObjectName("SecondaryLabel")
        self._message.setWordWrap(True)
        self._message.setStyleSheet("background: transparent;")
        self._lines: list[tuple[QLabel, str]] = []
        for _ in range(4):
            line = QLabel("")
            line.setAlignment(Qt.AlignmentFlag.AlignCenter)
            line.setObjectName("MutedLabel")
            line.setStyleSheet("background: transparent;")
            self._lines.append((line, ""))
            layout.addWidget(line)
        self._buttons = QHBoxLayout()
        self._buttons.setSpacing(Spacing.S)
        self._buttons.addStretch(1)
        self._buttons.addStretch(1)

        layout.addWidget(self._icon)
        layout.addWidget(self._title)
        layout.addWidget(self._message)
        layout.addSpacing(Spacing.M)
        layout.addLayout(self._buttons)

    def set_status(self, icon: str, title: str, message: str) -> None:
        self._icon.setText(icon)
        self._title.setText(title)
        self._message.setText(message)

    def set_lines(self, lines: list[str]) -> None:
        for index, (label, _) in enumerate(self._lines):
            if index < len(lines):
                label.setText(lines[index])
            else:
                label.setText("")

    def clear_lines(self) -> None:
        self.set_lines([])

    def clear_buttons(self) -> None:
        while self._buttons.count():
            item = self._buttons.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)

    def add_button(self, button) -> None:
        self._buttons.insertWidget(self._buttons.count() - 1, button)


class LibraryScreen(QWidget):
    def __init__(self, context: UiContext) -> None:
        super().__init__()
        self.context = context
        self._pending_path: str | None = None
        self._worker = None
        self._building = True
        self._build()
        self._building = False

    # ------------------------------------------------------------------ #
    # Shell plumbing                                                      #
    # ------------------------------------------------------------------ #

    def on_activated(self) -> None:
        route = self.context.navigation.current_route
        pending = route.params.get("pending_path") if route else None
        if pending:
            self._show_pending(str(pending))
            return
        self._refresh_locations()
        worker = library_flow.current_scan_worker(self._app())
        if worker is not None:
            if self._worker is not worker:
                worker.progress.connect(self._on_progress)
                worker.done.connect(self._on_scan_done)
                worker.failed.connect(self._on_scan_failed)
                self._worker = worker
            self._show_scanning(worker)

    def shutdown(self) -> None:
        worker = self._worker
        if worker is not None and worker.isRunning():
            worker.wait(10_000)

    def handle_escape(self) -> bool:
        if self._stack.currentWidget() is self._pending_widget:
            self._pending_path = None
            self._refresh_locations()
            self._stack.setCurrentWidget(self._locations_widget)
            return True
        return False

    def refresh_theme(self) -> None:
        self.update()

    # ------------------------------------------------------------------ #
    # Construction                                                        #
    # ------------------------------------------------------------------ #

    def _app(self):
        from PyQt6.QtWidgets import QApplication

        return QApplication.instance()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(Spacing.L)

        header = PageHeader("Library", subtitle="Locations and scans")
        outer.addWidget(header)

        self._stack = QStackedWidget()
        outer.addWidget(self._stack, 1)

        self._locations_widget = self._build_locations_view()
        self._pending_widget = self._build_pending_view()
        self._status_widget = _StatusCard()
        self._status_card = self._status_widget

        self._stack.addWidget(self._locations_widget)
        self._stack.addWidget(self._pending_widget)
        self._stack.addWidget(self._status_widget)
        self._refresh_locations()

    def _build_locations_view(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, Spacing.S)
        layout.setSpacing(Spacing.S)
        layout.addWidget(_section_label("LIBRARY LOCATIONS"))

        self._list_card = QFrame()
        self._list_card.setObjectName("CardFrame")
        self._list_layout = QVBoxLayout(self._list_card)
        self._list_layout.setContentsMargins(Spacing.M, Spacing.M, Spacing.M, Spacing.M)
        self._list_layout.setSpacing(Spacing.S)
        layout.addWidget(self._list_card)

        self._hint = QLabel(
            "No library locations yet. Add a folder to get started."
        )
        self._hint.setObjectName("MutedLabel")
        self._hint.setStyleSheet("background: transparent;")
        layout.addWidget(self._hint)

        actions = QHBoxLayout()
        actions.setSpacing(Spacing.S)
        self._add_button = PrimaryButton("+ Add Library Location")
        self._rescan_button = GhostButton("Rescan Library")
        self._rescan_button.setEnabled(False)
        self._add_button.clicked.connect(self._on_add_location)
        self._rescan_button.clicked.connect(self._on_rescan)
        actions.addWidget(self._add_button)
        actions.addWidget(self._rescan_button)
        actions.addStretch(1)
        layout.addLayout(actions)
        layout.addStretch(1)
        return page

    def _build_pending_view(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, Spacing.S)
        layout.setSpacing(Spacing.S)
        layout.addWidget(_section_label("ADD LIBRARY LOCATION"))

        self._pending_card = QFrame()
        self._pending_card.setObjectName("CardFrame")
        card_layout = QVBoxLayout(self._pending_card)
        card_layout.setContentsMargins(Spacing.L, Spacing.L, Spacing.L, Spacing.L)
        card_layout.setSpacing(Spacing.S)

        title = QLabel("Add this folder as a library location?")
        title.setStyleSheet("font-weight: 600; background: transparent;")
        self._pending_path_label = QLabel("")
        self._pending_path_label.setObjectName("SecondaryLabel")
        self._pending_path_label.setWordWrap(True)
        self._pending_path_label.setStyleSheet("background: transparent;")
        note = QLabel(
            "The folder will be scanned for movies, TV shows and music. "
            "You can remove the location later."
        )
        note.setObjectName("MutedLabel")
        note.setWordWrap(True)
        note.setStyleSheet("background: transparent;")
        card_layout.addWidget(title)
        card_layout.addWidget(self._pending_path_label)
        card_layout.addWidget(note)
        layout.addWidget(self._pending_card)

        actions = QHBoxLayout()
        actions.setSpacing(Spacing.S)
        confirm = PrimaryButton("Add & Scan")
        cancel = GhostButton("Cancel")
        confirm.clicked.connect(self._on_confirm_add)
        cancel.clicked.connect(self._on_cancel_pending)
        actions.addWidget(confirm)
        actions.addWidget(cancel)
        actions.addStretch(1)
        layout.addLayout(actions)
        layout.addStretch(1)
        return page

    # ------------------------------------------------------------------ #
    # Locations list                                                      #
    # ------------------------------------------------------------------ #

    def _refresh_locations(self) -> None:
        from app.library.library_repository import LibraryRepository

        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)

        locations: list[dict] = []
        try:
            # use the UI composition's repository for reads
            repo = LibraryRepository(self.context.services.library_repository._conn)  # noqa: SLF001
            locations = repo.list_locations()
        except Exception:  # noqa: BLE001 — surface empty state, never crash
            locations = []

        for row in locations:
            self._list_layout.addWidget(self._location_row(row))
        self._hint.setText(
            "No library locations yet. Add a folder to get started."
            if not locations
            else ""
        )
        self._rescan_button.setEnabled(bool(locations) and self._worker is None)

    def _location_row(self, row: dict) -> QFrame:
        frame = QFrame()
        frame.setObjectName("ElevatedFrame")
        frame.setFixedHeight(52)
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(Spacing.M, 0, Spacing.S, 0)
        layout.setSpacing(Spacing.S)

        text = QVBoxLayout()
        text.setSpacing(2)
        path_label = QLabel(str(row.get("path", "")))
        path_label.setStyleSheet(
            "font-weight: 600; background: transparent;"
        )
        label = row.get("label")
        sub = QLabel(str(label) if label else "media library")
        sub.setObjectName("MutedLabel")
        sub.setStyleSheet("background: transparent;")
        text.addWidget(path_label)
        text.addWidget(sub)
        layout.addLayout(text, 1)

        remove = IconButton("✕", f"Remove location {row.get('path', '')}")
        remove.clicked.connect(lambda _=False, rid=row.get("id"): self._on_remove(rid))
        layout.addWidget(remove)
        return frame

    def _on_remove(self, location_id) -> None:
        if location_id is None:
            return
        try:
            repo_conn = self.context.services.library_repository._conn  # noqa: SLF001
            from app.library.library_repository import LibraryRepository

            removed = LibraryRepository(repo_conn).remove_location(location_id)
        except Exception as exc:  # noqa: BLE001
            self._toast(f"Couldn't remove location: {exc.__class__.__name__}")
            return
        if removed:
            self._toast("Location removed")
        self._refresh_locations()

    # ------------------------------------------------------------------ #
    # Add-location flow                                                   #
    # ------------------------------------------------------------------ #

    def pick_directory(self, title: str = "Choose a media folder") -> str | None:
        """Real directory picker (seam for headless tests)."""
        start = str(Path.home()) if (Path.home() or None) else ""
        path = QFileDialog.getExistingDirectory(self, title, start)
        return str(path) if path else None

    def _on_add_location(self) -> None:
        if library_flow.scan_in_progress(self._app()):
            self._toast("A scan is already running")
            return
        path = self.pick_directory()
        if not path:
            return
        self._show_pending(path)

    def _show_pending(self, path: str) -> None:
        self._pending_path = str(path)
        self._pending_path_label.setText(self._pending_path)
        self._stack.setCurrentWidget(self._pending_widget)

    def _on_cancel_pending(self) -> None:
        self._pending_path = None
        if self.context.navigation.can_go_back and (
            self.context.navigation.current_route is None
            or self.context.navigation.current_route.screen != "home"
        ):
            self.context.navigation.back()
        self._refresh_locations()
        self._stack.setCurrentWidget(self._locations_widget)

    def _on_confirm_add(self) -> None:
        path = self._pending_path
        self._pending_path = None
        if not path:
            return
        self._start_scan(add_path=path)

    def _on_rescan(self) -> None:
        self._start_scan(add_path=None)

    # ------------------------------------------------------------------ #
    # Scan                                                                #
    # ------------------------------------------------------------------ #

    def _start_scan(self, *, add_path: str | None) -> None:
        app = self._app()
        if library_flow.scan_in_progress(app):
            self._toast("A scan is already running")
            return
        worker = library_flow.LibrarySyncWorker(
            add_path=add_path, parent=self
        )
        worker.progress.connect(self._on_progress)
        worker.done.connect(self._on_scan_done)
        worker.failed.connect(self._on_scan_failed)
        self._worker = worker
        library_flow.register_scan_worker(app, worker)
        self._show_scanning(worker)
        worker.start()

    def _show_scanning(self, worker) -> None:
        self._add_button.setEnabled(False)
        self._rescan_button.setEnabled(False)
        self._status_card.set_status(
            "⟳", "Scanning your library", "Looking for movie, TV and music files…"
        )
        self._status_card.clear_lines()
        self._status_card.clear_buttons()
        self._stack.setCurrentWidget(self._status_widget)

    def _on_progress(self, phase: str, message: str) -> None:
        self._status_card.set_status(
            "⟳", "Scanning your library", message
        )

    def _on_scan_done(self, summary) -> None:
        self._finish_worker()
        s = summary if isinstance(summary, dict) else {}
        lines = [
            f"{s.get('media_files_found', 0)} media file(s) found",
            f"{s.get('entities_created', 0)} new title(s), show(s) or artist(s) added",
        ]
        errors = s.get("errors") or []
        if errors:
            lines.append(f"{len(errors)} warning(s) — see library log")
        self._status_card.set_status(
            "✓", "Scan complete", "Your library has been updated."
        )
        self._status_card.set_lines(lines)
        self._status_card.clear_buttons()
        back = GhostButton("Back")
        back.clicked.connect(self._return_to_locations)
        rescan = GhostButton("Rescan")
        rescan.clicked.connect(self._on_rescan)
        self._status_card.add_button(back)
        self._status_card.add_button(rescan)
        self._stack.setCurrentWidget(self._status_widget)
        self._toast("Library scan complete")

    def _on_scan_failed(self, exc) -> None:
        self._finish_worker()
        detail = str(exc)
        self._status_card.set_status(
            "⚠", "Scan failed", "Something went wrong while scanning."
        )
        self._status_card.set_lines([detail] if detail else [])
        self._status_card.clear_buttons()
        retry = PrimaryButton("Retry")
        retry.clicked.connect(lambda: self._start_scan(add_path=None))
        back = GhostButton("Back")
        back.clicked.connect(self._return_to_locations)
        self._status_card.add_button(back)
        self._status_card.add_button(retry)
        self._stack.setCurrentWidget(self._status_widget)
        self._toast(f"Scan failed: {exc.__class__.__name__}")

    def _finish_worker(self) -> None:
        app = self._app()
        library_flow.register_scan_worker(app, None)
        self._worker = None
        self._add_button.setEnabled(True)
        self._rescan_button.setEnabled(True)
        self._refresh_locations()

    def _return_to_locations(self) -> None:
        self._refresh_locations()
        self._stack.setCurrentWidget(self._locations_widget)

    # ------------------------------------------------------------------ #

    def _toast(self, message: str) -> None:
        window = self.window() if hasattr(self, "window") else None
        if window is not None and hasattr(window, "toast"):
            window.toast(message)
        else:
            print(message)  # noqa: T201 — fallback for headless tests
