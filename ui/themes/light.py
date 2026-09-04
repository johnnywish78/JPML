"""Light theme tokens — same components, same layout."""
from __future__ import annotations

from ui.themes.dark import ThemeTokens


LIGHT = ThemeTokens(
    name="light",
    background="#F4F4F6",
    surface="#FFFFFF",
    elevated="#FFFFFF",
    card="#FFFFFF",
    card_hover="#FFFFFF",
    text_primary="#17181C",
    text_secondary="#565B66",
    text_muted="#8B909C",
    text_on_accent="#FFFFFF",
    accent="#C81E34",
    accent_hover="#D7263D",
    accent_pressed="#A5182A",
    border="#E1E3E8",
    border_strong="#C6CAD2",
    overlay="rgba(244, 244, 246, 0.6)",
    hero_gradient_top="rgba(255, 255, 255, 0.30)",
    hero_gradient_bottom="#F4F4F6",
    skeleton="#E8E9ED",
    skeleton_shine="#F3F4F6",
    shadow_rgb="60, 64, 74",
    progress_track="#DDDFE5",
    scrollbar="#C9CCD4",
    scrollbar_hover="#AEB2BC",
    input_field="#F1F2F5",
    menu_background="#FFFFFF",
    menu_hover="#F1F2F5",
    badge_background="#EDEEF2",
    success="#248A55",
    warning="#A9741C",
    danger="#C81E34",
)
