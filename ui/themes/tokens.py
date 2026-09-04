"""Centralized JPML design tokens.

All visual values used across the UI come from here. No raw visual
constants belong in screens or components.
"""
from __future__ import annotations

from dataclasses import dataclass


# -- spacing ------------------------------------------------------------------

class Spacing:
    XS = 4
    S = 8
    M = 12
    L = 16
    XL = 20
    XXL = 24
    XXL2 = 32
    XXL3 = 40
    XXL4 = 48
    XXL5 = 64


# -- radii --------------------------------------------------------------------

class Radius:
    CONTROL = 6
    BUTTON = 8
    CARD = 10
    SURFACE = 12
    HERO = 14


# -- motion (ms) ----------------------------------------------------------------

class Motion:
    MICRO = 150
    STANDARD = 200
    PAGE = 300
    CINEMATIC = 450


# -- typography -----------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Type:
    family: str
    hero: int
    page: int
    section: int
    card: int
    metadata: int
    navigation: int


class Typography:
    HERO_PX = 48
    PAGE_PX = 32
    SECTION_PX = 22
    CARD_PX = 15
    METADATA_PX = 13
    NAVIGATION_PX = 14

    WEIGHT_REGULAR = 400
    WEIGHT_MEDIUM = 500
    WEIGHT_SEMIBOLD = 600
    WEIGHT_BOLD = 700


# -- layout ---------------------------------------------------------------------

class Layout:
    SIDEBAR_WIDTH = 260
    CONTENT_PAD_H = 32
    CONTENT_PAD_TOP = 28
    CONTENT_PAD_BOTTOM = 40
    MAX_CONTENT_WIDTH = 1800
    HERO_MIN_HEIGHT = 500
    HERO_MAX_HEIGHT = 560
    POSTER_ASPECT_NUM = 2
    POSTER_ASPECT_DEN = 3
    SQUARE_ASPECT = 1
    BACKDROP_ASPECT_NUM = 16
    BACKDROP_ASPECT_DEN = 9
    CARD_MIN_WIDTH = 150
    CARD_GAP = 16
