# SPDX-FileCopyrightText: Copyright (C) 2024-2025 沉默の金 <cmzj@cmzj.org>
# SPDX-License-Identifier: GPL-3.0-only
"""Small outline navigation icons with explicit normal and selected colors."""

from PySide6.QtGui import QIcon, QPixmap

_SHAPES = {
    "search": '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
    "match": '<path d="M9 4H4v16h16v-5M9 9h5M9 13h3m2 4 7-7m-5 0h5v5"/>',
    "open": '<path d="M3 8V5h7l2 3h9v3M3 8h8l2 3h9l-3 9H3Z"/>',
    "convert": '<path d="M4 7h16l-4-4m4 14H4l4 4M20 7l-4 4M4 17l4-4"/>',
    "about": '<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10v.5"/>',
    "settings": '<path d="M4 6h3m4 0h9M4 12h9m4 0h3M4 18h3m4 0h9"/>'
                '<circle cx="9" cy="6" r="2"/><circle cx="15" cy="12" r="2"/><circle cx="9" cy="18" r="2"/>',
}


def navigation_icon(name: str, normal: str, selected: str, disabled: str) -> QIcon:
    icon = QIcon()
    for mode, state, color in (
        (QIcon.Mode.Normal, QIcon.State.Off, normal),
        (QIcon.Mode.Normal, QIcon.State.On, selected),
        (QIcon.Mode.Active, QIcon.State.Off, normal),
        (QIcon.Mode.Active, QIcon.State.On, selected),
        (QIcon.Mode.Disabled, QIcon.State.Off, disabled),
        (QIcon.Mode.Disabled, QIcon.State.On, disabled),
    ):
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="36" height="36" viewBox="0 0 24 24" '
               f'fill="none" stroke="{color}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">'
               f'{_SHAPES[name]}</svg>')
        pixmap = QPixmap()
        pixmap.loadFromData(svg.encode(), "SVG")
        pixmap.setDevicePixelRatio(2)
        icon.addPixmap(pixmap, mode, state)
    return icon
