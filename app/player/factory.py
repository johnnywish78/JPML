from __future__ import annotations

from app.player import PlaybackCallbacks, PlayerBackend

BACKEND_VLC = "vlc"
BACKEND_MPV = "mpv"
BACKEND_MOCK = "mock"

SUPPORTED_BACKENDS = (BACKEND_VLC, BACKEND_MPV, BACKEND_MOCK)


def create_backend(
    name: str = BACKEND_VLC,
    *,
    callbacks: PlaybackCallbacks | None = None,
    **kwargs: object,
) -> PlayerBackend:
    """Factory function to create a player backend by name.

    Supported backend identifiers:
      - ``"vlc"``  — VLCPlayerBackend (default)
      - ``"mpv"``  — MPVPlayerBackend
      - ``"mock"`` — MockPlayerBackend (test-only)

    Parameters
    ----------
    name:
        Backend identifier.
    callbacks:
        Optional :class:`PlaybackCallbacks` instance.
    **kwargs:
        Extra keyword arguments forwarded to the backend constructor
        (e.g. ``vlc_args``, ``mpv_args``).

    Raises
    ------
    ValueError
        If *name* is not a recognised backend identifier.
    """
    name = name.strip().lower()

    if name == BACKEND_VLC:
        from app.player.vlc_backend import VLCPlayerBackend

        vlc_args = kwargs.get("vlc_args")
        return VLCPlayerBackend(
            vlc_args=list(vlc_args) if vlc_args is not None else None,
            callbacks=callbacks,
        )

    if name == BACKEND_MPV:
        from app.player.mpv_backend import MPVPlayerBackend

        mpv_args = kwargs.get("mpv_args")
        return MPVPlayerBackend(
            mpv_args=list(mpv_args) if mpv_args is not None else None,
            callbacks=callbacks,
        )

    if name == BACKEND_MOCK:
        from app.player import MockPlayerBackend

        return MockPlayerBackend()

    raise ValueError(
        f"Unknown backend {name!r}. Supported: {', '.join(SUPPORTED_BACKENDS)}"
    )
