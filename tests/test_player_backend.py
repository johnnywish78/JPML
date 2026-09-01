from __future__ import annotations

import pytest

from app.player import MockPlayerBackend, PlayerState


class TestMockPlayerBackend:
    def test_open_and_is_open(self) -> None:
        backend = MockPlayerBackend()
        assert backend.is_open() is False
        backend.open("/path/to/movie.mkv")
        assert backend.is_open() is True

    def test_close(self) -> None:
        backend = MockPlayerBackend()
        backend.open("/path/to/movie.mkv")
        backend.close()
        assert backend.is_open() is False

    def test_stop(self) -> None:
        backend = MockPlayerBackend()
        backend.open("/path/to/movie.mkv")
        backend.stop()
        assert backend.is_open() is False

    def test_play_and_pause(self) -> None:
        backend = MockPlayerBackend()
        backend.open("/path/to/movie.mkv")
        assert backend.is_paused() is True

        backend.play()
        assert backend.is_playing() is True
        assert backend.is_paused() is False

        backend.pause()
        assert backend.is_paused() is True
        assert backend.is_playing() is False

    def test_toggle_pause(self) -> None:
        backend = MockPlayerBackend()
        backend.open("/path/to/movie.mkv")
        assert backend.is_paused() is True
        backend.toggle_pause()
        assert backend.is_paused() is False
        backend.toggle_pause()
        assert backend.is_paused() is True

    def test_seek(self) -> None:
        backend = MockPlayerBackend()
        backend.open("/path/to/movie.mkv")
        backend.seek(60.0)
        assert backend.get_position() == 60.0

    def test_seek_clamps_negative(self) -> None:
        backend = MockPlayerBackend()
        backend.open("/path/to/movie.mkv")
        backend.seek(-10.0)
        assert backend.get_position() == 0.0

    def test_set_volume(self) -> None:
        backend = MockPlayerBackend()
        backend.open("/path/to/movie.mkv")
        backend.set_volume(0.5)
        assert backend.get_state().volume == 0.5

    def test_set_volume_clamps(self) -> None:
        backend = MockPlayerBackend()
        backend.open("/path/to/movie.mkv")
        backend.set_volume(2.0)
        assert backend.get_state().volume == 1.0
        backend.set_volume(-0.5)
        assert backend.get_state().volume == 0.0

    def test_get_state(self) -> None:
        backend = MockPlayerBackend()
        backend.open("/path/to/movie.mkv")
        state = backend.get_state()
        assert state.path == "/path/to/movie.mkv"
        assert state.position_seconds == 0.0
        assert state.is_paused is True

    def test_no_media_errors(self) -> None:
        backend = MockPlayerBackend()
        with pytest.raises(RuntimeError):
            backend.play()
        with pytest.raises(RuntimeError):
            backend.pause()
        with pytest.raises(RuntimeError):
            backend.toggle_pause()
        with pytest.raises(RuntimeError):
            backend.seek(10.0)
        with pytest.raises(RuntimeError):
            backend.set_volume(0.5)
        with pytest.raises(RuntimeError):
            backend.get_state()
        with pytest.raises(RuntimeError):
            backend.get_position()
        with pytest.raises(RuntimeError):
            backend.get_duration()
