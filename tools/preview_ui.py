# SPDX-FileCopyrightText: Copyright (C) 2024-2025 沉默の金 <cmzj@cmzj.org>
# SPDX-License-Identifier: GPL-3.0-only
"""Render the application offline with isolated data, and check layout/keyboard interactions.

Run from the repository root: python tools/preview_ui.py
Screenshots and temporary app data go to tests/artifacts/ui-preview.
"""

import os
import sys
from pathlib import Path
from types import ModuleType

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUTPUT = ROOT / "tests" / "artifacts" / "ui-preview"
OUTPUT.mkdir(parents=True, exist_ok=True)

# Avoid opening the user's database or changing their settings during visual QA.
paths = ModuleType("LDDC.common.paths")
for name in ("config_dir", "data_dir", "cache_dir", "log_dir", "auto_save_dir", "default_save_lyrics_dir"):
    directory = OUTPUT / "data" / name
    directory.mkdir(parents=True, exist_ok=True)
    setattr(paths, name, directory)
paths.command_line = None
sys.modules[paths.__name__] = paths

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QFontDatabase, QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QCheckBox, QComboBox, QPushButton, QTableWidgetItem

app = QApplication(sys.argv)
# The offscreen backend does not enumerate all Windows system fonts.
if app.platformName() == "offscreen":
    for font_name in ("msyh.ttc", "msyhbd.ttc"):
        font_path = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / font_name
        if font_path.exists():
            QFontDatabase.addApplicationFont(str(font_path))

from LDDC.gui.components.typography import ui_font

app.setFont(ui_font())

from LDDC.common.data.config import cfg
cfg.reset()

from LDDC.common.models import Lyrics, LyricsData, LyricsLine, LyricsType, LyricsWord, SongInfo, Source
from LDDC.gui.components.theme import apply_theme
from LDDC.gui.view.main_window import main_window
from LDDC.res import resource_rc

resource_rc.qInitResources()
cfg["auto_check_update"] = False
main_window.show()
app.processEvents()
view = main_window.search_widget
view.save_path_lineEdit.setText("D:\\Music\\Lyrics")


def snapshot(name: str) -> None:
    app.processEvents()
    assert main_window.grab().save(str(OUTPUT / f"{name}.png"))


cfg["color_scheme"] = "light"
app.styleHints().setColorScheme(Qt.ColorScheme.Light)
apply_theme(main_window)
snapshot("search-light-empty")

# Exercise the real preview/conversion path without calling music services.
lyrics = Lyrics(SongInfo(Source.Local, title="晨间信号", artist="LDDC 示例", album="界面预览", duration=240000))
lyrics["orig"] = LyricsData([
    LyricsLine(0, 4000, [LyricsWord(0, 2000, "把旋律装进清晨的口袋"), LyricsWord(2000, 4000, " 让每一秒都有色彩")]),
    LyricsLine(5000, 9000, [LyricsWord(5000, 9000, "这是一段用于检查排版的原创示例文字")]),
])
lyrics.types["orig"] = LyricsType.VERBATIM
view.set_lyrics(lyrics)
assert "把旋律装进清晨的口袋" in view.preview_plainTextEdit.toPlainText()
checkbox = view.original_checkBox
checkbox.setFocus()
QTest.keyClick(checkbox, Qt.Key.Key_Space)
assert not checkbox.isChecked()
QTest.keyClick(checkbox, Qt.Key.Key_Space)
assert checkbox.isChecked()
view.offset_spinBox.setValue(100)
assert "[00:00.100]" in view.preview_plainTextEdit.toPlainText()
view.results_tableWidget.setColumnCount(4)
view.results_tableWidget.setHorizontalHeaderLabels(["歌曲", "歌手", "专辑", "来源"])
view.results_tableWidget.setRowCount(3)
for row, title in enumerate(("晨间信号", "晨间信号（Live）", "晨间信号 · 钢琴版")):
    for column, text in enumerate((title, "LDDC 示例", "界面预览", "本地示例")):
        view.results_tableWidget.setItem(row, column, QTableWidgetItem(text))
view.results_tableWidget.set_proportions([0.35, 0.2, 0.25, 0.2])
view.results_tableWidget.selectRow(0)
snapshot("search-light-content")

for width, height in ((1000, 680), (1440, 900)):
    main_window.resize(width, height)
    app.processEvents()
    for button in (view.save_preview_lyric_pushButton, view.save_to_tag_pushButton, view.save_list_lyrics_pushButton):
        assert button.height() < 60, (button.text(), button.size())
        assert button.width() >= button.sizeHint().width(), (button.text(), button.size(), button.sizeHint())
    assert view.search_keyword_lineEdit.width() > 200
    snapshot(f"search-light-{width}")

main_window.resize(1180, 780)
for index, name in enumerate(("search", "local-match", "open-lyrics", "batch-convert", "about", "settings")):
    main_window.set_current_widget(index)
    snapshot(f"{name}-light")
    assert main_window.Widgets.currentIndex() == index

main_window.resize(1000, 680)
app.processEvents()
assert main_window.settings_widget.scrollArea.horizontalScrollBar().maximum() == 0
main_window.settings_widget.scrollArea.ensureWidgetVisible(main_window.settings_widget.groupBox_3)
snapshot("settings-desktop-light-1000")
main_window.settings_widget.scrollArea.verticalScrollBar().setValue(0)
main_window.resize(1180, 780)

cfg["color_scheme"] = "dark"
app.styleHints().setColorScheme(Qt.ColorScheme.Dark)
apply_theme(main_window)
main_window.set_current_widget(0)
snapshot("search-dark")
main_window.set_current_widget(5)
snapshot("settings-dark")

# Keyboard focus, disabled, selected and unselected checkbox appearances.
state_panel = main_window.settings_widget
for index, checkbox in enumerate(state_panel.findChildren(QCheckBox)[:4]):
    checkbox.setChecked(index % 2 == 0)
    checkbox.setEnabled(index < 2)
snapshot("settings-dark-checkbox-states")

# Check the actual settings control, including persisted color names, not just a stylesheet call.
settings = main_window.settings_widget
settings.color_scheme_comboBox.setCurrentIndex(1)
settings.apply_button.click()
assert cfg["color_scheme"] == "light"
assert "#f4f7fc" in main_window.styleSheet()
settings.color_scheme_comboBox.setCurrentIndex(2)
settings.apply_button.click()
assert cfg["color_scheme"] == "dark"
assert "#151c29" in main_window.styleSheet()
settings.color_scheme_comboBox.setCurrentIndex(0)
settings.apply_button.click()
assert cfg["color_scheme"] == "auto"

# Review the subtle selection treatment for settings checklists and drag ordering.
settings.multi_search_source_list.setCurrentRow(1)
settings.lyrics_order_buttons.buttons["ts"].setFocus()
settings.scrollArea.ensureWidgetVisible(settings.multi_search_source_list)
for scheme in ("light", "dark"):
    cfg["color_scheme"] = scheme
    apply_theme(main_window)
    snapshot(f"settings-selection-{scheme}")
cfg["color_scheme"] = "auto"
apply_theme(main_window)

# The UI size applies only after confirmation, survives reload, and fits the smallest window.
from LDDC.common.data.config import Config

assert cfg["ui_font_size"] == 10
main_window.resize(1000, 680)
for size in (9, 10, 11, 12):
    settings.ui_font_size_comboBox.setCurrentIndex(settings.ui_font_size_comboBox.findData(size))
    settings.apply_button.click()
    app.processEvents()
    assert cfg["ui_font_size"] == size
    assert Config()["ui_font_size"] == size
    assert view.search_keyword_lineEdit.font().pointSizeF() == size
    assert main_window.width() == 1000
    settings.scrollArea.ensureWidgetVisible(settings.ui_font_size_comboBox)
    snapshot(f"settings-font-size-{size}")
    assert settings.scrollArea.horizontalScrollBar().maximum() == 0, (size, settings.scrollArea.horizontalScrollBar().maximum())
    apply_theme(main_window)
    assert view.search_keyword_lineEdit.font().pointSizeF() == size
settings.ui_font_size_comboBox.setCurrentIndex(settings.ui_font_size_comboBox.findData(10))
settings.apply_button.click()
main_window.resize(1180, 780)

# Cache units and the entire OpenAI form must fit after switching providers.
from PySide6.QtWidgets import QStyle, QStyleOptionComboBox

for width in (1000, 1180):
    main_window.resize(width, 780)
    for size in (10, 12):
        cfg["ui_font_size"] = size
        apply_theme(main_window)
        for provider in (2, 0, 2):
            settings.translate_source_comboBox.setCurrentIndex(provider)
            app.processEvents()
            settings.scrollArea.verticalScrollBar().setValue(settings.scrollArea.verticalScrollBar().maximum())
            app.processEvents()
            assert settings.cache_size_label.width() >= settings.cache_size_label.sizeHint().width()
            combo_option = QStyleOptionComboBox()
            settings.translate_source_comboBox.initStyleOption(combo_option)
            text_rect = settings.translate_source_comboBox.style().subControlRect(
                QStyle.ComplexControl.CC_ComboBox, combo_option, QStyle.SubControl.SC_ComboBoxEditField,
                settings.translate_source_comboBox)
            assert text_rect.width() >= settings.translate_source_comboBox.fontMetrics().horizontalAdvance(
                settings.translate_source_comboBox.currentText())
            if provider == 2:
                stack = settings.translate_cfg_stackedWidget
                assert stack.height() >= stack.currentWidget().minimumSizeHint().height()
                for field in (settings.oai_base_url_lineEdit, settings.oai_key_lineEdit, settings.oai_model_lineEdit):
                    assert stack.rect().contains(field.mapTo(stack, field.rect().bottomRight()))
                    assert field.y() == settings.oai_base_url_lineEdit.y()
                    assert field.width() >= 80
                assert settings.groupBox_6.rect().contains(stack.mapTo(settings.groupBox_6, stack.rect().bottomRight()))
        assert settings.scrollArea.horizontalScrollBar().maximum() == 0
        snapshot(f"settings-openai-{width}-{size}")
settings.translate_source_comboBox.setCurrentIndex(0)
cfg["ui_font_size"] = 10
apply_theme(main_window)
main_window.resize(1180, 780)

# Closed settings dropdowns must never change on wheel, even with keyboard focus.
before_settings = cfg.copy()
for combo in settings.findChildren(QComboBox):
    index = combo.currentIndex()
    for focused in (False, True):
        combo.setFocus() if focused else combo.clearFocus()
        for delta in (-120, 120):
            event = QWheelEvent(QPointF(combo.rect().center()), QPointF(combo.mapToGlobal(combo.rect().center())),
                                QPoint(), QPoint(0, delta), Qt.MouseButton.NoButton,
                                Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
            QApplication.sendEvent(combo, event)
            assert combo.currentIndex() == index, combo.objectName()
assert cfg.copy() == before_settings

# Real wheel input over a closed dropdown should still scroll the settings page.
combo = settings.color_scheme_comboBox
settings.scrollArea.ensureWidgetVisible(combo)
app.processEvents()
scrollbar = settings.scrollArea.verticalScrollBar()
before_scroll = scrollbar.value()
QTest.wheelEvent(main_window.windowHandle(), combo.mapTo(main_window, combo.rect().center()), QPoint(0, 120))
app.processEvents()
assert scrollbar.value() < before_scroll
assert combo.currentIndex() == 0

from LDDC.common.translator import load_translation

cfg["language"] = "en"
load_translation()
main_window.set_current_widget(0)
main_window.resize(1000, 680)
snapshot("search-english-1000")
assert main_window.Widgets.count() == 6
main_window.set_current_widget(5)
snapshot("settings-english-1000")

assert main_window.findChildren(QPushButton)
print(f"UI smoke checks passed. Screenshots: {OUTPUT}")
main_window.hide()
