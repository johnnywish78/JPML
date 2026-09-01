from __future__ import annotations

import os
import tempfile
import time

import pytest

from app.bootstrap import (
    create_event_bus,
    create_player_controller,
    create_playback_service,
)
from app.library.playback_repository import PlaybackRepository
from app.player.controller import PlayerController
from app.player.events import PlaybackEvent, PlaybackEventData, PlaybackEventBus
from app.player.factory import create_backend
from app.player.vlc_backend import VLCPlayerBackend
from app.services.playback import PlaybackService


TEST_FILE = "/run/media/johnny/Movies/Le_Cercle_Rouge.1970.mkv"


def _skip_if_no_media() -> None:
    if not os.path.exists(TEST_FILE):
        pytest.skip("test media file not available")


def _make_temp_media() -> str:
    fd, path = tempfile.mkstemp(suffix=".mkv")
    os.write(fd, b"\x00" * 1024)
    os.close(fd)
    return path


# ---------------------------------------------------------------------------
# A. Bootstrap / composition root
# ---------------------------------------------------------------------------

class TestBootstrap:
    def test_create_event_bus(self) -> None:
        bus = create_event_bus()
        assert isinstance(bus, PlaybackEventBus)

    def test_create_vlc_backend(self) -> None:
        backend = create_backend("vlc")
        assert isinstance(backend, VLCPlayerBackend)
        assert backend.is_open() is False
        backend.release()

    def test_create_playback_service(self) -> None:
        svc = create_playback_service()
        assert isinstance(svc, PlaybackService)
        assert svc.is_open() is False

    def test_create_player_controller(self) -> None:
        ctrl = create_player_controller()
        assert isinstance(ctrl, PlayerController)
        ctrl.release()


# ---------------------------------------------------------------------------
# B. PlayerController with VLC backend
# ---------------------------------------------------------------------------

class TestPlayerControllerVLC:
    def test_controller_uses_vlc_backend(self) -> None:
        ctrl = create_player_controller()
        assert isinstance(ctrl.backend, VLCPlayerBackend)
        ctrl.release()

    def test_controller_has_event_bus(self) -> None:
        bus = create_event_bus()
        ctrl = create_player_controller(event_bus=bus)
        assert ctrl.event_bus is bus
        ctrl.release()


# ---------------------------------------------------------------------------
# C. Open / resume flow
# ---------------------------------------------------------------------------

class TestOpenResumeFlow:
    def test_open_real_file(self) -> None:
        _skip_if_no_media()
        ctrl = create_player_controller()
        try:
            resume = ctrl.open("movie", 1, TEST_FILE, backend_used="vlc")
            assert isinstance(resume, float)
            assert ctrl.is_open() is True
        finally:
            ctrl.release()

    def test_open_missing_file_raises(self) -> None:
        ctrl = create_player_controller()
        with pytest.raises(FileNotFoundError):
            ctrl.open("movie", 1, "/nonexistent/file.mkv")
        ctrl.release()

    def test_open_empty_path_raises(self) -> None:
        ctrl = create_player_controller()
        with pytest.raises(ValueError):
            ctrl.open("movie", 1, "")
        ctrl.release()


# ---------------------------------------------------------------------------
# D. Playback controls through controller
# ---------------------------------------------------------------------------

class TestPlaybackControls:
    def test_play_pause_stop(self) -> None:
        _skip_if_no_media()
        ctrl = create_player_controller()
        try:
            ctrl.open("movie", 1, TEST_FILE)
            time.sleep(1.0)
            ctrl.pause()
            time.sleep(0.3)
            assert ctrl.is_paused() is True
            ctrl.play()
            time.sleep(0.3)
            assert ctrl.is_playing() is True
            ctrl.stop()
            assert ctrl.is_open() is False
        finally:
            ctrl.release()

    def test_seek(self) -> None:
        _skip_if_no_media()
        ctrl = create_player_controller()
        try:
            ctrl.open("movie", 1, TEST_FILE)
            time.sleep(1.5)
            ctrl.seek(60.0)
            time.sleep(0.5)
            pos = ctrl.get_position()
            assert pos > 0
        finally:
            ctrl.release()


# ---------------------------------------------------------------------------
# E. Volume through controller
# ---------------------------------------------------------------------------

class TestVolume:
    def test_set_get_volume(self) -> None:
        _skip_if_no_media()
        ctrl = create_player_controller()
        try:
            ctrl.open("movie", 1, TEST_FILE)
            time.sleep(0.5)
            ctrl.set_volume(0.4)
            time.sleep(0.3)
            vol = ctrl.get_volume()
            assert abs(vol - 0.4) < 0.1
        finally:
            ctrl.release()

    def test_mute_unmute(self) -> None:
        _skip_if_no_media()
        ctrl = create_player_controller()
        try:
            ctrl.open("movie", 1, TEST_FILE)
            time.sleep(0.5)
            ctrl.mute()
            time.sleep(0.2)
            assert ctrl.is_muted() is True
            ctrl.unmute()
            time.sleep(0.2)
            assert ctrl.is_muted() is False
        finally:
            ctrl.release()


# ---------------------------------------------------------------------------
# F. Playback rate through controller
# ---------------------------------------------------------------------------

class TestPlaybackRate:
    def test_set_rate(self) -> None:
        _skip_if_no_media()
        ctrl = create_player_controller()
        try:
            ctrl.open("movie", 1, TEST_FILE)
            time.sleep(1.0)
            ctrl.set_playback_rate(2.0)
            assert ctrl.get_playback_rate() == 2.0
        finally:
            ctrl.release()


# ---------------------------------------------------------------------------
# G. Audio / subtitle tracks through controller
# ---------------------------------------------------------------------------

class TestTracks:
    def test_audio_tracks(self) -> None:
        _skip_if_no_media()
        ctrl = create_player_controller()
        try:
            ctrl.open("movie", 1, TEST_FILE)
            time.sleep(1.5)
            tracks = ctrl.get_audio_tracks()
            assert len(tracks) >= 1
        finally:
            ctrl.release()

    def test_subtitle_tracks(self) -> None:
        _skip_if_no_media()
        ctrl = create_player_controller()
        try:
            ctrl.open("movie", 1, TEST_FILE)
            time.sleep(1.5)
            tracks = ctrl.get_subtitle_tracks()
            assert len(tracks) >= 1
        finally:
            ctrl.release()


# ---------------------------------------------------------------------------
# H. Video info through controller
# ---------------------------------------------------------------------------

class TestVideoInfo:
    def test_video_size(self) -> None:
        _skip_if_no_media()
        ctrl = create_player_controller()
        try:
            ctrl.open("movie", 1, TEST_FILE)
            time.sleep(1.5)
            size = ctrl.get_video_size()
            assert size is not None
            assert size[0] > 0
        finally:
            ctrl.release()

    def test_media_info(self) -> None:
        _skip_if_no_media()
        ctrl = create_player_controller()
        try:
            ctrl.open("movie", 1, TEST_FILE)
            time.sleep(1.5)
            info = ctrl.get_media_info()
            assert info.duration_ms > 0
        finally:
            ctrl.release()


# ---------------------------------------------------------------------------
# I. Position persistence through controller
# ---------------------------------------------------------------------------

class TestPersistence:
    def test_save_position(self) -> None:
        _skip_if_no_media()
        ctrl = create_player_controller()
        try:
            ctrl.open("movie", 1, TEST_FILE)
            time.sleep(1.0)
            ctrl.seek(120.0)
            ctrl.save_position()
            pos = ctrl.get_resume_position("movie", 1)
            assert pos == 120.0
        finally:
            ctrl.release()

    def test_close_persists_position(self) -> None:
        _skip_if_no_media()
        ctrl = create_player_controller()
        try:
            ctrl.open("movie", 1, TEST_FILE)
            time.sleep(1.0)
            ctrl.seek(200.0)
            ctrl.close()
            pos = ctrl.get_resume_position("movie", 1)
            assert pos == 200.0
        finally:
            ctrl.release()


# ---------------------------------------------------------------------------
# J. Completion through controller
# ---------------------------------------------------------------------------

class TestCompletion:
    def test_mark_completed(self) -> None:
        _skip_if_no_media()
        ctrl = create_player_controller()
        try:
            ctrl.open("movie", 1, TEST_FILE)
            ctrl.mark_completed()
            assert ctrl.is_completed("movie", 1) is True
            resume = ctrl.get_resume_position("movie", 1)
            assert resume == 0.0
        finally:
            ctrl.release()


# ---------------------------------------------------------------------------
# K. Event bus integration
# ---------------------------------------------------------------------------

class TestEventBus:
    def test_events_emitted_on_open(self) -> None:
        _skip_if_no_media()
        bus = create_event_bus()
        events: list[PlaybackEvent] = []
        bus.subscribe(
            PlaybackEvent.MEDIA_OPENED,
            lambda d: events.append(d.event),
        )
        bus.subscribe(
            PlaybackEvent.PLAYBACK_STARTED,
            lambda d: events.append(d.event),
        )
        ctrl = create_player_controller(event_bus=bus)
        try:
            ctrl.open("movie", 1, TEST_FILE)
            assert PlaybackEvent.MEDIA_OPENED in events
            assert PlaybackEvent.PLAYBACK_STARTED in events
        finally:
            ctrl.release()

    def test_events_emitted_on_pause(self) -> None:
        _skip_if_no_media()
        bus = create_event_bus()
        events: list[PlaybackEvent] = []
        bus.subscribe(
            PlaybackEvent.PLAYBACK_PAUSED,
            lambda d: events.append(d.event),
        )
        ctrl = create_player_controller(event_bus=bus)
        try:
            ctrl.open("movie", 1, TEST_FILE)
            time.sleep(0.5)
            ctrl.pause()
            assert PlaybackEvent.PLAYBACK_PAUSED in events
        finally:
            ctrl.release()

    def test_events_emitted_on_stop(self) -> None:
        _skip_if_no_media()
        bus = create_event_bus()
        events: list[PlaybackEvent] = []
        bus.subscribe(
            PlaybackEvent.PLAYBACK_STOPPED,
            lambda d: events.append(d.event),
        )
        ctrl = create_player_controller(event_bus=bus)
        try:
            ctrl.open("movie", 1, TEST_FILE)
            time.sleep(0.5)
            ctrl.stop()
            assert PlaybackEvent.PLAYBACK_STOPPED in events
        finally:
            ctrl.release()

    def test_events_emitted_on_close(self) -> None:
        _skip_if_no_media()
        bus = create_event_bus()
        events: list[PlaybackEvent] = []
        bus.subscribe(
            PlaybackEvent.PLAYBACK_STOPPED,
            lambda d: events.append(d.event),
        )
        ctrl = create_player_controller(event_bus=bus)
        try:
            ctrl.open("movie", 1, TEST_FILE)
            time.sleep(0.5)
            ctrl.close()
            assert PlaybackEvent.PLAYBACK_STOPPED in events
        finally:
            ctrl.release()

    def test_event_bus_subscribe_unsubscribe(self) -> None:
        bus = create_event_bus()
        events: list[PlaybackEvent] = []
        handler = lambda d: events.append(d.event)
        bus.subscribe(PlaybackEvent.PLAYBACK_STARTED, handler)
        bus.emit(PlaybackEventData(event=PlaybackEvent.PLAYBACK_STARTED))
        assert len(events) == 1
        bus.unsubscribe(PlaybackEvent.PLAYBACK_STARTED, handler)
        bus.emit(PlaybackEventData(event=PlaybackEvent.PLAYBACK_STARTED))
        assert len(events) == 1

    def test_event_bus_clear(self) -> None:
        bus = create_event_bus()
        bus.subscribe(
            PlaybackEvent.PLAYBACK_STARTED, lambda d: None
        )
        bus.clear()
        bus.emit(PlaybackEventData(event=PlaybackEvent.PLAYBACK_STARTED))


# ---------------------------------------------------------------------------
# L. Embedded video (no Qt, just API)
# ---------------------------------------------------------------------------

class TestEmbeddedVideo:
    def test_set_video_window_id(self) -> None:
        _skip_if_no_media()
        ctrl = create_player_controller()
        try:
            ctrl.open("movie", 1, TEST_FILE)
            ctrl.set_video_window_id(0)
        finally:
            ctrl.release()


# ---------------------------------------------------------------------------
# M. Repeated open/close resource safety
# ---------------------------------------------------------------------------

class TestResourceCleanup:
    def test_repeated_open_close(self) -> None:
        _skip_if_no_media()
        ctrl = create_player_controller()
        try:
            for i in range(3):
                ctrl.open("movie", i + 1, TEST_FILE)
                time.sleep(0.3)
                ctrl.close()
        finally:
            ctrl.release()

    def test_release_is_safe(self) -> None:
        ctrl = create_player_controller()
        ctrl.release()
