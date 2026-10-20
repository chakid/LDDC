# SPDX-FileCopyrightText: Copyright (C) 2024-2025 沉默の金 <cmzj@cmzj.org>
# SPDX-License-Identifier: GPL-3.0-only
"""Shared UI typography, using installed outline fonts and Qt's DPI scaling."""

import sys

from PySide6.QtGui import QFont, QFontDatabase

from LDDC.common.data.config import cfg


def ui_font_size() -> int:
    """Return a supported point size, including for older configuration files."""
    value = cfg.get("ui_font_size", 10)
    return value if type(value) is int and 9 <= value <= 12 else 10


def ui_font() -> QFont:
    """Return a readable UI font with a platform-appropriate CJK fallback."""
    font = QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont)
    candidates = (
        ("Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", "Noto Sans CJK SC", "Noto Sans SC")
        if sys.platform == "win32" else
        (font.family(), "PingFang SC", "Noto Sans CJK SC", "Noto Sans SC", "WenQuanYi Micro Hei")
    )
    available = set(QFontDatabase.families())
    families = list(dict.fromkeys(family for family in (*candidates, font.family()) if family in available))
    if families:
        font.setFamilies(families)
    font.setPointSize(ui_font_size())
    font.setWeight(QFont.Weight.Normal)
    # Prefer scalable glyphs over embedded bitmap strikes at small CJK sizes.
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias | QFont.StyleStrategy.PreferOutline)
    font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    return font
