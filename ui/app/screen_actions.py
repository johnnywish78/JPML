"""Common screen actions: play, details, favorite/watchlist, context menu.

Every content screen mixes this in so the interaction model is identical
across Home/Movies/Favorites/Collections/etc.
"""
from __future__ import annotations

from PyQt6.QtCore import QPoint
from PyQt6.QtWidgets import QMenu, QLabel

from ui.app import data
from ui.app.view_model import BaseViewModel, UiContext
from ui.models import EntityRef


class ScreenActions:
    """Requires: self.context, and (optionally) access to a main window
    for toasts — screens resolve it from the context."""

    def _toast(self, message: str) -> None:
        window = self.window() if hasattr(self, "window") else None
        if window is not None and hasattr(window, "toast"):
            window.toast(message)
        else:
            print(message)  # noqa: T201 — fallback for headless tests

    def play_entity(self, ref: EntityRef) -> None:
        if ref.kind == "episode":
            self._toast("Episode playback uses the TV show details view")
            self.open_details(ref)
            return
        file_path = data.resolve_play_file(self.context.services, ref)
        if not file_path:
            self._toast("This media file is currently unavailable")
            return
        self.context.navigation.navigate(
            "player",
            kind=ref.kind,
            entity_id=ref.entity_id,
            title=ref.title,
            file_path=file_path,
        )

    def open_details(self, ref: EntityRef) -> None:
        self.context.navigation.navigate(
            "details",
            kind=ref.kind,
            entity_id=ref.entity_id,
            title=ref.title,
        )

    def entity_action(self, ref: EntityRef, action: str) -> None:
        services = self.context.services
        try:
            if action == "favorite":
                if ref.is_favorite:
                    services.favorites.remove(ref.kind, ref.entity_id)
                else:
                    services.favorites.add(ref.kind, ref.entity_id)
                ref.is_favorite = not ref.is_favorite
                self._toast(
                    "Removed from Favorites" if ref.is_favorite is False else "Added to Favorites"
                )
                self._refresh_after_state_change()
            elif action == "watchlist":
                if ref.in_watchlist:
                    services.watchlist.remove(ref.kind, ref.entity_id)
                else:
                    services.watchlist.add(ref.kind, ref.entity_id)
                ref.in_watchlist = not ref.in_watchlist
                self._toast(
                    "Removed from Watchlist" if ref.in_watchlist is False else "Added to Watchlist"
                )
                self._refresh_after_state_change()
        except Exception as exc:  # noqa: BLE001 — surface as toast, never crash
            self._toast(f"Couldn't update: {exc.__class__.__name__}")

    def entity_context_menu(self, ref: EntityRef, pos: QPoint) -> None:
        menu = QMenu(self)
        play = menu.addAction("Play")
        details = menu.addAction("Details")
        menu.addSeparator()
        fav = menu.addAction(
            "Remove from Favorites" if ref.is_favorite else "Add to Favorites"
        )
        wl = menu.addAction(
            "Remove from Watchlist" if ref.in_watchlist else "Add to Watchlist"
        )
        menu.addSeparator()
        add_collection = menu.addAction("Add to Collection…")
        chosen = menu.exec(pos.toPoint())
        if chosen is None:
            return
        if chosen is play:
            self.play_entity(ref)
        elif chosen is details:
            self.open_details(ref)
        elif chosen is fav:
            self.entity_action(ref, "favorite")
        elif chosen is wl:
            self.entity_action(ref, "watchlist")
        elif chosen is add_collection:
            self._add_to_collection(ref)

    def _add_to_collection(self, ref: EntityRef) -> None:
        services = self.context.services
        collections = data.fetch_collections(services)
        if not collections:
            self._toast("Create a collection first")
            self.context.navigation.navigate("collections")
            return
        menu = QMenu(self)
        actions = {}
        for collection in collections:
            action = menu.addAction(collection.name)
            actions[action] = collection
        chosen = menu.exec(self.mapToGlobal(self.rect().topLeft()))
        if chosen is None or chosen not in actions:
            return
        collection = actions[chosen]
        try:
            services.collections.add_item(collection.id, ref.kind, ref.entity_id)
            self._toast(f"Added to {collection.name}")
        except Exception as exc:  # noqa: BLE001
            self._toast(f"Couldn't add to collection: {exc.__class__.__name__}")

    # -- refresh hook ------------------------------------------------------

    def _refresh_after_state_change(self) -> None:
        loader = getattr(self, "load", None)
        if callable(loader):
            loader()

    def make_context_label(self, title: str, subtitle: str) -> QLabel:
        label = QLabel(title)
        label.setTextFormat(label.textFormat())
        return label
