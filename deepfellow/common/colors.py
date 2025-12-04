"""Definition of the colors."""

import enum
import os
import sys
from dataclasses import dataclass


class COLORTERM(enum.Enum):
    truecolor = "truecolor"
    limited = "limited"


def get_color_support() -> COLORTERM:
    """Detects terminal color support.

    Returns:
        COLORTERM.truecolor: 24-bit RGB colors supported
        COLORTERM.limited: 256-color or less
    """
    if not sys.stdout.isatty():
        return COLORTERM.limited

    # Check for truecolor support
    colorterm = os.environ.get("COLORTERM", "")
    if colorterm in ("truecolor", "24bit"):
        return COLORTERM.truecolor

    # Some terminals support truecolor but don't set COLORTERM
    term = os.environ.get("TERM", "")
    if "truecolor" in term or "24bit" in term:
        return COLORTERM.truecolor

    # Everything else is limited (256-color, 16-color, or 8-color)
    return COLORTERM.limited


@dataclass(frozen=True)
class Colors:
    very_light_blue: str
    light_blue: str
    lighter_blue: str
    light_medium_blue: str
    medium_light_blue: str
    medium_blue: str
    blue: str
    darker_blue: str
    dark_blue: str
    very_dark_blue: str
    darkest_blue: str
    reset: str = "\033[0m"


TRUE_COLORS = Colors(
    very_light_blue="\033[38;2;238;245;255m",
    light_blue="\033[38;2;217;231;255m",
    lighter_blue="\033[38;2;188;213;255m",
    light_medium_blue="\033[38;2;142;187;255m",
    medium_light_blue="\033[38;2;89;150;255m",
    medium_blue="\033[38;2;47;108;255m",
    blue="\033[38;2;27;76;245m",
    darker_blue="\033[38;2;20;56;225m",
    dark_blue="\033[38;2;23;46;182m",
    very_dark_blue="\033[38;2;25;45;143m",
    darkest_blue="\033[38;2;20;29;87m",
)

LIMITED_COLORS = Colors(
    very_light_blue="\033[38;5;189m",
    light_blue="\033[38;5;153m",
    lighter_blue="\033[38;5;117m",
    light_medium_blue="\033[38;5;111m",
    medium_light_blue="\033[38;5;75m",
    medium_blue="\033[38;5;69m",
    blue="\033[38;5;63m",
    darker_blue="\033[38;5;62m",
    dark_blue="\033[38;5;61m",
    very_dark_blue="\033[38;5;60m",
    darkest_blue="\033[38;5;17m",
)

# Reset code
RESET = "\033[0m"

# Usage
color_support = get_color_support()
COLORS = TRUE_COLORS if color_support == COLORTERM.truecolor else LIMITED_COLORS
