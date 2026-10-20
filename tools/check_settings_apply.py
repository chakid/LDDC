# SPDX-FileCopyrightText: Copyright (C) 2024-2025 沉默の金 <cmzj@cmzj.org>
# SPDX-License-Identifier: GPL-3.0-only
"""Offline regression checks for staged settings; never open the user's config or database."""

import json
import os
import sys
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from types import ModuleType
from unittest.mock import patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
(ROOT / "tests" / "artifacts").mkdir(parents=True, exist_ok=True)
temporary = TemporaryDirectory(dir=ROOT / "tests" / "artifacts", ignore_cleanup_errors=True)
paths = ModuleType("LDDC.common.paths")
for name in ("config_dir", "data_dir", "cache_dir", "log_dir", "auto_save_dir", "default_save_lyrics_dir"):
    directory = Path(temporary.name) / name
    directory.mkdir()
    setattr(paths, name, directory)
paths.command_line = None
sys.modules[paths.__name__] = paths

from PySide6.QtGui import QColor, QFontDatabase
from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv)
for name in ("msyh.ttc", "msyhbd.ttc"):
    font = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / name
    if font.exists():
        QFontDatabase.addApplicationFont(str(font))

from LDDC.common.data.cache import cache
from LDDC.common.data.config import Config, cfg
from LDDC.common.logger import logger
from LDDC.gui.components.msg_box import MsgBox
from LDDC.gui.view.main_window import main_window as window
from LDDC.res import resource_rc

resource_rc.qInitResources()
cfg.write_config()
disk_before = cfg.config_path.read_bytes()
window.show()
app.processEvents()
settings = window.settings_widget
window.set_current_widget(5)
assert cfg.config_path.read_bytes() == disk_before
assert not settings.apply_button.isEnabled()
before = deepcopy(dict(cfg))
baseline = settings.collect_settings()
style_before = window.styleSheet()
font_before = app.font()
events = []
cfg.lyrics_changed.connect(lambda _: events.append(deepcopy(dict(cfg))))
cfg.desktop_lyrics_changed.connect(lambda _: events.append(deepcopy(dict(cfg))))

# Change every setting represented by the form, covering text, lists, colors and runtime effects.
settings.lyrics_file_name_fmt_lineEdit.setText("%<title> - staged")
settings.default_save_path_lineEdit.setText("D:/Music/Staged")
settings.id3_ver_comboBox.setCurrentIndex(1)
settings.lyrics_order_buttons.buttons["roma"].click()
settings.lyrics_order_buttons.buttons["roma"].click()
assert settings.lyrics_order_buttons.get_order() == ["orig", "ts", "roma"]
settings.skip_inst_lyrics_checkBox.setChecked(False)
settings.auto_select_checkBox.setChecked(False)
assert settings.local_match_concurrency_spinBox.minimum() == 1
assert settings.local_match_concurrency_spinBox.maximum() == 20
assert settings.local_match_concurrency_spinBox.value() == 5
settings.local_match_concurrency_spinBox.setValue(20)
settings.add_end_timestamp_line_checkBox.setChecked(True)
settings.lrc_ms_digit_count_spinBox.setValue(2)
settings.last_ref_line_time_sty_comboBox.setCurrentIndex(1)
settings.lrc_tag_info_src_comboBox.setCurrentIndex(1)
settings.played_color_list.set_colors([(12, 34, 56)])
settings.unplayed_color_list.set_colors([(78, 90, 123)])
for listing in (settings.lang_type_list, settings.source_list, settings.multi_search_source_list):
    listing.itemWidget(listing.item(0)).toggle()
listing = settings.lang_type_list
listing.insertItem(0, listing.takeItem(listing.count() - 1))
listing.data_changed.emit()
settings.font_comboBox.setCurrentIndex(1)
settings.auto_frame_rate_checkBox.setChecked(False)
settings.frame_rate_spinBox.setValue(144)
settings.ui_font_size_comboBox.setCurrentIndex(settings.ui_font_size_comboBox.findData(12))
settings.language_comboBox.setCurrentIndex(3)
settings.color_scheme_comboBox.setCurrentIndex(2)
settings.log_level_comboBox.setCurrentText("ERROR")
settings.auto_check_update_checkBox.setChecked(False)
settings.translate_source_comboBox.setCurrentIndex(2)
settings.translate_target_lang_comboBox.setCurrentIndex(3)
settings.oai_base_url_lineEdit.setText("https://example.invalid/v1")
settings.oai_key_lineEdit.setText("local-test-placeholder")
settings.oai_model_lineEdit.setText("offline-test")
draft = settings.collect_settings()
assert all(draft[key] != baseline[key] for key in baseline)
assert dict(cfg) == before
assert cfg.config_path.read_bytes() == disk_before
assert window.styleSheet() == style_before and app.font() == font_before
assert window.search_widget.save_path_lineEdit.text() == before["default_save_path"]
assert not events
assert settings.apply_button.isEnabled()
window.set_current_widget(0)
window.set_current_widget(5)
assert settings.collect_settings() == draft

with patch.object(logger, "set_level", wraps=logger.set_level) as set_level:
    settings.apply_button.click()
    set_level.assert_called_once_with("ERROR")
app.processEvents()
assert not settings.apply_button.isEnabled()
assert events and all(all(state[key] == value for key, value in draft.items()) for state in events)
assert all(cfg[key] == value for key, value in draft.items())
saved = json.loads(cfg.config_path.read_text(encoding="utf-8"))
assert saved == json.loads(json.dumps(dict(cfg)))
assert Config()["ui_font_size"] == 12
assert Config()["local_match_concurrency"] == 20
assert "#151c29" in window.styleSheet()
assert window.search_widget.search_keyword_lineEdit.font().pointSizeF() == 12
assert cfg["translate_target_lang"] == "JAPANESE"
assert window.search_widget.save_path_lineEdit.text() == draft["default_save_path"]

# Restoring defaults and cache clearing are also staged, and can be canceled by editing back.
before = deepcopy(dict(cfg))
disk_before = cfg.config_path.read_bytes()
settings.restore2default_pushButton.click()
assert dict(cfg) == before and cfg.config_path.read_bytes() == disk_before
assert settings.apply_button.isEnabled()
settings.apply_button.click()
for key in settings.collect_settings():
    if key.endswith("_colors"):
        assert [QColor(*value).getRgb() for value in cfg[key]] == [QColor(*value).getRgb() for value in cfg.default_cfg[key]]
    else:
        assert cfg[key] == cfg.default_cfg[key], key
cache.set("settings-apply-test", "keep until apply")
settings.clear_cache_pushButton.click()
assert "settings-apply-test" in cache
settings.clear_cache_pushButton.click()
assert not settings.apply_button.isEnabled()
settings.clear_cache_pushButton.click()
settings.apply_button.click()
assert "settings-apply-test" not in cache
assert not settings.apply_button.isEnabled()

# A failed disk replacement leaves active settings and notifications unchanged; retry keeps the draft.
before = deepcopy(dict(cfg))
disk_before = cfg.config_path.read_bytes()
events.clear()
settings.lrc_ms_digit_count_spinBox.setValue(2)
with patch.object(Path, "replace", side_effect=OSError("simulated write failure")), patch.object(MsgBox, "warning") as warning:
    settings.apply_button.click()
    warning.assert_called_once()
assert dict(cfg) == before and cfg.config_path.read_bytes() == disk_before
assert not events and settings.apply_button.isEnabled()
assert not cfg.config_path.with_suffix(".json.tmp").exists()
settings.apply_button.click()
assert cfg["lrc_ms_digit_count"] == 2 and not settings.apply_button.isEnabled()
window.hide()
cache.close()
from LDDC.common.data.local_song_lyrics_db import local_song_lyrics

local_song_lyrics.close()
print("Settings apply checks passed: draft isolation, batch notifications, persistence, defaults, cache and save failure.")
