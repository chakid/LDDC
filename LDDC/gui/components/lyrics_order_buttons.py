# SPDX-FileCopyrightText: Copyright (C) 2024-2025 沉默の金 <cmzj@cmzj.org>
# SPDX-License-Identifier: GPL-3.0-only
"""Select lyric languages in click order without a scrollable item view."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from LDDC.common.translator import language_changed


class LyricsOrderButtons(QWidget):
    order_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._order: list[str] = []
        self.buttons: dict[str, QPushButton] = {}
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        for language in ("roma", "orig", "ts"):
            button = QPushButton(self)
            button.setCheckable(True)
            button.setProperty("role", "lyrics-order")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda checked, lang=language: self._toggle(lang, checked))
            layout.addWidget(button)
            self.buttons[language] = button
        layout.addStretch(1)
        language_changed.connect(self._refresh)
        self._refresh()

    def set_order(self, order: list[str]) -> None:
        self._order = list(dict.fromkeys(lang for lang in order if lang in self.buttons))
        self._refresh()

    def get_order(self) -> list[str]:
        return self._order.copy()

    def _toggle(self, language: str, checked: bool) -> None:
        if checked:
            self._order.append(language)
        else:
            self._order.remove(language)
        self._refresh()
        self.order_changed.emit()

    def _refresh(self) -> None:
        names = {"roma": self.tr("罗马音"), "orig": self.tr("原文"), "ts": self.tr("译文")}
        for language, button in self.buttons.items():
            selected = language in self._order
            button.setChecked(selected)
            number = f"{self._order.index(language) + 1} · " if selected else ""
            button.setText(number + names[language])
            button.setToolTip(self.tr("按选中先后排列歌词；取消后重新选中可调整顺序。"))
