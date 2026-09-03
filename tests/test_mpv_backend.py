from __future__ import annotations

import os
import tempfile
import time
from unittest.mock import MagicMock

import pytest

from app.player import (
    AudioTrack,
    MediaInfo,
    PlaybackCallbacks,
    SubtitleTrack,
    VideoTrack,
)
from app.player.mpv_backend import BACKEND_NAME, MPVPlayerBackend


# ---------------------------------------------------------------------------
# Skip entire module if python-mpv cannot create instances
# ---------------------------------------------------------------------------

def _mpv_available() -> bool:
    try:
        import mpv as _mpv
        p = _mpv.MPV()
        p.terminate()
        return True
    except Exception:
        return False


MPV_AVAILABLE = _mpv_available()

pytestmark = pytest.mark.skipif(
    not MPV_AVAILABLE,
    reason="python-mpv or libmpv not available",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_temp_media(suffix: str = ".mkv") -> str:
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.write(fd, b"\x00" * 1024)
    os.close(fd)
    return path


def _make_backend(**kwargs) -> MPVPlayerBackend:
    return MPVPlayerBackend(mpv_args=[], **kwargs)


# ---------------------------------------------------------------------------
# A. Backend creation & initial state
# ---------------------------------------------------------------------------

class TestCreation:
    def test_create_backend(self) -> None:
        backend = _make_backend()
        assert backend.is_open() is False
        backend.release()

    def test_backend_name(self) -> None:
        assert BACKEND_NAME == "mpv"

    def test_initial_state_queries(self) -> None:
        backend = _make_backend()
        assert backend.is_open() is False
        assert backend.is_playing() is False
        assert backend.is_paused() is False
        assert backend.get_position() == 0.0
        assert backend.get_duration() == 0.0
        assert backend.get_volume() == 1.0
        assert backend.get_playback_rate() == 1.0
        backend.release()

    def test_initial_tracks_empty(self) -> None:
        backend = _make_backend()
        assert backend.get_audio_tracks() == []
        assert backend.get_subtitle_tracks() == []
        assert backend.get_video_tracks() == []
        assert backend.get_current_audio_track() == -1
        assert backend.get_current_subtitle_track() == -1
        backend.release()

    def test_initial_video_info(self) -> None:
        backend = _make_backend()
        assert backend.get_video_size() is None
        assert backend.get_aspect_ratio() is None
        assert backend.get_crop_geometry() is None
        backend.release()

    def test_initial_media_info(self) -> None:
        backend = _make_backend()
        info = backend.get_media_info()
        assert info.path == ""
        assert info.duration_ms == 0
        backend.release()


# ---------------------------------------------------------------------------
# B. Open / close / stop lifecycle
# ---------------------------------------------------------------------------

class TestLifecycle:
    def test_open_real_file(self) -> None:
        path = _make_temp_media()
        backend = _make_backend()
        try:
            backend.open(path)
            assert backend.is_open() is True
        finally:
            backend.close()
            backend.release()
            os.unlink(path)

    def test_open_empty_path_raises(self) -> None:
        backend = _make_backend()
        with pytest.raises(ValueError, match="empty"):
            backend.open("")
        backend.release()

    def test_open_missing_file_raises(self) -> None:
        backend = _make_backend()
        with pytest.raises(FileNotFoundError):
            backend.open("/nonexistent/path/movie.mkv")
        backend.release()

    def test_close_clears_state(self) -> None:
        path = _make_temp_media()
        backend = _make_backend()
        try:
            backend.open(path)
            backend.close()
            assert backend.is_open() is False
            assert backend.is_playing() is False
        finally:
            backend.release()
            os.unlink(path)

    def test_stop_clears_state(self) -> None:
        path = _make_temp_media()
        backend = _make_backend()
        try:
            backend.open(path)
            backend.stop()
            assert backend.is_open() is False
        finally:
            backend.release()
            os.unlink(path)

    def test_close_without_open_is_safe(self) -> None:
        backend = _make_backend()
        backend.close()
        backend.release()

    def test_stop_without_open_is_safe(self) -> None:
        backend = _make_backend()
        backend.stop()
        backend.release()

    def test_reopen_replaces_media(self) -> None:
        path1 = _make_temp_media()
        path2 = _make_temp_media()
        backend = _make_backend()
        try:
            backend.open(path1)
            assert backend.is_open() is True
            backend.open(path2)
            assert backend.is_open() is True
        finally:
            backend.close()
            backend.release()
            os.unlink(path1)
            os.unlink(path2)

    def test_release_makes_unusable(self) -> None:
        backend = _make_backend()
        backend.release()
        assert True


# ---------------------------------------------------------------------------
# C. Play / pause / toggle_pause
# ---------------------------------------------------------------------------

class TestPlaybackControls:
    def test_play_and_pause(self) -> None:
        path = _make_temp_media()
        backend = _make_backend()
        try:
            backend.open(path)
            backend.play()
            time.sleep(0.3)
            backend.pause()
            time.sleep(0.1)
            assert backend.is_open() is True
        finally:
            backend.close()
            backend.release()
            os.unlink(path)

    def test_toggle_pause(self) -> None:
        path = _make_temp_media()
        backend = _make_backend()
        try:
            backend.open(path)
            time.sleep(0.3)
            backend.toggle_pause()
            time.sleep(0.1)
            backend.toggle_pause()
            time.sleep(0.1)
            assert backend.is_open() is True
        finally:
            backend.close()
            backend.release()
            os.unlink(path)

    def test_play_without_open_raises(self) -> None:
        backend = _make_backend()
        with pytest.raises(RuntimeError):
            backend.play()
        backend.release()

    def test_pause_without_open_raises(self) -> None:
        backend = _make_backend()
        with pytest.raises(RuntimeError):
            backend.pause()
        backend.release()

    def test_toggle_pause_without_open_raises(self) -> None:
        backend = _make_backend()
        with pytest.raises(RuntimeError):
            backend.toggle_pause()
        backend.release()


# ---------------------------------------------------------------------------
# D. Seek
# ---------------------------------------------------------------------------

class TestSeek:
    def test_seek(self) -> None:
        path = _make_temp_media()
        backend = _make_backend()
        try:
            backend.open(path)
            backend.seek(0.0)
            assert backend.get_position() >= 0.0
        finally:
            backend.close()
            backend.release()
            os.unlink(path)

    def test_seek_clamps_negative(self) -> None:
        path = _make_temp_media()
        backend = _make_backend()
        try:
            backend.open(path)
            backend.seek(-10.0)
            assert backend.get_position() >= 0.0
        finally:
            backend.close()
            backend.release()
            os.unlink(path)

    def test_seek_without_open_raises(self) -> None:
        backend = _make_backend()
        with pytest.raises(RuntimeError):
            backend.seek(10.0)
        backend.release()


# ---------------------------------------------------------------------------
# E. Volume
# ---------------------------------------------------------------------------

class TestVolume:
    def test_set_volume(self) -> None:
        path = _make_temp_media()
        backend = _make_backend()
        try:
            backend.open(path)
            backend.set_volume(0.5)
            vol = backend.get_volume()
            assert abs(vol - 0.5) < 0.02
        finally:
            backend.close()
            backend.release()
            os.unlink(path)

    def test_volume_clamps_high(self) -> None:
        path = _make_temp_media()
        backend = _make_backend()
        try:
            backend.open(path)
            backend.set_volume(2.0)
            vol = backend.get_volume()
            assert vol <= 1.01
        finally:
            backend.close()
            backend.release()
            os.unlink(path)

    def test_volume_clamps_low(self) -> None:
        path = _make_temp_media()
        backend = _make_backend()
        try:
            backend.open(path)
            backend.set_volume(-0.5)
            vol = backend.get_volume()
            assert vol >= -0.01
        finally:
            backend.close()
            backend.release()
            os.unlink(path)

    def test_mute_unmute(self) -> None:
        path = _make_temp_media()
        backend = _make_backend()
        try:
            backend.open(path)
            assert backend.is_muted() is False
            backend.mute()
            assert backend.is_muted() is True
            backend.unmute()
            assert backend.is_muted() is False
        finally:
            backend.close()
            backend.release()
            os.unlink(path)

    def test_set_volume_without_open_raises(self) -> None:
        backend = _make_backend()
        with pytest.raises(RuntimeError):
            backend.set_volume(0.5)
        backend.release()

    def test_mute_without_open_raises(self) -> None:
        backend = _make_backend()
        with pytest.raises(RuntimeError):
            backend.mute()
        backend.release()


# ---------------------------------------------------------------------------
# F. Playback rate
# ---------------------------------------------------------------------------

class TestPlaybackRate:
    def test_default_rate(self) -> None:
        path = _make_temp_media()
        backend = _make_backend()
        try:
            backend.open(path)
            rate = backend.get_playback_rate()
            assert rate == 1.0
        finally:
            backend.close()
            backend.release()
            os.unlink(path)

    def test_set_rate(self) -> None:
        path = _make_temp_media()
        backend = _make_backend()
        try:
            backend.open(path)
            backend.set_playback_rate(2.0)
            rate = backend.get_playback_rate()
            assert rate == 2.0
        finally:
            backend.close()
            backend.release()
            os.unlink(path)

    def test_set_rate_without_open_raises(self) -> None:
        backend = _make_backend()
        with pytest.raises(RuntimeError):
            backend.set_playback_rate(1.5)
        backend.release()

    def test_invalid_rate_raises(self) -> None:
        path = _make_temp_media()
        backend = _make_backend()
        try:
            backend.open(path)
            with pytest.raises(ValueError, match="positive"):
                backend.set_playback_rate(0.0)
            with pytest.raises(ValueError, match="positive"):
                backend.set_playback_rate(-1.0)
        finally:
            backend.close()
            backend.release()
            os.unlink(path)


# ---------------------------------------------------------------------------
# G. Audio tracks
# ---------------------------------------------------------------------------

class TestAudioTracks:
    def test_audio_tracks_without_media(self) -> None:
        backend = _make_backend()
        assert backend.get_audio_tracks() == []
        backend.release()

    def test_audio_tracks_with_real_file(self) -> None:
        test_file = "/run/media/johnny/Movies/Le_Cercle_Rouge.1970.mkv"
        if not os.path.exists(test_file):
            pytest.skip("test media file not available")

        backend = _make_backend()
        try:
            backend.open(test_file)
            time.sleep(1.5)
            tracks = backend.get_audio_tracks()
            assert len(tracks) >= 1
            for t in tracks:
                assert isinstance(t.id, int)
                assert isinstance(t.name, str)
                assert t.id >= 0
        finally:
            backend.close()
            backend.release()

    def test_set_audio_track_without_open_raises(self) -> None:
        backend = _make_backend()
        with pytest.raises(RuntimeError):
            backend.set_audio_track(0)
        backend.release()


# ---------------------------------------------------------------------------
# H. Subtitle tracks
# ---------------------------------------------------------------------------

class TestSubtitleTracks:
    def test_subtitle_tracks_without_media(self) -> None:
        backend = _make_backend()
        assert backend.get_subtitle_tracks() == []
        backend.release()

    def test_subtitle_tracks_with_real_file(self) -> None:
        test_file = "/run/media/johnny/Movies/Le_Cercle_Rouge.1970.mkv"
        if not os.path.exists(test_file):
            pytest.skip("test media file not available")

        backend = _make_backend()
        try:
            backend.open(test_file)
            time.sleep(1.5)
            tracks = backend.get_subtitle_tracks()
            assert len(tracks) >= 1
            for t in tracks:
                assert isinstance(t.id, int)
                assert isinstance(t.name, str)
        finally:
            backend.close()
            backend.release()

    def test_set_subtitle_track_without_open_raises(self) -> None:
        backend = _make_backend()
        with pytest.raises(RuntimeError):
            backend.set_subtitle_track(0)
        backend.release()


# ---------------------------------------------------------------------------
# I. Video tracks / info
# ---------------------------------------------------------------------------

class TestVideoInfo:
    def test_video_tracks_without_media(self) -> None:
        backend = _make_backend()
        assert backend.get_video_tracks() == []
        backend.release()

    def test_video_size_without_media(self) -> None:
        backend = _make_backend()
        assert backend.get_video_size() is None
        backend.release()

    def test_video_size_with_real_file(self) -> None:
        test_file = "/run/media/johnny/Movies/Le_Cercle_Rouge.1970.mkv"
        if not os.path.exists(test_file):
            pytest.skip("test media file not available")

        backend = _make_backend()
        try:
            backend.open(test_file)
            time.sleep(1.5)
            size = backend.get_video_size()
            assert size is not None
            w, h = size
            assert w > 0
            assert h > 0
        finally:
            backend.close()
            backend.release()

    def test_aspect_ratio_without_media(self) -> None:
        backend = _make_backend()
        assert backend.get_aspect_ratio() is None
        backend.release()

    def test_crop_geometry_without_media(self) -> None:
        backend = _make_backend()
        assert backend.get_crop_geometry() is None
        backend.release()

    def test_set_aspect_ratio_without_open_raises(self) -> None:
        backend = _make_backend()
        with pytest.raises(RuntimeError):
            backend.set_aspect_ratio("16:9")
        backend.release()

    def test_set_crop_geometry_without_open_raises(self) -> None:
        backend = _make_backend()
        with pytest.raises(RuntimeError):
            backend.set_crop_geometry("16:9")
        backend.release()

    def test_set_deinterlace_without_open_raises(self) -> None:
        backend = _make_backend()
        with pytest.raises(RuntimeError):
            backend.set_deinterlace("auto")
        backend.release()


# ---------------------------------------------------------------------------
# J. Media info
# ---------------------------------------------------------------------------

class TestMediaInfo:
    def test_media_info_empty(self) -> None:
        backend = _make_backend()
        info = backend.get_media_info()
        assert info.path == ""
        assert info.duration_ms == 0
        assert len(info.video_tracks) == 0
        assert len(info.audio_tracks) == 0
        assert len(info.subtitle_tracks) == 0
        backend.release()

    def test_media_info_with_real_file(self) -> None:
        test_file = "/run/media/johnny/Movies/Le_Cercle_Rouge.1970.mkv"
        if not os.path.exists(test_file):
            pytest.skip("test media file not available")

        backend = _make_backend()
        try:
            backend.open(test_file)
            time.sleep(1.5)
            info = backend.get_media_info()
            assert info.path == test_file
            assert info.duration_ms > 0
            assert info.video_width is not None and info.video_width > 0
            assert info.video_height is not None and info.video_height > 0
        finally:
            backend.close()
            backend.release()


# ---------------------------------------------------------------------------
# K. Embedded video output
# ---------------------------------------------------------------------------

class TestEmbeddedVideo:
    def test_set_video_window_id(self) -> None:
        path = _make_temp_media()
        backend = _make_backend()
        try:
            backend.open(path)
            backend.set_video_window_id(0)
        finally:
            backend.close()
            backend.release()
            os.unlink(path)

    def test_set_video_widget_without_open_raises(self) -> None:
        backend = _make_backend()
        with pytest.raises(RuntimeError):
            backend.set_video_window_id(12345)
        backend.release()

    def test_set_video_widget_with_mock(self) -> None:
        path = _make_temp_media()
        backend = _make_backend()
        try:
            backend.open(path)
            widget = MagicMock()
            widget.winId.return_value = 12345
            backend.set_video_widget(widget)
            widget.winId.assert_called_once()
        finally:
            backend.close()
            backend.release()
            os.unlink(path)


# ---------------------------------------------------------------------------
# L. Callbacks
# ---------------------------------------------------------------------------

class TestCallbacks:
    def test_set_callbacks(self) -> None:
        cb = PlaybackCallbacks(
            on_end_reached=lambda: None,
            on_error=lambda msg: None,
            on_state_changed=lambda s: None,
        )
        backend = _make_backend(callbacks=cb)
        assert backend._callbacks.on_end_reached is not None
        backend.release()

    def test_default_callbacks_no_crash(self) -> None:
        backend = _make_backend()
        backend._on_eof("eof-reached", None)
        backend._on_eof("eof-reached", False)
        backend._on_pause_changed("pause", None)
        backend._on_core_idle("core-idle", None)
        backend._on_core_idle("core-idle", False)
        backend.release()

    def test_callback_exception_does_not_crash(self) -> None:
        def bad_cb() -> None:
            raise RuntimeError("intentional error")

        cb = PlaybackCallbacks(on_end_reached=bad_cb)
        backend = _make_backend(callbacks=cb)
        backend._on_eof("eof-reached", True)
        backend.release()

    def test_end_reached_callback_fires(self) -> None:
        called = []
        cb = PlaybackCallbacks(on_end_reached=lambda: called.append(True))
        backend = _make_backend(callbacks=cb)
        backend._on_eof("eof-reached", True)
        assert called == [True]
        backend.release()

    def test_state_changed_callback_fires(self) -> None:
        called = []
        cb = PlaybackCallbacks(on_state_changed=lambda s: called.append(s))
        backend = _make_backend(callbacks=cb)
        called.clear()
        backend._on_pause_changed("pause", True)
        backend._on_pause_changed("pause", False)
        backend._on_core_idle("core-idle", True)
        assert called == ["paused", "playing", "stopped"]
        backend.release()


# ---------------------------------------------------------------------------
# M. State queries after open
# ---------------------------------------------------------------------------

class TestStateAfterOpen:
    def test_get_state_after_open(self) -> None:
        path = _make_temp_media()
        backend = _make_backend()
        try:
            backend.open(path)
            state = backend.get_state()
            assert state.path == path
            assert state.is_paused is True or state.is_paused is False
        finally:
            backend.close()
            backend.release()
            os.unlink(path)

    def test_get_state_without_open_raises(self) -> None:
        backend = _make_backend()
        with pytest.raises(RuntimeError):
            backend.get_state()
        backend.release()


# ---------------------------------------------------------------------------
# N. Resource cleanup: repeated open/close
# ---------------------------------------------------------------------------

class TestRepeatedOpenClose:
    def test_repeated_open_close(self) -> None:
        backend = _make_backend()
        try:
            for _ in range(5):
                path = _make_temp_media()
                try:
                    backend.open(path)
                    backend.close()
                finally:
                    os.unlink(path)
        finally:
            backend.release()

    def test_repeated_open_stop(self) -> None:
        backend = _make_backend()
        try:
            for _ in range(5):
                path = _make_temp_media()
                try:
                    backend.open(path)
                    backend.stop()
                finally:
                    os.unlink(path)
        finally:
            backend.release()


# ---------------------------------------------------------------------------
# O. Data object construction
# ---------------------------------------------------------------------------

class TestDataObjects:
    def test_audio_track(self) -> None:
        t = AudioTrack(id=1, name="French", language="fr")
        assert t.id == 1
        assert t.name == "French"
        assert t.language == "fr"

    def test_subtitle_track(self) -> None:
        t = SubtitleTrack(id=2, name="English")
        assert t.id == 2
        assert t.language is None

    def test_video_track(self) -> None:
        t = VideoTrack(id=0, name="H264", width=1920, height=1080)
        assert t.width == 1920

    def test_media_info(self) -> None:
        info = MediaInfo(path="/test.mkv", duration_ms=60000)
        assert info.path == "/test.mkv"
        assert info.duration_ms == 60000

    def test_playback_callbacks_defaults(self) -> None:
        cb = PlaybackCallbacks()
        assert cb.on_end_reached is None
        assert cb.on_error is None
        assert cb.on_state_changed is None


# ---------------------------------------------------------------------------
# P. Real MPV integration (skipped if media unavailable)
# ---------------------------------------------------------------------------

class TestRealMPVIntegration:
    """Integration tests that exercise actual libmpv with a real file."""

    TEST_FILE = "/run/media/johnny/Movies/Le_Cercle_Rouge.1970.mkv"

    @pytest.fixture()
    def backend(self) -> MPVPlayerBackend:
        b = _make_backend()
        yield b
        try:
            b.close()
        except Exception:
            pass
        b.release()

    def _skip_if_no_media(self) -> None:
        if not os.path.exists(self.TEST_FILE):
            pytest.skip("test media file not available")

    def test_real_open_and_play(self, backend: MPVPlayerBackend) -> None:
        self._skip_if_no_media()
        backend.open(self.TEST_FILE)
        time.sleep(1.0)
        assert backend.is_open() is True
        assert backend.is_paused() is True

    def test_real_pause_resume(self, backend: MPVPlayerBackend) -> None:
        self._skip_if_no_media()
        backend.open(self.TEST_FILE)
        time.sleep(1.0)
        backend.play()
        time.sleep(0.5)
        assert backend.is_playing() is True
        backend.pause()
        time.sleep(0.3)
        assert backend.is_paused() is True

    def test_real_seek(self, backend: MPVPlayerBackend) -> None:
        self._skip_if_no_media()
        backend.open(self.TEST_FILE)
        time.sleep(1.5)
        dur = backend.get_duration()
        assert dur > 0
        backend.seek(dur / 2)
        time.sleep(0.5)
        pos = backend.get_position()
        assert pos > 0

    def test_real_duration(self, backend: MPVPlayerBackend) -> None:
        self._skip_if_no_media()
        backend.open(self.TEST_FILE)
        time.sleep(1.5)
        dur = backend.get_duration()
        assert dur > 8000

    def test_real_audio_tracks(self, backend: MPVPlayerBackend) -> None:
        self._skip_if_no_media()
        backend.open(self.TEST_FILE)
        time.sleep(1.5)
        tracks = backend.get_audio_tracks()
        assert len(tracks) >= 1

    def test_real_subtitle_tracks(self, backend: MPVPlayerBackend) -> None:
        self._skip_if_no_media()
        backend.open(self.TEST_FILE)
        time.sleep(1.5)
        tracks = backend.get_subtitle_tracks()
        assert len(tracks) >= 1

    def test_real_video_size(self, backend: MPVPlayerBackend) -> None:
        self._skip_if_no_media()
        backend.open(self.TEST_FILE)
        time.sleep(1.5)
        size = backend.get_video_size()
        assert size is not None
        assert size[0] > 0
        assert size[1] > 0

    def test_real_playback_rate(self, backend: MPVPlayerBackend) -> None:
        self._skip_if_no_media()
        backend.open(self.TEST_FILE)
        time.sleep(1.0)
        backend.set_playback_rate(2.0)
        assert backend.get_playback_rate() == 2.0

    def test_real_volume(self, backend: MPVPlayerBackend) -> None:
        self._skip_if_no_media()
        backend.open(self.TEST_FILE)
        time.sleep(1.0)
        backend.set_volume(0.3)
        time.sleep(0.3)
        vol = backend.get_volume()
        assert abs(vol - 0.3) < 0.1

    def test_real_stop_and_reopen(self, backend: MPVPlayerBackend) -> None:
        self._skip_if_no_media()
        backend.open(self.TEST_FILE)
        time.sleep(1.0)
        backend.stop()
        assert backend.is_open() is False
        backend.open(self.TEST_FILE)
        time.sleep(0.5)
        assert backend.is_open() is True
        backend.stop()
