# SPDX-FileCopyrightText: Copyright (C) 2024-2025 沉默の金 <cmzj@cmzj.org>
# SPDX-License-Identifier: GPL-3.0-only
"""Application-themed message boxes, retaining Qt's standard button semantics."""

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPen, QPixmap, QShowEvent
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QMessageBox, QScrollArea, QToolButton, QWidget

from LDDC.gui.components.theme import theme_colors
from LDDC.gui.components.typography import ui_font, ui_font_size


class MessageDialog(QMessageBox):
    """A rounded, frameless message card with accessible native Qt buttons."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._set_card_window_flags()
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        font = ui_font()
        font.setPointSize(max(12, ui_font_size() + 2))
        self.setFont(font)
        self._prepared = False
        self._colors = theme_colors()

    def _set_card_window_flags(self) -> None:
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint)

    def setWindowModality(self, modality: Qt.WindowModality) -> None:
        super().setWindowModality(modality)
        # QMessageBox switches to Sheet and restores native decorations for WindowModal.
        # Restore the card flags before the native window is created, so alpha works on Windows.
        self._set_card_window_flags()

    def _status_pixmap(self, colors: dict[str, str]) -> QPixmap:
        kind = self.icon()
        warning = kind == QMessageBox.Icon.Warning
        critical = kind == QMessageBox.Icon.Critical
        color = QColor("#d97706" if warning else "#dc4c64" if critical else colors["accent"])
        ratio = self.devicePixelRatioF()
        pixmap = QPixmap(round(44 * ratio), round(44 * ratio))
        pixmap.setDevicePixelRatio(ratio)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        background = QColor(color)
        background.setAlpha(24)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(background)
        painter.drawRoundedRect(QRectF(0, 0, 44, 44), 13, 13)
        painter.setPen(QPen(color, 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        if warning:
            painter.drawLine(QPointF(22, 12), QPointF(22, 24))
            painter.drawPoint(QPointF(22, 31))
        elif critical:
            painter.drawLine(QPointF(16, 16), QPointF(28, 28))
            painter.drawLine(QPointF(28, 16), QPointF(16, 28))
        else:
            font = ui_font()
            font.setPixelSize(26)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(QRectF(0, 0, 44, 44), Qt.AlignmentFlag.AlignCenter,
                             "?" if kind == QMessageBox.Icon.Question else "i")
        painter.end()
        return pixmap

    def _prepare(self) -> None:
        colors = self._colors
        self.setIconPixmap(self._status_pixmap(colors))
        self.setStyleSheet("""
            QMessageBox { background: transparent; }
            QLabel { background: transparent; color: %(text)s; font-size: %(size)spt; }
            QLabel#messageTitle { font-size: %(title_size)spt; font-weight: 600; }
            QLabel#qt_msgbox_label { color: %(text)s; }
            QScrollArea, QScrollArea > QWidget, QScrollArea > QWidget > QWidget {
                background: transparent; border: none;
            }
            QPushButton {
                background: %(panel)s; color: %(text)s; border: 1px solid %(border)s;
                border-radius: 8px; padding: 6px 16px; min-width: 48px; min-height: 20px;
                font-size: %(size)spt; font-weight: 500;
            }
            QPushButton:hover { background: %(hover)s; border-color: %(accent)s; }
            QPushButton:pressed { background: %(selected)s; }
            QPushButton:focus { border-color: %(accent)s; }
            QPushButton[role="primary"] { background: %(primary)s; color: white; border-color: %(primary)s; }
            QPushButton[role="primary"]:hover { background: %(pressed)s; border-color: %(pressed)s; }
            QPushButton[role="primary"]:pressed { background: #1e40af; }
            QPushButton[role="primary"]:focus { border: 2px solid %(accent)s; padding: 5px 15px; }
            QToolButton#messageClose {
                background: %(bg)s; color: %(text)s; border: 1px solid %(border)s; border-radius: 8px;
                padding: 0; min-width: 30px; min-height: 30px; font-size: 22px; font-weight: 600;
            }
            QToolButton#messageClose:hover, QToolButton#messageClose:focus {
                background: rgba(220, 76, 100, 24); color: #dc4c64; border-color: #dc4c64;
            }
            QToolButton#messageClose:pressed { background: rgba(220, 76, 100, 48); }
            QScrollBar:vertical { background: transparent; width: 8px; }
            QScrollBar::handle:vertical { background: %(border)s; border-radius: 4px; min-height: 24px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
        """ % {**colors, "size": self.font().pointSize(), "title_size": self.font().pointSize() + 2})

        grid = self.layout()
        if not isinstance(grid, QGridLayout):
            return
        # Keep QMessageBox's button box and connections; make room for an in-card title bar.
        items = []
        while grid.count():
            position = grid.getItemPosition(0)
            items.append((grid.takeAt(0), position))
        for item, (row, column, rows, columns) in items:
            grid.addItem(item, row + 1, column, rows, columns)
        grid.setContentsMargins(32, 26, 32, 28)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        title = QLabel(self.windowTitle(), self)
        title.setObjectName("messageTitle")
        title.setTextFormat(Qt.TextFormat.PlainText)
        title.setWordWrap(True)
        header.addWidget(title, 1)
        close = QToolButton(self)
        close.setObjectName("messageClose")
        close.setText("×")
        close.setAccessibleName(self.tr("关闭"))
        close.setToolTip(close.accessibleName())
        close.setFixedSize(32, 32)
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.clicked.connect(self._dismiss)
        header.addWidget(close, 0, Qt.AlignmentFlag.AlignTop)
        grid.addLayout(header, 0, 0, 1, grid.columnCount())

        screen = self.screen().availableGeometry()
        content_width = max((self.fontMetrics().horizontalAdvance(line) for line in self.text().splitlines()), default=0)
        width = min(max(210, content_width), 400, max(160, screen.width() - 160))
        title.setMaximumWidth(width + 60)
        icon = self.findChild(QLabel, "qt_msgboxex_icon_label")
        if icon is not None:
            grid.setAlignment(icon, Qt.AlignmentFlag.AlignTop)
        label = self.findChild(QLabel, "qt_msgbox_label")
        if label is not None:
            label.setWordWrap(True)
            label.setFixedWidth(width)
            label.setMinimumHeight(44)
            label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            max_height = max(80, min(320, screen.height() - 240))
            height = max(44, label.heightForWidth(width))
            if height > max_height:
                position = grid.getItemPosition(grid.indexOf(label))
                grid.removeWidget(label)
                area = QScrollArea(self)
                area.setWidget(label)
                area.setWidgetResizable(True)
                area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                area.setFixedSize(width + 12, max_height)
                label.setMinimumHeight(height)
                label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
                grid.addWidget(area, *position)

        for button in self.buttons():
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            if button == self.defaultButton():
                button.setProperty("role", "primary")
                button.style().unpolish(button)
                button.style().polish(button)
        self.adjustSize()

    def _dismiss(self) -> None:
        """Use the safe escape action when the in-card close button is clicked."""
        button = self.escapeButton()
        if button is None:
            button = self.button(QMessageBox.StandardButton.Cancel) or self.button(QMessageBox.StandardButton.No)
        if button is None and len(self.buttons()) == 1:
            button = self.buttons()[0]
        if button is not None:
            button.click()
        else:
            self.close()

    def showEvent(self, event: QShowEvent) -> None:
        if not self._prepared:
            self._prepare()
            self._prepared = True
        super().showEvent(event)
        QTimer.singleShot(0, self, self._finish_layout)

    def _finish_layout(self) -> None:
        # QMessageBox applies its native fixed size after showEvent; include our header afterward.
        self.setFixedSize(self.layout().sizeHint())
        self.layout().activate()
        # Center the complete card over its owning window (or screen for standalone notices).
        parent = self.parentWidget()
        bounds = parent.window().frameGeometry() if parent else self.screen().availableGeometry()
        available = self.screen().availableGeometry()
        position = bounds.center() - self.rect().center()
        position.setX(max(available.left(), min(position.x(), available.right() - self.width() + 1)))
        position.setY(max(available.top(), min(position.y(), available.bottom() - self.height() + 1)))
        self.move(position)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: ARG002
        colors = self._colors
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        # A restrained soft shadow fits both palettes, without a native Windows frame.
        for spread in range(12, 0, -1):
            painter.setBrush(QColor(15, 23, 42, 2 if spread > 5 else 4))
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(14 - spread, 16 - spread, spread - 14, spread - 12),
                                    16 + spread, 16 + spread)
        painter.setPen(QPen(QColor(colors["border"]), 1))
        painter.setBrush(QColor(colors["panel"]))
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(14, 12, -14, -16), 16, 16)
        painter.end()
