"""Collections — create/rename/delete with confirmation + items view.

Navigates to a collection detail via the route 'collection_detail'
(handled by this same screen class via params).
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

import ui.app.data as data
from ui.app.screen_actions import ScreenActions
from ui.components.cards.media_card import MediaCard
from ui.components.common.page_header import PageHeader
from ui.components.common.screen import BaseScreen
from ui.components.dialogs.collection_dialog import create_collection, rename_collection
from ui.components.dialogs.confirmation_dialog import confirm
from ui.components.media.media_grid import MediaGridView
from ui.themes.tokens import Spacing


class CollectionsScreen(BaseScreen, ScreenActions):
    def __init__(self, context) -> None:
        super().__init__(context)

    # -- state -------------------------------------------------------------

    def empty_title(self) -> str:
        return "No Collections Yet"

    def empty_subtitle(self) -> str:
        return "Group movies, shows and music into your own collections."

    def empty_action(self) -> str | None:
        return "New Collection"

    def page_title(self) -> str:
        return "Collections"

    def on_activated(self) -> None:
        route = self.context.navigation.current_route
        if route is not None and route.params.get("collection_id"):
            self._collection_id = int(route.params["collection_id"])
        else:
            self._collection_id = None
        self.load()

    # -- load ----------------------------------------------------------------

    def load(self) -> None:
        if self._collection_id is not None:
            self._load_detail()
        else:
            self._load_list()

    def _load_list(self) -> None:
        def gather(services):
            collections = services.collections.list()
            counts = {c.id: services.collections.count_items(c.id) for c in collections}
            return (collections, counts)

        self.start_async_load(gather)

    def handle_data(self, payload) -> None:
        collections, counts = payload
        self.clear_content()
        if not collections:
            self.show_empty()
            return
        header = PageHeader("Collections", subtitle="{n} collections")
        self.add_to_content(header)
        header.set_count(len(collections))

        for collection in collections:
            self.add_to_content(self._collection_row(collection, counts.get(collection.id, 0)))
        self.show_content()

    def _collection_row(self, collection, count: int) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(16, 12, 16, 12)
        card_frame = QPushButton("", row)
        card_frame.setObjectName("CardFrame")
        card_frame.setFixedSize(180, 40)
        layout.addWidget(card_frame)
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(2)
        name = QLabel(collection.name)
        name.setStyleSheet("font-size: 16px; font-weight: 600; background: transparent;")
        sub = QLabel(f"{count} items" + (f" · {collection.description}" if collection.description else ""))
        sub.setObjectName("SecondaryLabel")
        sub.setStyleSheet("font-size: 13px; background: transparent;")
        ll.addWidget(name)
        ll.addWidget(sub)
        layout.addWidget(left)
        layout.addStretch(1)

        open_button = QPushButton("Open")
        open_button.setObjectName("GhostButton")
        open_button.setCursor(Qt.CursorShape.PointingHandCursor)
        open_button.clicked.connect(
            lambda _=False, c=collection: self.context.navigation.navigate(
                "collections", collection_id=c.id, title=c.name
            )
        )
        layout.addWidget(open_button)

        rename_button = QPushButton("Rename")
        rename_button.setObjectName("GhostButton")
        rename_button.setCursor(Qt.CursorShape.PointingHandCursor)
        rename_button.clicked.connect(lambda _=False, c=collection: self._rename(c))
        layout.addWidget(rename_button)

        delete_button = QPushButton("Delete")
        delete_button.setObjectName("DangerButton")
        delete_button.setCursor(Qt.CursorShape.PointingHandCursor)
        delete_button.clicked.connect(lambda _=False, c=collection: self._delete(c))
        layout.addWidget(delete_button)
        return row

    # -- detail -----------------------------------------------------------------

    def _load_detail(self) -> None:
        self.start_async_load(self._gather_detail)

    def _gather_detail(self, services):
        collection = services.collections.get(self._collection_id)
        items = (
            data.fetch_collection_items(services, self._collection_id)
            if collection is not None
            else []
        )
        return (collection, items)

    def handle_data(self, payload) -> None:
        if self._collection_id is not None:
            collection, items = payload
            self._render_detail(collection, items)
        else:
            collections, counts = payload
            self._render_list(collections, counts)

    def _render_list(self, collections, counts) -> None:
        self.clear_content()
        if not collections:
            self.show_empty()
            return
        header = PageHeader("Collections", subtitle="{n} collections")
        self.add_to_content(header)
        header.set_count(len(collections))

        for collection in collections:
            self.add_to_content(self._collection_row(collection, counts.get(collection.id, 0)))
        self.show_content()

    def _render_detail(self, collection, items: list) -> None:
        self.clear_content()
        if collection is None:
            self.show_empty()
            return
        header = PageHeader(collection.name, subtitle=f"{len(items)} items")
        back = QPushButton("← Back")
        back.setObjectName("GhostButton")
        back.setCursor(Qt.CursorShape.PointingHandCursor)
        back.clicked.connect(
            lambda: self.context.navigation.navigate("collections")
        )
        header.add_control(back)
        self.add_to_content(header)

        if not items:
            label = QLabel("This collection is empty. Add items from any media card.")
            label.setObjectName("SecondaryLabel")
            label.setStyleSheet("font-size: 14px; background: transparent;")
            self.add_to_content(label)
            self.show_content()
            return

        grid = MediaGridView(self, parent=self.container)
        grid.set_entities(items)
        self.add_to_content(grid, stretch=1)
        self.show_content()

    # -- actions ------------------------------------------------------------------

    def entity_context_menu(self, ref, pos) -> None:
        """In collection-detail view, add a 'Remove from collection' entry."""
        if self._collection_id is None:
            super().entity_context_menu(ref, pos)
            return
        menu = __import__("PyQt6.QtWidgets", fromlist=["QMenu"]).QMenu(self)
        play = menu.addAction("Play")
        details = menu.addAction("Details")
        menu.addSeparator()
        remove = menu.addAction("Remove from Collection")
        chosen = menu.exec(pos.toPoint() if hasattr(pos, "toPoint") else pos)
        if chosen is None:
            return
        if chosen is play:
            self.play_entity(ref)
        elif chosen is details:
            self.open_details(ref)
        elif chosen is remove:
            try:
                self.context.services.collections.remove_item(
                    self._collection_id, ref.kind, ref.entity_id
                )
                self._toast("Removed from collection")
                self.load()
            except Exception as exc:  # noqa: BLE001
                self._toast(f"Couldn't remove: {exc.__class__.__name__}")

    def _create(self) -> None:
        name = create_collection(self)
        if not name:
            return
        try:
            self.context.services.collections.create(name)
            self._toast("Collection created")
            self.load()
        except Exception as exc:  # noqa: BLE001
            self._toast(f"Couldn't create collection: {exc.__class__.__name__}")

    def _rename(self, collection) -> None:
        name = rename_collection(collection.name, self)
        if not name:
            return
        try:
            self.context.services.collections.rename(collection.id, name)
            self._toast("Collection renamed")
            self.load()
        except Exception as exc:  # noqa: BLE001
            self._toast(f"Couldn't rename: {exc.__class__.__name__}")

    def _delete(self, collection) -> None:
        if not confirm(
            "Delete collection",
            f"“{collection.name}” and its item list will be removed. "
            "The media itself is not deleted.",
            confirm_text="Delete",
            parent=self,
        ):
            return
        try:
            self.context.services.collections.delete(collection.id)
            self._toast("Collection deleted")
            self.load()
        except Exception as exc:  # noqa: BLE001
            self._toast(f"Couldn't delete: {exc.__class__.__name__}")

    # BaseScreen empty action
    def empty_action_clicked(self) -> None:
        self._create()

    def refresh_theme(self) -> None:
        pass
