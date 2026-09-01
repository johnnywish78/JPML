from __future__ import annotations

import os
import tempfile
from typing import Any, Generator

import pytest

from app.player import (
    AudioTrack,
    MediaInfo,
    PlaybackCallbacks,
    PlayerBackend,
    PlayerState,
    SubtitleTrack,
    VideoTrack,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_temp_media(suffix: str = ".mkv") -> str:
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.write(fd, b"\x00" * 1024)
    os.close(fd)
    return path


def _is_vlc_available() -> bool:
    try:
        from app.player.vlc_backend import VLCPlayerBackend
        b = VLCPlayerBackend(vlc_args=["--quiet", "--no-xlib"])
        b.release()
        return True
    except Exception:
        return False


def _is_mpv_available() -> bool:
    try:
        import mpv as _mpv
        p = _mpv.MPV()
        p.terminate()
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Backend fixture — fresh instance per test
# ---------------------------------------------------------------------------

BACKEND_FACTORIES: list[tuple[str, Any]] = [("MockPlayerBackend", None)]

if _is_vlc_available():
    from app.player.vlc_backend import VLCPlayerBackend
    BACKEND_FACTORIES.append(("VLCPlayerBackend", VLCPlayerBackend))

if _is_mpv_available():
    from app.player.mpv_backend import MPVPlayerBackend
    BACKEND_FACTORIES.append(("MPVPlayerBackend", MPVPlayerBackend))


@pytest.fixture(params=BACKEND_FACTORIES, ids=[n for n, _ in BACKEND_FACTORIES])
def backend(request: pytest.FixtureRequest) -> Generator[PlayerBackend, None, None]:
    name, factory = request.param
    if factory is None:
        from app.player import MockPlayerBackend
        inst = MockPlayerBackend()
    else:
        if name == "VLCPlayerBackend":
            inst = factory(vlc_args=["--quiet", "--no-xlib"])
        else:
            inst = factory()
    yield inst
    try:
        inst.close()
    except Exception:
        pass
    try:
        inst.release()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Cross-backend contract tests
# ---------------------------------------------------------------------------


class TestContractInitialState:
    def test_not_open_initially(self, backend: PlayerBackend) -> None:
        assert backend.is_open() is False

    def test_not_playing_initially(self, backend: PlayerBackend) -> None:
        assert backend.is_playing() is False

    def test_not_paused_initially(self, backend: PlayerBackend) -> None:
        assert backend.is_paused() is False


class TestContractLifecycle:
    def test_open_makes_is_open(self, backend: PlayerBackend) -> None:
        path = _make_temp_media()
        try:
            backend.open(path)
            assert backend.is_open() is True
        finally:
            os.unlink(path)

    def test_close_clears_state(self, backend: PlayerBackend) -> None:
        path = _make_temp_media()
        try:
            backend.open(path)
            backend.close()
            assert backend.is_open() is False
        finally:
            os.unlink(path)

    def test_stop_clears_state(self, backend: PlayerBackend) -> None:
        path = _make_temp_media()
        try:
            backend.open(path)
            backend.stop()
            assert backend.is_open() is False
        finally:
            os.unlink(path)

    def test_close_without_open_safe(self, backend: PlayerBackend) -> None:
        backend.close()

    def test_stop_without_open_safe(self, backend: PlayerBackend) -> None:
        backend.stop()


class TestContractPlaybackControls:
    def test_play_pause_cycle(self, backend: PlayerBackend) -> None:
        path = _make_temp_media()
        try:
            backend.open(path)
            backend.play()
            backend.pause()
            # Null-byte files may not actually transition states,
            # just verify no crash and backend is still open.
            assert backend.is_open() is True
        finally:
            os.unlink(path)

    def test_toggle_pause(self, backend: PlayerBackend) -> None:
        path = _make_temp_media()
        try:
            backend.open(path)
            backend.toggle_pause()
            backend.toggle_pause()
            assert backend.is_open() is True
        finally:
            os.unlink(path)

    def test_play_without_open_raises(self, backend: PlayerBackend) -> None:
        with pytest.raises(RuntimeError):
            backend.play()

    def test_pause_without_open_raises(self, backend: PlayerBackend) -> None:
        with pytest.raises(RuntimeError):
            backend.pause()

    def test_toggle_pause_without_open_raises(self, backend: PlayerBackend) -> None:
        with pytest.raises(RuntimeError):
            backend.toggle_pause()


class TestContractSeek:
    def test_seek_non_negative(self, backend: PlayerBackend) -> None:
        path = _make_temp_media()
        try:
            backend.open(path)
            backend.seek(0.0)
            assert backend.get_position() >= 0.0
        finally:
            os.unlink(path)

    def test_seek_clamps_negative(self, backend: PlayerBackend) -> None:
        path = _make_temp_media()
        try:
            backend.open(path)
            backend.seek(-10.0)
            assert backend.get_position() >= 0.0
        finally:
            os.unlink(path)

    def test_seek_without_open_raises(self, backend: PlayerBackend) -> None:
        with pytest.raises(RuntimeError):
            backend.seek(10.0)


class TestContractVolume:
    def test_set_volume(self, backend: PlayerBackend) -> None:
        path = _make_temp_media()
        try:
            backend.open(path)
            backend.set_volume(0.5)
        finally:
            os.unlink(path)

    def test_set_volume_without_open_raises(self, backend: PlayerBackend) -> None:
        with pytest.raises(RuntimeError):
            backend.set_volume(0.5)


class TestContractGetState:
    def test_get_state_after_open(self, backend: PlayerBackend) -> None:
        path = _make_temp_media()
        try:
            backend.open(path)
            state = backend.get_state()
            assert isinstance(state, PlayerState)
            assert state.path == path
        finally:
            os.unlink(path)

    def test_get_state_without_open_raises(self, backend: PlayerBackend) -> None:
        with pytest.raises(RuntimeError):
            backend.get_state()


class TestContractDataObjects:
    def test_audio_track(self, backend: PlayerBackend) -> None:
        t = AudioTrack(id=1, name="Track", language="en")
        assert t.id == 1
        assert t.name == "Track"
        assert t.language == "en"

    def test_subtitle_track(self, backend: PlayerBackend) -> None:
        t = SubtitleTrack(id=2, name="Sub")
        assert t.id == 2

    def test_video_track(self, backend: PlayerBackend) -> None:
        t = VideoTrack(id=0, name="Video", width=1920, height=1080)
        assert t.width == 1920
        assert t.height == 1080

    def test_media_info(self, backend: PlayerBackend) -> None:
        info = MediaInfo(path="/test.mkv", duration_ms=60000)
        assert info.path == "/test.mkv"

    def test_playback_callbacks(self, backend: PlayerBackend) -> None:
        cb = PlaybackCallbacks()
        assert cb.on_end_reached is None
        assert cb.on_error is None
        assert cb.on_state_changed is None
