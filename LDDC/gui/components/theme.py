# SPDX-FileCopyrightText: Copyright (C) 2024-2025 沉默の金 <cmzj@cmzj.org>
# SPDX-License-Identifier: GPL-3.0-only
"""Shared styling for the application window, independent of generated Qt UI files."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontInfo, QFontMetrics, QGuiApplication
from PySide6.QtWidgets import QPushButton, QWidget

from LDDC.common.data.config import cfg
from LDDC.gui.components.navigation_icons import navigation_icon
from LDDC.gui.components.typography import ui_font, ui_font_size


def theme_colors() -> dict[str, str]:
    """Return the shared palette for the configured application color scheme."""
    scheme = cfg.get("color_scheme", "auto")
    dark = scheme == "dark" or (scheme == "auto" and QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark)
    return (
        dict(bg="#151c29", panel="#1e293b", sidebar="#192233", text="#e5edf8", muted="#9aaec8",
             border="#36455d", hover="#2b3a52", accent="#80b4ff", primary="#2563eb", pressed="#1d4ed8",
             selected="#293f61", nav_selected="#2563eb", disabled="#233047", disabled_text="#74859e", input="#192335")
        if dark else
        dict(bg="#f4f7fc", panel="#ffffff", sidebar="#eaf0f8", text="#20304a", muted="#64748b",
             border="#d9e2ef", hover="#eef4fd", accent="#2563eb", primary="#2563eb", pressed="#1d4ed8",
             selected="#dceafe", nav_selected="#2563eb", disabled="#f0f3f8", disabled_text="#98a5b8", input="#ffffff")
    )


def apply_theme(window: QWidget) -> None:
    window.setFont(ui_font())
    settings_title_font = ui_font()
    settings_title_font.setPixelSize(QFontInfo(settings_title_font).pixelSize() + 2)
    settings_title_height = QFontMetrics(settings_title_font).height()
    colors = theme_colors()
    assets = (Path(__file__).parent / "assets").as_posix()
    # Scope to this window: transparent desktop lyrics keep their own painting and palette.
    window.setStyleSheet("""
        QMainWindow#SidebarWindow, QWidget#centralwidget, QTabWidget::pane {
            background: %(bg)s; color: %(text)s; border: none;
        }
        QWidget { font-size: %(font_size)spt; color: %(text)s; }
        QWidget#sidebar { background: %(sidebar)s; border-right: 1px solid %(border)s; }
        QLabel { background: transparent; }
        QLabel[role="title"] { font-size: 26px; font-weight: 600; }
        QLabel[role="subtitle"], QLabel[role="muted"] { color: %(muted)s; }
        QLabel[role="section"] { font-size: 16px; font-weight: 600; }
        QWidget[role="card"] { background: %(panel)s; border: 1px solid %(border)s; border-radius: 12px; }
        QPushButton, QToolButton {
            background: %(panel)s; border: 1px solid %(border)s; border-radius: 7px;
            padding: 7px 14px; min-height: 20px; font-weight: 500;
        }
        QPushButton:hover, QToolButton:hover { background: %(hover)s; border-color: %(accent)s; }
        QPushButton:pressed, QToolButton:pressed { background: %(selected)s; }
        QPushButton[role="lyrics-order"]:checked {
            background: %(selected)s; color: %(accent)s; border-color: %(accent)s;
        }
        QPushButton:focus, QToolButton:focus { border: 1px solid %(accent)s; }
        QPushButton[role="primary"] { background: %(primary)s; color: white; border-color: %(primary)s; }
        QPushButton[role="primary"]:hover { background: %(pressed)s; border-color: %(pressed)s; }
        QPushButton[role="primary"]:pressed { background: #1e40af; }
        QPushButton:disabled, QToolButton:disabled, QPushButton[role="primary"]:disabled {
            background: %(disabled)s; color: %(disabled_text)s; border-color: %(border)s;
        }
        QPushButton[role="nav"] {
            background: transparent; color: %(muted)s; border: 1px solid transparent;
            border-radius: 6px; text-align: left; padding: 8px 10px; min-height: 20px;
            font-size: %(font_size)spt;
        }
        QPushButton[role="nav"]:hover {
            background: %(hover)s; color: %(text)s; border-color: transparent;
        }
        QPushButton[role="nav"]:checked {
            background: %(nav_selected)s; color: white; border-color: transparent;
        }
        QPushButton[role="nav"]:pressed { background: %(nav_selected)s; color: white; border-color: transparent; }
        QPushButton[role="nav"]:focus { border-color: %(border)s; }
        QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
            background: %(input)s; border: 1px solid %(border)s; border-radius: 7px;
            padding: 6px 10px; min-height: 20px; selection-background-color: %(primary)s;
            selection-color: white;
        }
        QLineEdit:hover, QComboBox:hover, QSpinBox:hover { border-color: %(muted)s; }
        QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border-color: %(accent)s; }
        QLineEdit:read-only { background: %(bg)s; color: %(muted)s; }
        QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled {
            background: %(disabled)s; color: %(disabled_text)s;
        }
        QComboBox { padding-right: 30px; }
        QGroupBox#groupBox_6 QComboBox { padding-left: 8px; padding-right: 24px; }
        QComboBox::drop-down { width: 26px; border: none; }
        QComboBox::down-arrow { image: url("%(assets)s/chevron-down.svg"); width: 12px; height: 12px; }
        QComboBox QAbstractItemView {
            background: %(panel)s; color: %(text)s; border: 1px solid %(border)s;
            selection-background-color: %(selected)s; selection-color: %(accent)s; padding: 4px;
        }
        QSpinBox { padding-right: 24px; }
        QSpinBox::up-button { subcontrol-origin: border; subcontrol-position: top right; width: 22px; border: none; }
        QSpinBox::down-button { subcontrol-origin: border; subcontrol-position: bottom right; width: 22px; border: none; }
        QSpinBox::up-arrow { image: url("%(assets)s/chevron-up.svg"); width: 10px; height: 10px; }
        QSpinBox::down-arrow { image: url("%(assets)s/chevron-down.svg"); width: 10px; height: 10px; }
        QCheckBox, QRadioButton { spacing: 8px; padding: 5px 2px; background: transparent; }
        QCheckBox:hover, QRadioButton:hover { color: %(accent)s; }
        QCheckBox:disabled, QRadioButton:disabled { color: %(disabled_text)s; }
        QCheckBox::indicator {
            width: 17px; height: 17px; border: 1px solid %(muted)s; border-radius: 5px; background: %(input)s;
        }
        QCheckBox::indicator:unchecked:hover { border-color: %(accent)s; background: %(hover)s; }
        QCheckBox::indicator:checked {
            background: %(primary)s; border-color: %(primary)s; image: url("%(assets)s/check.svg");
        }
        QCheckBox::indicator:checked:hover { background: %(pressed)s; border-color: %(pressed)s; }
        QCheckBox::indicator:indeterminate {
            background: %(primary)s; border-color: %(primary)s; image: url("%(assets)s/minus.svg");
        }
        QCheckBox::indicator:disabled { background: %(disabled)s; border-color: %(border)s; }
        QCheckBox::indicator:checked:disabled { background: %(disabled_text)s; }
        QCheckBox::indicator:focus { border-color: %(accent)s; }
        QRadioButton::indicator { width: 16px; height: 16px; border-radius: 9px; border: 1px solid %(muted)s; background: %(input)s; }
        QRadioButton::indicator:checked { background: %(primary)s; border: 4px solid %(selected)s; width: 10px; height: 10px; }
        QTableWidget, QListWidget, QPlainTextEdit, QTextEdit {
            background: %(panel)s; alternate-background-color: %(bg)s; border: 1px solid %(border)s;
            border-radius: 8px; selection-background-color: %(selected)s; selection-color: %(text)s;
        }
        QPlainTextEdit, QTextEdit { padding: 12px; }
        QWidget#localMatchResultsFrame {
            background: %(panel)s; border: 1px solid %(border)s; border-radius: 8px;
        }
        QWidget#localMatchResultsFrame QTableWidget#songs_table { border: none; border-radius: 0; }
        QTableWidget::item, QListWidget::item { padding: 7px 8px; border: none; }
        QListWidget[role="checks"]::item { padding: 0px; }
        QListWidget#source_listWidget, QListWidget#multi_search_source_list { padding-left: 4px; }
        QTableWidget::item:hover, QListWidget::item:hover { background: %(hover)s; }
        QTableWidget::item:selected, QListWidget::item:selected { background: %(selected)s; color: %(accent)s; }
        QListWidget[role="checks"], QListWidget[role="order"] {
            selection-background-color: transparent; outline: none;
        }
        QListWidget[role="checks"]::item:hover, QListWidget[role="checks"]::item:selected {
            background: transparent; color: %(text)s;
        }
        QListWidget[role="order"]::item { border-bottom: 2px solid transparent; }
        QListWidget[role="order"]::item:hover { background: transparent; color: %(accent)s; }
        QListWidget[role="order"]::item:selected {
            background: transparent; color: %(accent)s; border-bottom: 2px solid %(accent)s;
        }
        QHeaderView::section {
            background: %(bg)s; color: %(muted)s; padding: 9px 8px; border: none;
            border-bottom: 1px solid %(border)s; font-weight: 500;
        }
        QHeaderView#localMatchRowHeader { background: %(panel)s; }
        QHeaderView#localMatchRowHeader::section {
            background: %(panel)s; padding: 0 8px; border: none; font-weight: normal;
        }
        QHeaderView#localMatchRowHeader::section:checked {
            background: %(selected)s; color: %(accent)s;
        }
        QTableCornerButton::section { background: %(bg)s; border: none; }
        QTableWidget#songs_table QTableCornerButton::section {
            border-bottom: 1px solid %(border)s;
        }
        QSplitter::handle { background: transparent; }
        QSplitter::handle:hover { background: %(border)s; border-radius: 3px; }
        QGroupBox { background: %(panel)s; border: 1px solid %(border)s; border-radius: 9px; margin-top: 16px; padding: 16px 12px 12px; }
        QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; color: %(muted)s; }
        QWidget#settings QGroupBox {
            font-size: %(settings_title_size)spx; margin-top: %(settings_title_margin)spx;
        }
        QWidget#settings QGroupBox::title {
            subcontrol-position: top left; left: 0; padding: 0;
        }
        QScrollArea { border: none; background: %(bg)s; }
        QWidget#scrollAreaWidgetContents, QWidget#scrollAreaWidgetContents_2 { background: %(bg)s; }
        QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
        QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
        QScrollBar::handle { background: %(border)s; border-radius: 4px; min-height: 28px; min-width: 28px; }
        QScrollBar::handle:hover { background: %(muted)s; }
        QScrollBar::add-line, QScrollBar::sub-line { width: 0px; height: 0px; }
        QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
        QProgressBar { border: none; border-radius: 5px; background: %(disabled)s; text-align: center; min-height: 10px; }
        QProgressBar[complete="true"] { color: white; }
        QProgressBar::chunk { background: %(primary)s; border-radius: 5px; }
        QMenu { background: %(panel)s; border: 1px solid %(border)s; padding: 5px; }
        QMenu::item { padding: 7px 22px; border-radius: 4px; }
        QMenu::item:selected { background: %(selected)s; }
        QToolTip { color: %(text)s; background: %(panel)s; border: 1px solid %(border)s; padding: 6px; }
    """ % {**colors, "assets": assets, "font_size": ui_font_size(),
           "settings_title_size": settings_title_font.pixelSize(), "settings_title_margin": settings_title_height + 2})
    sidebar = window.findChild(QWidget, "sidebar")
    if sidebar is not None:
        buttons = [button for button in sidebar.findChildren(QPushButton) if button.property("role") == "nav"]
        for button in buttons:
            if name := button.property("navIcon"):
                button.setIcon(navigation_icon(name, colors["muted"], "#ffffff", colors["disabled_text"]))
            button.ensurePolished()
        # Keep the compact width unless a larger font or translation needs more room.
        margins = sidebar.layout().contentsMargins()
        content_width = max((button.sizeHint().width() for button in buttons), default=0)
        sidebar.setFixedWidth(max(sidebar.property("preferredWidth") or 140, content_width + margins.left() + margins.right()))


def primary_button(button: QPushButton) -> None:
    button.setProperty("role", "primary")
