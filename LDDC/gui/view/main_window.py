# SPDX-FileCopyrightText: Copyright (C) 2024-2025 沉默の金 <cmzj@cmzj.org>
# SPDX-License-Identifier: GPL-3.0-only

"""LDDC的主窗口"""

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QCloseEvent, QCursor, QIcon, QShowEvent
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton, QTableWidget

from LDDC.common.models import Direction
from LDDC.common.translator import language_changed
from LDDC.gui.components.msg_box import MsgBox
from LDDC.gui.components.page_layouts import refine_batch_convert, refine_local_match, refine_settings
from LDDC.gui.components.sidebar_window import SidebarWindow
from LDDC.gui.components.theme import apply_theme, primary_button
from LDDC.gui.exit_manager import exit_manager

from .about import AboutWidget
from .batch_convert import BatchConvertWidget
from .local_match import LocalMatchWidget
from .open_lyrics import OpenLyricsWidget
from .search import SearchWidget
from .setting import SettingWidget


class MainWindow(SidebarWindow):

    def __init__(self) -> None:
        super().__init__()
        exit_manager.windows.append(self)
        self.is_inited = False

    def showEvent(self, event: QShowEvent) -> None:
        # 直到要显示时才初始化
        first_show = not self.is_inited
        if first_show:
            self.init()
        super().showEvent(event)
        if first_show:
            self.center_on_screen()

    def center_on_screen(self) -> None:
        screen = QApplication.screenAt(QCursor.pos()) or self.screen() or QApplication.primaryScreen()
        if screen is None:
            return
        # Include the native title bar and borders, and exclude taskbars/docks.
        frame = self.frameGeometry()
        frame.moveCenter(screen.availableGeometry().center())
        self.move(frame.topLeft())

    def init(self) -> None:
        """初始化主窗口"""
        self.setWindowTitle("LDDC")
        self.resize(1180, 780)
        self.setMinimumSize(1000, 680)
        self.setWindowIcon(QIcon(":/LDDC/img/icon/logo.png"))
        self.set_sidebar_width(164)

        self.search_widget = SearchWidget()
        self.local_match_widget = LocalMatchWidget()
        self.settings_widget = SettingWidget()
        self.about_widget = AboutWidget()
        self.open_lyrics_widget = OpenLyricsWidget()
        self.batch_convert_widget = BatchConvertWidget()

        self.init_widgets()
        self.setup_appearance()
        self.connect_signals()
        self.is_inited = True

    def setup_appearance(self) -> None:
        refine_local_match(self.local_match_widget)
        refine_batch_convert(self.batch_convert_widget)
        refine_settings(self.settings_widget)
        for page in (self.local_match_widget, self.open_lyrics_widget, self.batch_convert_widget,
                     self.settings_widget, self.about_widget):
            if page.layout():
                page.layout().setContentsMargins(24, 24, 24, 24)
                page.layout().setSpacing(14)
        for button in (self.local_match_widget.start_cancel_pushButton,
                       self.batch_convert_widget.start_button, self.open_lyrics_widget.open_pushButton):
            primary_button(button)
        for button in self.findChildren(QPushButton):
            button.setCursor(Qt.CursorShape.PointingHandCursor)
        for table in self.findChildren(QTableWidget):
            table.setAlternatingRowColors(True)
            table.verticalHeader().setDefaultSectionSize(40)
            table.horizontalHeader().setHighlightSections(False)
        apply_theme(self)
        QApplication.styleHints().colorSchemeChanged.connect(lambda _: apply_theme(self))

    def init_widgets(self) -> None:
        self.add_widget(self.tr("搜索"), self.search_widget)
        self.add_widget(self.tr("本地匹配"), self.local_match_widget)
        self.add_widget(self.tr("打开歌词"), self.open_lyrics_widget)
        self.add_widget(self.tr("批量转换"), self.batch_convert_widget)
        self.add_widget(self.tr("关于"), self.about_widget, Direction.BOTTOM)
        self.add_widget(self.tr("设置"), self.settings_widget, Direction.BOTTOM)

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self.local_match_widget.taskmanager.is_finished("local_match"):
            def question_slot(but: QMessageBox.StandardButton) -> None:
                if but == QMessageBox.StandardButton.Yes and not self.local_match_widget.taskmanager.is_finished("local_match"):
                    self.local_match_widget.taskmanager.clear_task("local_match")
                    if exit_manager.window_close_event(self):
                        self.destroy()
                        self.deleteLater()
                    else:
                        self.hide()

            MsgBox.question(self, self.tr("提示"), self.tr("正在匹配歌词，是否退出？"),
                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No, question_slot)
            event.ignore()
            return

        if exit_manager.window_close_event(self):
            super().closeEvent(event)
        else:
            event.ignore()
            self.hide()

    def connect_signals(self) -> None:
        self.widget_changed.connect(self.settings_widget.update_cache_size)  # 更新缓存大小
        self.settings_widget.settings_applied.connect(self.on_settings_applied)
        language_changed.connect(self.retranslateUi)

        self.local_match_widget.search_song.connect(self.search_widget.auto_fetch)
        self.local_match_widget.search_song.connect(lambda: self.set_current_widget(0))
        self.batch_convert_widget.open_lyrics.connect(self.open_lyrics_widget.open_file)
        self.batch_convert_widget.open_lyrics.connect(lambda: self.set_current_widget(2))

    @Slot(dict)
    def on_settings_applied(self, changes: dict) -> None:
        if "default_save_path" in changes:
            self.search_widget.save_path_lineEdit.setText(changes["default_save_path"])

    @Slot()
    def retranslateUi(self) -> None:
        self.search_widget.retranslateUi()
        self.local_match_widget.retranslateUi(self.local_match_widget)
        self.settings_widget.retranslateUi(self.settings_widget)
        self.about_widget.retranslateUi(self.about_widget)
        self.open_lyrics_widget.retranslateUi(self.open_lyrics_widget)
        self.batch_convert_widget.retranslateUi(self.batch_convert_widget)

        # 重新设置侧边栏按钮
        current_widget = self.current_widget
        self.clear_widgets()
        self.init_widgets()
        self.set_current_widget(current_widget)

    @Slot()
    def show_window(self) -> None:
        if self.isMinimized():
            self.showNormal()

        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.show()
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, False)
        self.show()

        self.setFocus()


main_window = MainWindow()
