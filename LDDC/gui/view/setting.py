# SPDX-FileCopyrightText: Copyright (C) 2024-2025 沉默の金 <cmzj@cmzj.org>
# SPDX-License-Identifier: GPL-3.0-only
import os
from copy import deepcopy

from PySide6.QtCore import QEvent, QObject, Qt, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices, QFontDatabase, QGuiApplication
from PySide6.QtWidgets import QApplication, QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpinBox, QWidget

from LDDC.common.data.cache import cache
from LDDC.common.data.config import cfg
from LDDC.common.logger import logger
from LDDC.common.models import TranslateSource, TranslateTargetLanguage
from LDDC.common.paths import log_dir
from LDDC.common.translator import load_translation
from LDDC.gui.components.msg_box import MsgBox
from LDDC.gui.components.lyrics_order_buttons import LyricsOrderButtons
from LDDC.gui.components.theme import apply_theme, primary_button
from LDDC.gui.components.typography import ui_font
from LDDC.gui.ui.settings_ui import Ui_settings


class SettingWidget(QWidget, Ui_settings):
    settings_applied = Signal(dict)

    def __init__(self) -> None:
        super().__init__()
        self._loading = True
        self._clear_cache_pending = False
        self.setupUi(self)
        self.lyrics_order_buttons = LyricsOrderButtons(self.groupBox_2)
        self.gridLayout.replaceWidget(self.langs_order_listWidget, self.lyrics_order_buttons)
        self.langs_order_listWidget.hide()
        self.ui_font_size_label = QLabel(self.groupBox_3)
        self.ui_font_size_comboBox = QComboBox(self.groupBox_3)
        self.ui_font_size_comboBox.setObjectName("ui_font_size_comboBox")
        for size in range(9, 13):
            self.ui_font_size_comboBox.addItem(f"{size} pt", size)
        self.ui_font_size_label.setBuddy(self.ui_font_size_comboBox)
        self.gridLayout_3.addWidget(self.ui_font_size_label, 4, 0)
        self.gridLayout_3.addWidget(self.ui_font_size_comboBox, 4, 1)
        self.local_match_concurrency_label = QLabel(self.groupBox_2)
        self.local_match_concurrency_spinBox = QSpinBox(self.groupBox_2)
        self.local_match_concurrency_spinBox.setObjectName("local_match_concurrency_spinBox")
        self.local_match_concurrency_spinBox.setRange(1, 20)
        self.local_match_concurrency_label.setBuddy(self.local_match_concurrency_spinBox)
        self.gridLayout.addWidget(self.local_match_concurrency_label, 6, 1)
        self.gridLayout.addWidget(self.local_match_concurrency_spinBox, 6, 2, 1, 3)
        for combo in self.findChildren(QComboBox):
            combo.installEventFilter(self)
        self.apply_status_label = QLabel(self)
        self.apply_status_label.setProperty("role", "muted")
        self.apply_button = QPushButton(self.tr("应用"), self)
        self.apply_button.setObjectName("apply_settings_button")
        self.apply_button.setMinimumWidth(100)
        self.apply_button.setCursor(Qt.CursorShape.PointingHandCursor)
        primary_button(self.apply_button)
        footer = QHBoxLayout()
        footer.addWidget(self.apply_status_label)
        footer.addStretch(1)
        footer.addWidget(self.apply_button)
        self.verticalLayout.addLayout(footer)
        self.init_ui()
        self._baseline = self.collect_settings()
        self._loading = False
        self.connect_signals()
        self.update_dirty()

    def retranslateUi(self, settings: QWidget) -> None:
        super().retranslateUi(settings)
        self.groupBox_6.setTitle(f"{self.groupBox_6.title()} / {self.groupBox_5.title()} / {self.groupBox_7.title()}")
        if hasattr(self, "apply_button"):
            self.apply_button.setText(self.tr("应用"))
            self.ui_font_size_label.setText(self.tr("界面字号:"))
            self.local_match_concurrency_label.setText(self.tr("最多同时下载歌词数量:"))
            self.update_dirty()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        # Let the page scroll without changing settings under the pointer.
        # The open popup keeps its normal scrolling and selection behavior.
        if (event.type() == QEvent.Type.Wheel and isinstance(watched, QComboBox)
                and not watched.view().isVisible()):
            event.ignore()
            return True
        return super().eventFilter(watched, event)

    def init_ui(self, values: dict | None = None) -> None:
        data = cfg if values is None else values
        self.ui_font_size_label.setText(self.tr("界面字号:"))
        self.ui_font_size_comboBox.setToolTip(self.tr("调整应用界面的文字大小，点击应用后生效；桌面歌词字号仍通过拉伸歌词窗口调整。"))
        self.ui_font_size_comboBox.setCurrentIndex(self.ui_font_size_comboBox.findData(data["ui_font_size"]))
        # 保存设置
        self.lyrics_file_name_fmt_lineEdit.setText(data["lyrics_file_name_fmt"])
        self.default_save_path_lineEdit.setText(data["default_save_path"])
        self.id3_ver_comboBox.setCurrentText(data["ID3_version"])

        self.local_match_concurrency_label.setText(self.tr("最多同时下载歌词数量:"))
        self.local_match_concurrency_spinBox.setToolTip(self.tr("本地匹配时同时处理的歌曲数量（1–20），点击应用后对新任务生效。"))
        self.local_match_concurrency_spinBox.setValue(data["local_match_concurrency"])
        # 歌词设置
        self.lyrics_order_buttons.set_order(data["langs_order"])
        self.skip_inst_lyrics_checkBox.setChecked(data["skip_inst_lyrics"])
        self.auto_select_checkBox.setChecked(data["auto_select"])
        self.add_end_timestamp_line_checkBox.setChecked(data["add_end_timestamp_line"])
        self.lrc_ms_digit_count_spinBox.setValue(data["lrc_ms_digit_count"])
        self.last_ref_line_time_sty_comboBox.setCurrentIndex(data["last_ref_line_time_sty"])
        self.lrc_tag_info_src_comboBox.setCurrentIndex(data["lrc_tag_info_src"])

        # 桌面歌词部分
        self.played_color_list.set_colors(data["desktop_lyrics_played_colors"])
        self.unplayed_color_list.set_colors(data["desktop_lyrics_unplayed_colors"])

        self.lang_type_list.set_langs(data["desktop_lyrics_default_langs"], data["desktop_lyrics_langs_order"])
        self.source_list.set_soures(data["desktop_lyrics_sources"])

        self.font_comboBox.clear()
        self.font_comboBox.addItem(self.tr("跟随系统"), "")
        self.font_comboBox.addItems(QFontDatabase.families())
        if not data["desktop_lyrics_font_family"]:
            self.font_comboBox.setCurrentIndex(0)
        elif data["desktop_lyrics_font_family"] in QFontDatabase.families():
            self.font_comboBox.setCurrentText(data["desktop_lyrics_font_family"])
        else:
            self.font_comboBox.addItem(data["desktop_lyrics_font_family"])
            self.font_comboBox.setCurrentIndex(self.font_comboBox.count() - 1)

        self.auto_frame_rate_checkBox.setChecked(bool(data["desktop_lyrics_refresh_rate"] == -1))
        self.frame_rate_spinBox.setDisabled(self.auto_frame_rate_checkBox.isChecked())
        if data["desktop_lyrics_refresh_rate"] >= 0:
            self.frame_rate_spinBox.setValue(data["desktop_lyrics_refresh_rate"])

        # 其他设置
        match data["language"]:
            case "auto":
                self.language_comboBox.setCurrentIndex(0)
            case "zh-Hans":
                self.language_comboBox.setCurrentIndex(1)
            case "zh-Hant":
                self.language_comboBox.setCurrentIndex(2)
            case "en":
                self.language_comboBox.setCurrentIndex(3)
            case "ja":
                self.language_comboBox.setCurrentIndex(4)

        self.color_scheme_mapping = {
            0: "auto",
            1: "light",
            2: "dark",
        }
        for i, v in self.color_scheme_mapping.items():
            if v == data["color_scheme"]:
                self.color_scheme_comboBox.setCurrentIndex(i)
                break

        self.log_level_comboBox.setCurrentText(data["log_level"])
        self.auto_check_update_checkBox.setChecked(data["auto_check_update"])

        # 翻译API设置
        self.translate_source_comboBox.setCurrentIndex(TranslateSource.__members__.get(data["translate_source"], TranslateSource(0)).value)
        self.translate_cfg_stackedWidget.setCurrentIndex(self.translate_source_comboBox.currentIndex())

        self.translate_target_lang_comboBox.setCurrentIndex(
            TranslateTargetLanguage.__members__.get(data["translate_target_lang"], TranslateTargetLanguage(0)).value,
        )
        self.oai_base_url_lineEdit.setText(data["openai_base_url"])
        self.oai_key_lineEdit.setText(data["openai_api_key"])
        self.oai_model_lineEdit.setText(data["openai_model"])

        # 搜索设置
        self.multi_search_source_list.set_soures(data["multi_search_sources"])

    @Slot()
    def select_default_save_path(self) -> None:
        @Slot(str)
        def file_selected(path: str) -> None:
            self.default_save_path_lineEdit.setText(os.path.normpath(path))

        dialog = QFileDialog(self)
        dialog.setWindowTitle(self.tr("选择默认保存路径"))
        dialog.setFileMode(QFileDialog.FileMode.Directory)
        dialog.fileSelected.connect(file_selected)
        dialog.open()

    def collect_settings(self) -> dict:
        """Read the settings form without modifying the active configuration."""
        return {
            "lyrics_file_name_fmt": self.lyrics_file_name_fmt_lineEdit.text(),
            "default_save_path": self.default_save_path_lineEdit.text(),
            "ID3_version": self.id3_ver_comboBox.currentText(),
            "langs_order": self.lyrics_order_buttons.get_order(),
            "skip_inst_lyrics": self.skip_inst_lyrics_checkBox.isChecked(),
            "auto_select": self.auto_select_checkBox.isChecked(),
            "local_match_concurrency": self.local_match_concurrency_spinBox.value(),
            "add_end_timestamp_line": self.add_end_timestamp_line_checkBox.isChecked(),
            "lrc_ms_digit_count": self.lrc_ms_digit_count_spinBox.value(),
            "last_ref_line_time_sty": self.last_ref_line_time_sty_comboBox.currentIndex(),
            "lrc_tag_info_src": self.lrc_tag_info_src_comboBox.currentIndex(),
            "desktop_lyrics_played_colors": self.played_color_list.get_colors(),
            "desktop_lyrics_unplayed_colors": self.unplayed_color_list.get_colors(),
            "desktop_lyrics_default_langs": self.lang_type_list.get_data(),
            "desktop_lyrics_langs_order": self.lang_type_list.get_order(),
            "desktop_lyrics_sources": self.source_list.get_data(),
            "desktop_lyrics_font_family": self.font_comboBox.currentData()
            if self.font_comboBox.currentData() is not None else self.font_comboBox.currentText(),
            "desktop_lyrics_refresh_rate": -1 if self.auto_frame_rate_checkBox.isChecked() else self.frame_rate_spinBox.value(),
            "ui_font_size": self.ui_font_size_comboBox.currentData(),
            "language": ("auto", "zh-Hans", "zh-Hant", "en", "ja")[self.language_comboBox.currentIndex()],
            "color_scheme": self.color_scheme_mapping[self.color_scheme_comboBox.currentIndex()],
            "log_level": self.log_level_comboBox.currentText(),
            "auto_check_update": self.auto_check_update_checkBox.isChecked(),
            "translate_source": TranslateSource(self.translate_source_comboBox.currentIndex()).name,
            "translate_target_lang": TranslateTargetLanguage(self.translate_target_lang_comboBox.currentIndex()).name,
            "openai_base_url": self.oai_base_url_lineEdit.text(),
            "openai_api_key": self.oai_key_lineEdit.text(),
            "openai_model": self.oai_model_lineEdit.text(),
            "multi_search_sources": self.multi_search_source_list.get_data(),
        }

    def connect_signals(self) -> None:
        # Editing changes only the form. Configuration and runtime effects live in apply_settings.
        for widget in self.findChildren(QLineEdit):
            widget.textChanged.connect(self.update_dirty)
        for widget in self.findChildren(QComboBox):
            widget.currentIndexChanged.connect(self.update_dirty)
        for widget in self.findChildren(QSpinBox):
            widget.valueChanged.connect(self.update_dirty)
        for widget in self.findChildren(QCheckBox):
            widget.toggled.connect(self.update_dirty)
        self.lyrics_order_buttons.order_changed.connect(self.update_dirty)
        for listing in (self.lang_type_list, self.source_list, self.multi_search_source_list):
            listing.data_changed.connect(self.update_dirty)
        for listing in (self.played_color_list, self.unplayed_color_list):
            listing.color_changed.connect(self.update_dirty)
        self.auto_frame_rate_checkBox.toggled.connect(self.frame_rate_spinBox.setDisabled)
        self.apply_button.clicked.connect(self.apply_settings)
        self.restore2default_pushButton.clicked.connect(self.restore_defaults)
        self.select_default_save_path_pushButton.clicked.connect(self.select_default_save_path)
        self.played_add_color_button.clicked.connect(lambda: self.played_color_list.open_color_dialog())
        self.played_del_color_button.clicked.connect(self.played_color_list.del_selected)
        self.unplayed_add_color_button.clicked.connect(lambda: self.unplayed_color_list.open_color_dialog())
        self.unplayed_del_color_button.clicked.connect(self.unplayed_color_list.del_selected)

        from .local_song_lyrics_db_manager import local_song_lyrics_db_manager

        self.show_local_song_lyrics_db_manager_button.clicked.connect(local_song_lyrics_db_manager.show)
        self.open_log_dir_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(log_dir)))
        self.clear_cache_pushButton.clicked.connect(self.clear_cache)

    def update_dirty(self, *_args: object) -> None:
        if self._loading:
            return
        dirty = self.collect_settings() != self._baseline or self._clear_cache_pending
        self.apply_button.setEnabled(dirty)
        self.apply_status_label.setText(self.tr("有未应用的更改") if dirty else self.tr("所有更改已应用"))
        self.clear_cache_pushButton.setText(self.tr("取消清除缓存") if self._clear_cache_pending else self.tr("清除缓存"))

    @Slot()
    def restore_defaults(self) -> None:
        self._loading = True
        try:
            self.init_ui(deepcopy(cfg.default_cfg))
        finally:
            self._loading = False
        self.update_dirty()

    @Slot()
    def apply_settings(self) -> None:
        values = self.collect_settings()
        changes = {key: value for key, value in values.items() if value != self._baseline[key]}
        try:
            cfg.apply_settings(changes)
        except Exception as error:
            MsgBox.warning(self, self.tr("应用失败"), self.tr("无法保存设置：") + str(error))
            return

        self._loading = True
        try:
            if "log_level" in changes:
                logger.set_level(cfg["log_level"])
            if "color_scheme" in changes:
                hints = QGuiApplication.styleHints()
                if cfg["color_scheme"] == "auto":
                    hints.unsetColorScheme()
                else:
                    hints.setColorScheme(Qt.ColorScheme.Dark if cfg["color_scheme"] == "dark" else Qt.ColorScheme.Light)
            if "ui_font_size" in changes:
                QApplication.instance().setFont(ui_font())
            if "color_scheme" in changes or "ui_font_size" in changes:
                apply_theme(self.window())
            if "language" in changes:
                load_translation()
            self.init_ui()
            self._baseline = self.collect_settings()
        finally:
            self._loading = False

        if self._clear_cache_pending:
            try:
                cache.clear()
                self._clear_cache_pending = False
            except Exception as error:
                MsgBox.warning(self, self.tr("清除缓存失败"), str(error))
        self.update_cache_size()
        self.update_dirty()
        self.settings_applied.emit(changes)

    @Slot()
    def update_cache_size(self) -> None:
        self.cache_size_label.setText(self.tr("缓存大小:") + f" {cache.volume() / 1000000:.2f} MB")

    @Slot()
    def clear_cache(self) -> None:
        self._clear_cache_pending = not self._clear_cache_pending
        self.update_dirty()
