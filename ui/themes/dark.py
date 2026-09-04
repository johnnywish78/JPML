"""Theme token sets. Dark is the default JPML identity."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ThemeTokens:
    name: str
    background: str
    surface: str
    elevated: str
    card: str
    card_hover: str
    text_primary: str
    text_secondary: str
    text_muted: str
    text_on_accent: str
    accent: str
    accent_hover: str
    accent_pressed: str
    border: str
    border_strong: str
    overlay: str
    hero_gradient_top: str
    hero_gradient_bottom: str
    skeleton: str
    skeleton_shine: str
    shadow_rgb: str  # "0,0,0" used with alpha in QSS
    progress_track: str
    scrollbar: str
    scrollbar_hover: str
    input_field: str
    menu_background: str
    menu_hover: str
    badge_background: str
    success: str
    warning: str
    danger: str


DARK = ThemeTokens(
    name="dark",
    background="#08090C",
    surface="#0E1015",
    elevated="#151820",
    card="#191C24",
    card_hover="#20242E",
    text_primary="#F5F5F7",
    text_secondary="#A7ABB5",
    text_muted="#6F7480",
    text_on_accent="#FFFFFF",
    accent="#D7263D",
    accent_hover="#E63950",
    accent_pressed="#B71E33",
    border="#232733",
    border_strong="#39404E",
    overlay="rgba(8, 9, 12, 0.55)",
    hero_gradient_top="rgba(8, 9, 12, 0.25)",
    hero_gradient_bottom="#08090C",
    skeleton="#1A1D26",
    skeleton_shine="#232733",
    shadow_rgb="0, 0, 0",
    progress_track="#2A2F3B",
    scrollbar="#2A2F3B",
    scrollbar_hover="#39404E",
    input_field="#12141B",
    menu_background="#151820",
    menu_hover="#20242E",
    badge_background="#20242E",
    success="#3DBE7B",
    warning="#E5A83B",
    danger="#D7263D",
)
