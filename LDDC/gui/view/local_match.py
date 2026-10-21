# SPDX-FileCopyrightText: Copyright (C) 2024-2025 沉默の金 <cmzj@cmzj.org>
# SPDX-License-Identifier: GPL-3.0-only
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QMimeData, Qt, QUrl, Signal, Slot
from PySide6.QtGui import QContextMenuEvent, QDesktopServices, QDragEnterEvent, QDropEvent, QKeyEvent
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QLineEdit,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QStyle,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from LDDC.common.data.config import cfg
from LDDC.common.models import LyricsFormat, SongInfo, Source
from LDDC.common.models._enums import FileNameMode, SaveMode
from LDDC.common.path_processor import get_local_match_save_path
from LDDC.common.paths import default_save_lyrics_dir
from LDDC.common.task_manager import TaskManager
from LDDC.gui.components.custom_widgets import RowSelectionDelegate
from LDDC.gui.components.msg_box import MsgBox
from LDDC.gui.components.page_options import PageOptions
from LDDC.gui.ui.local_match_ui import Ui_local_match
from LDDC.gui.workers.local_match import (
    GetInfosWorker,
    LocalMatchingStatus,
    LocalMatchingStatusType,
    LocalMatchSave2TagMode,
    LocalMatchWorker,
)


class LocalMatchWidget(QWidget, Ui_local_match):
    search_song = Signal(SongInfo)

    _get_infos_callback_signal = Signal(str, int, int, SongInfo)
    _restore_match_signal = Signal()
    _restore_infos_signal = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setupUi(self)
        self.selected_input_files: list[str] = []
        self.selected_input_dirs: list[str] = []
        self.selected_files_edit = QLineEdit(self.control_bar)
        self.selected_dirs_edit = QLineEdit(self.control_bar)
        self.selected_save_path_edit = QLineEdit(self.control_bar)
        for field in (self.selected_files_edit, self.selected_dirs_edit, self.selected_save_path_edit):
            field.setReadOnly(True)
            field.setMinimumWidth(0)
        for field, paths in ((self.selected_files_edit, self.selected_input_files), (self.selected_dirs_edit, self.selected_input_dirs)):
            action = field.addAction(
                self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView), QLineEdit.ActionPosition.TrailingPosition,
            )
            action.triggered.connect(lambda _checked=False, paths=paths: self.show_selected_paths(paths))
            field.setProperty("pathsAction", action)
        self._matching = False
        self._cancel_requested = False
        self._match_result_received = False
        self._pending_rows: set[int] = set()
        self.retry_failed_button = QPushButton(self.tr("重试失败歌曲"), self.control_bar)
        self.retry_failed_button.setObjectName("retry_failed_button")
        self.retry_failed_button.setEnabled(False)
        self.gridLayout.addWidget(self.retry_failed_button, 6, 0)
        self.setAcceptDrops(True)  # 启用拖放功能
        self.connect_signals()

        self.songs_table.set_proportions([0.2, 0.1, 0.1, 0.3, 2, 0.3, 2])  # 设置列宽比例
        self.songs_table.setItemDelegate(RowSelectionDelegate(self.songs_table))
        # Paths containing spaces must stay on one line, like the song path column.
        self.songs_table.setWordWrap(False)
        self.songs_table.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.songs_table.verticalHeader().setObjectName("localMatchRowHeader")
        self.songs_table.verticalHeader().setHighlightSections(True)
        self.songs_table.horizontalHeader().setHighlightSections(False)
        # Absorb proportional-width rounding and content-driven column changes.
        self.songs_table.horizontalHeader().setStretchLastSection(True)
        self.source_listWidget.set_soures(["QM", "KG", "NE"])

        def restore_start_cancel() -> None:
            if self.taskmanager.is_finished() and not self._matching:
                self.start_cancel_pushButton.setText(self.tr("开始"))
                self.start_cancel_pushButton.setEnabled(True)
                self.update_retry_button()

        def restore() -> None:
            self._matching = False
            for row in self._pending_rows:
                item = self.songs_table.item(row, 0)
                status = item.data(Qt.ItemDataRole.UserRole + 2) if item else None
                if isinstance(status, LocalMatchingStatus):
                    self.update_status(replace(status, index=row))
                else:
                    self.songs_table.item(row, 6).setText(self.tr("未匹配"))
            self._pending_rows.clear()
            if not self._match_result_received:
                self.update_progressbar(self.tr("匹配异常结束，请重试"), 0, 1)
            for widget in self.control_bar.children():
                if isinstance(widget, QWidget):
                    widget.setEnabled(True)
            restore_start_cancel()

        self._restore_match_signal.connect(restore, Qt.ConnectionType.QueuedConnection)
        self._restore_infos_signal.connect(restore_start_cancel, Qt.ConnectionType.QueuedConnection)
        self.taskmanager = TaskManager(
            {"get_infos": [], "local_match": []},
            {"get_infos": self._restore_infos_signal.emit, "local_match": self._restore_match_signal.emit},
        )
        self.songs_table.model().rowsRemoved.connect(self.update_retry_button)
        self.save_root_path: Path | None = None  # 保存根目录
        self.save_path_errors: set[str] = set()  # 保存路径错误
        self.page_options = PageOptions(self, "local_match", (
            "save_mode_comboBox", "save2tag_mode_comboBox", "filename_mode_comboBox", "lyricsformat_comboBox",
            "original_checkBox", "translate_checkBox", "romanized_checkBox", "min_score_spinBox",
            "skip_existing_lyrics_checkbox", "source_listWidget",
        ), ("save_root_path",))
        self.update_selection_paths()

    def retranslateUi(self, local_match: QWidget) -> None:
        super().retranslateUi(local_match)
        if hasattr(self, "retry_failed_button"):
            self.retry_failed_button.setText(self.tr("重试失败歌曲"))
        if hasattr(self, "page_options"):
            self.update_selection_paths()

    def update_selection_paths(self) -> None:
        """Show selected inputs separately from the parsed song list below."""
        for field, paths, placeholder in (
            (self.selected_files_edit, self.selected_input_files, self.tr("尚未选择文件，也可以拖入歌曲")),
            (self.selected_dirs_edit, self.selected_input_dirs, self.tr("尚未选择文件夹")),
        ):
            text = " ; ".join(paths)
            if len(paths) > 1:
                text = self.tr("共 {count} 项：").format(count=len(paths)) + text
            field.setText(text)
            field.setCursorPosition(0)
            field.setPlaceholderText(placeholder)
            field.setToolTip("\n".join(paths[:5]) or placeholder)
            action = field.property("pathsAction")
            action.setVisible(len(paths) > 1)
            action.setToolTip(self.tr("查看和复制完整路径列表"))
        save_mode = SaveMode(self.save_mode_comboBox.currentIndex())
        save_text = str(self.save_root_path) if self.save_root_path else ""
        if save_mode == SaveMode.SONG:
            hint = self.tr("当前保存到歌曲所在目录；所选保存路径不生效")
        else:
            hint = self.tr("尚未选择保存路径") if not save_text else self.tr("歌词将保存到所选目录")
        if LocalMatchSave2TagMode(self.save2tag_mode_comboBox.currentIndex()) == LocalMatchSave2TagMode.ONLY_TAG:
            hint = self.tr("当前仅保存到歌曲标签；CUE 歌曲仍会保存歌词文件")
        self.selected_save_path_edit.setText(save_text)
        self.selected_save_path_edit.setCursorPosition(0)
        self.selected_save_path_edit.setPlaceholderText(hint)
        self.selected_save_path_edit.setToolTip(f"{save_text}\n{hint}".strip())

    def show_selected_paths(self, paths: list[str]) -> None:
        dialog = QDialog(self)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.setWindowTitle(self.tr("所选路径（共 {count} 项）").format(count=len(paths)))
        dialog.resize(680, 320)
        layout = QVBoxLayout(dialog)
        listing = QPlainTextEdit(dialog)
        listing.setReadOnly(True)
        listing.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        listing.setPlainText("\n".join(paths))
        layout.addWidget(listing)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, dialog)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.open()

    def connect_signals(self) -> None:
        """连接信号与槽"""
        self.select_files_button.clicked.connect(self.select_files)
        self.select_dirs_button.clicked.connect(self.select_dirs)
        self.save_path_button.clicked.connect(self.select_save_root_path)
        self.start_cancel_pushButton.clicked.connect(self.start_cancel)
        self.retry_failed_button.clicked.connect(self.retry_failed)

        self.save_mode_comboBox.currentIndexChanged.connect(self.update_save_paths)
        self.filename_mode_comboBox.currentIndexChanged.connect(self.update_save_paths)
        self.save2tag_mode_comboBox.currentIndexChanged.connect(self.update_save_paths)
        self.lyricsformat_comboBox.currentIndexChanged.connect(self.update_save_paths)

    @Slot(str, int, int)
    def update_progressbar(self, text: str, value: int, max_value: int) -> None:
        """更新进度条"""
        self.progressBar.setRange(0, max_value if max_value or text else 1)
        self.progressBar.setValue(value)
        complete = max_value > 0 and value >= max_value
        if self.progressBar.property("complete") != complete:
            self.progressBar.setProperty("complete", complete)
            self.progressBar.style().unpolish(self.progressBar)
            self.progressBar.style().polish(self.progressBar)
        self.progressBar.setFormat("%v/%m %p%")
        self.status_label.setText(text)

    @Slot()
    def start_cancel(self) -> None:
        if self._matching or not self.taskmanager.is_finished():
            self._cancel_requested = True
            self.taskmanager.cancel()
            self.start_cancel_pushButton.setEnabled(False)
            self.start_cancel_pushButton.setText(self.tr("取消中..."))
            return

        self.start_matching()

    def failed_rows(self) -> list[int]:
        rows = []
        for row in range(self.songs_table.rowCount()):
            item = self.songs_table.item(row, 0)
            status = item.data(Qt.ItemDataRole.UserRole + 2) if item else None
            if isinstance(status, LocalMatchingStatus) and status.status in (
                LocalMatchingStatusType.AUTO_FETCH_FAIL,
                LocalMatchingStatusType.SAVE_FAIL,
                LocalMatchingStatusType.UNDERKNOWN_ERROR,
            ):
                rows.append(row)
        return rows

    def update_retry_button(self, *_args: object) -> None:
        self.retry_failed_button.setEnabled(not self._matching and self.taskmanager.is_finished() and bool(self.failed_rows()))

    @Slot()
    def retry_failed(self) -> None:
        if not self._matching and self.taskmanager.is_finished():
            self.start_matching(only_failed=True)

    def start_matching(self, *, only_failed: bool = False) -> None:
        if LocalMatchSave2TagMode(self.save2tag_mode_comboBox.currentIndex()) in (
            LocalMatchSave2TagMode.ONLY_TAG,
            LocalMatchSave2TagMode.BOTH,
        ) and LyricsFormat(self.lyricsformat_comboBox.currentIndex()) not in (LyricsFormat.VERBATIMLRC, LyricsFormat.LINEBYLINELRC, LyricsFormat.ENHANCEDLRC):
            MsgBox.warning(self, self.tr("警告"), self.tr("歌曲标签中的歌词应为LRC格式"))
            return

        if not self.langs:
            MsgBox.warning(self, self.tr("警告"), self.tr("请选择要匹配的语言"))
            return

        if len(sources := [Source[k] for k in self.source_listWidget.get_data()]) == 0:
            MsgBox.warning(self, self.tr("警告"), self.tr("请选择至少一个源！"))
            return

        if self.save_path_errors:
            MsgBox.warning(self, self.tr("警告"), "\n".join(self.save_path_errors))
            return

        rows = self.failed_rows() if only_failed else list(range(self.songs_table.rowCount()))
        infos = [
            (self.songs_table.item(row, 0).data(Qt.ItemDataRole.UserRole),
             self.songs_table.item(row, 0).data(Qt.ItemDataRole.UserRole + 1))
            for row in rows
        ]
        if not infos:
            MsgBox.warning(self, self.tr("警告"), self.tr("请选择要匹配的歌曲！"))
            return

        skip_existing_lyrics = self.skip_existing_lyrics_checkbox.isChecked() and not only_failed
        save2tag_mode = LocalMatchSave2TagMode(self.save2tag_mode_comboBox.currentIndex())
        file_name_mode = FileNameMode(self.filename_mode_comboBox.currentIndex())
        if skip_existing_lyrics and (save2tag_mode != LocalMatchSave2TagMode.ONLY_TAG and file_name_mode == FileNameMode.FORMAT_BY_LYRICS):
            MsgBox.warning(self, self.tr("警告"), self.tr("跳过已存在歌词时,如果不仅保存到标签,则歌曲文件名模式不能为按歌词格式命名！"))
            return

        worker = LocalMatchWorker(
            infos_root_paths=infos,
            save_mode=SaveMode(self.save_mode_comboBox.currentIndex()),
            file_name_mode=file_name_mode,
            save2tag_mode=save2tag_mode,
            lyrics_format=LyricsFormat(self.lyricsformat_comboBox.currentIndex()),
            langs=self.langs,
            save_root_path=self.save_root_path,
            min_score=self.min_score_spinBox.value(),
            sources=sources,
            skip_existing_lyrics=skip_existing_lyrics,
            refresh=only_failed,
        )

        def progress(text: str, value: int, maximum: int, status: LocalMatchingStatus | None) -> None:
            self.update_progressbar(text, value, maximum)
            if status is not None:
                row = rows[status.index]
                self._pending_rows.discard(row)
                self.update_status(replace(status, index=row))

        worker.progress.connect(progress)
        worker.finished.connect(self.matching_finished)
        self._matching = True
        self._cancel_requested = False
        self._match_result_received = False
        self._pending_rows = set(rows)
        for row in rows:
            item = self.songs_table.item(row, 6)
            item.setText(self.tr("等待匹配"))
            item.setForeground(self.palette().text())
            item.setToolTip("")
        self.update_progressbar(self.tr("正在匹配歌词..."), 0, len(rows))

        self.start_cancel_pushButton.setText(self.tr("取消(匹配歌词)"))

        for widget in self.control_bar.children():
            if isinstance(widget, QWidget) and widget != self.start_cancel_pushButton:
                widget.setEnabled(False)
        self.taskmanager.run_worker("local_match", worker)

    @Slot(int, int, int, int)
    def matching_finished(self, total: int, success_count: int, fail_count: int, skip_count: int) -> None:
        self._match_result_received = True
        state = self.tr("已取消") if self._cancel_requested else (self.tr("匹配完成") if fail_count else self.tr("匹配成功"))
        summary = self.tr("已处理{total}首歌曲，匹配成功{success}首，匹配失败{fail}首，跳过{skip}首。").format(
            total=total, success=success_count, fail=fail_count, skip=skip_count,
        )
        self.update_progressbar(f"{state}：{summary}", 1, 1)
        self.progressBar.setFormat(state)

    def add2table(self, infos: list[tuple[SongInfo, Path | None]]) -> None:
        """添加文件信息到表格中

        Args:
            infos: 文件信息
            root_path: 文件根路径, 注意传入infos为list[SongInfo]时, root_path应该为None

        """
        existing_infos = self.get_table_infos()
        for info, root_path in infos:
            if (info, root_path) in existing_infos:
                continue
            i = self.songs_table.rowCount()
            self.songs_table.insertRow(i)
            item = QTableWidgetItem(info.title or "")
            item.setData(Qt.ItemDataRole.UserRole, info)
            item.setData(Qt.ItemDataRole.UserRole + 1, root_path)
            self.songs_table.setItem(i, 0, item)
            self.songs_table.setItem(i, 1, QTableWidgetItem(info.str_artist))
            self.songs_table.setItem(i, 2, QTableWidgetItem(info.album or ""))
            path_item = QTableWidgetItem(str(info.path) if info.path else "")
            path_item.setToolTip(path_item.text())
            self.songs_table.setItem(i, 3, path_item)
            if info.duration is not None:
                self.songs_table.setItem(i, 4, QTableWidgetItem(info.format_duration))
            self.songs_table.setItem(i, 6, QTableWidgetItem(self.tr("未匹配")))
        self.update_save_paths()

    def update_status(self, status: LocalMatchingStatus) -> None:
        status_item, info_item = self.songs_table.item(status.index, 6), self.songs_table.item(status.index, 0)
        if not status_item or not info_item:
            MsgBox.critical(self, self.tr("错误"), self.tr("对应的引索{}不存在").format(status.index))
            return
        info_item.setData(Qt.ItemDataRole.UserRole + 2, status)
        match status.status:
            case LocalMatchingStatusType.SUCCESS:
                status_item.setForeground(Qt.GlobalColor.green)
                status_item.setText(self.tr("成功"))
                if status.path:
                    info: SongInfo = info_item.data(Qt.ItemDataRole.UserRole)
                    if (
                        LocalMatchSave2TagMode(self.save2tag_mode_comboBox.currentIndex()) in (LocalMatchSave2TagMode.ONLY_TAG, LocalMatchSave2TagMode.BOTH)
                        and not info.from_cue
                    ):
                        path_text = f"{self.tr('保存到标签')} + {status.path!s}"
                    else:
                        path_text = str(status.path)
                    path_item = QTableWidgetItem(path_text)
                    path_item.setToolTip(path_text)
                    self.songs_table.setItem(status.index, 5, path_item)
            case LocalMatchingStatusType.SKIP_INST | LocalMatchingStatusType.SKIP_EXISTING:
                status_item.setForeground(Qt.GlobalColor.blue)
                status_item.setText(self.tr("跳过"))

            case _:
                status_item.setForeground(Qt.GlobalColor.red)
                status_item.setText(self.tr("失败"))
        status_item.setToolTip(status.text)
        self.update_retry_button()

    @Slot(list)
    @Slot(str)
    def get_infos(self, paths: list[str] | str | QMimeData) -> None:
        """获取文件信息,并添加到表格中"""
        if self._matching:
            return
        if isinstance(paths, QMimeData):
            mime = paths

        if isinstance(paths, str):
            paths = [paths]

        if not paths:
            return

        if isinstance(paths, list) and paths:
            mime = QMimeData()
            mime.setUrls([QUrl.fromLocalFile(path) for path in paths])

        if mime.hasUrls():
            for url in mime.urls():
                if url.isLocalFile():
                    path = Path(url.toLocalFile())
                    selected = self.selected_input_dirs if path.is_dir() else self.selected_input_files
                    if str(path) not in selected:
                        selected.append(str(path))
            self.update_selection_paths()

        worker = GetInfosWorker(self, mime)
        worker.progress.connect(self.update_progressbar)
        worker.finished.connect(
            lambda result, errors: (self.add2table(result) if result else None, MsgBox.critical(self, self.tr("错误"), "\n".join(errors)) if errors else None),
        )
        self.taskmanager.run_worker("get_infos", worker)
        self.update_retry_button()
        self.start_cancel_pushButton.setText(self.tr("取消(获取文件信息)"))

    @Slot()
    def select_files(self) -> None:
        dialog = QFileDialog(self)
        dialog.setWindowTitle(self.tr("选择要匹配的文件"))
        dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
        dialog.filesSelected.connect(self.get_infos)
        self.page_options.remember_dialog(dialog, "input_files")
        dialog.open()

    @Slot()
    def select_dirs(self) -> None:
        dialog = QFileDialog(self)
        dialog.setWindowTitle(self.tr("选择要遍历的文件夹"))
        dialog.setFileMode(QFileDialog.FileMode.Directory)
        dialog.fileSelected.connect(self.get_infos)
        self.page_options.remember_dialog(dialog, "input_directory")
        dialog.open()

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        formats = event.mimeData().formats()
        if (
            event.mimeData().hasUrls()
            or 'application/x-qt-windows-mime;value="foobar2000_playable_location_format"' in formats
            or 'application/x-qt-windows-mime;value="ACL.FileURIs"' in formats
        ) and not self._matching and self.taskmanager.is_finished("local_match"):
            event.acceptProposedAction()  # 接受拖动操作
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        mime = QMimeData()

        # 复制一份数据以便在其他线程使用
        _mime = event.mimeData()
        for f in _mime.formats():
            mime.setData(f, _mime.data(f))
        self.get_infos(mime)

    @Slot()
    def select_save_root_path(self) -> None:
        """选择保存根目录"""

        @Slot(str)
        def set_save_root_path(path: str) -> None:
            self.save_root_path = Path(path).resolve()
            self.page_options.save()
            self.update_save_paths()

        dialog = QFileDialog(self)
        dialog.setWindowTitle(self.tr("选择保存根目录"))
        dialog.setFileMode(QFileDialog.FileMode.Directory)
        dialog.fileSelected.connect(set_save_root_path)
        dialog.setDirectory(str(self.save_root_path or default_save_lyrics_dir))
        dialog.open()

    @Slot(str)
    def select_root_path(self, rows: list[int]) -> None:
        @Slot(str)
        def set_root_path(path_str: str) -> None:
            path = Path(path_str)
            skips = []
            for row in rows:
                info_item = self.songs_table.item(row, 0)
                if not info_item:
                    MsgBox.critical(self, self.tr("错误"), self.tr("对应的引索{}不存在").format(row))
                    continue
                info: SongInfo = info_item.data(Qt.ItemDataRole.UserRole)
                if not info.path:
                    raise ValueError(self.tr("歌曲{}的路径为空").format(info.artist_title()))

                # 检查驱动器是否相同(仅在 Windows 上适用)
                # 检查文件路径是否以目录路径为前缀
                if info.path.is_relative_to(path):
                    info_item.setData(Qt.ItemDataRole.UserRole + 1, path)
                else:
                    skips.append(str(info.path))

            if skips:
                MsgBox.warning(self, self.tr("警告"), self.tr("由于以下歌曲不在指定的根目录中,无法设置\n") + "\n".join(skips))

            self.update_save_paths()

        dialog = QFileDialog(self)
        dialog.setWindowTitle(self.tr("选择歌曲根目录"))
        dialog.setFileMode(QFileDialog.FileMode.Directory)
        info_item = self.songs_table.item(rows[0], 0)
        if not info_item:
            MsgBox.critical(self, self.tr("错误"), self.tr("对应的引索{}不存在").format(rows[0]))
            return
        dialog.setDirectory(str(info_item.data(Qt.ItemDataRole.UserRole).path.parent))
        dialog.fileSelected.connect(set_root_path)
        self.page_options.remember_dialog(dialog, "song_root")
        dialog.open()

    @property
    def langs(self) -> list[str]:
        """返回选择了的歌词类型的列表"""
        return [
            lang
            for checkbox, lang in [
                (self.original_checkBox, "orig"),
                (self.translate_checkBox, "ts"),
                (self.romanized_checkBox, "roma"),
            ]
            if checkbox.isChecked()
        ]

    def get_table_infos(self) -> list[tuple[SongInfo, Path | None]]:
        """获取表格中的文件信息

        :return: 文件信息列表
        """
        infos: list[tuple[SongInfo, Path | None]] = []
        for row in range(self.songs_table.rowCount()):
            item = self.songs_table.item(row, 0)
            if item is not None:
                infos.append((item.data(Qt.ItemDataRole.UserRole), item.data(Qt.ItemDataRole.UserRole + 1)))
        return infos

    @Slot()
    def update_save_paths(self) -> None:
        """更新保存路径"""
        if hasattr(self, "page_options"):
            self.update_selection_paths()
        save_mode = SaveMode(self.save_mode_comboBox.currentIndex())
        file_name_mode = FileNameMode(self.filename_mode_comboBox.currentIndex())
        save2tag_mode = LocalMatchSave2TagMode(self.save2tag_mode_comboBox.currentIndex())
        lyrics_format = LyricsFormat(self.lyricsformat_comboBox.currentIndex())
        langs = self.langs
        file_name_format = cfg["lyrics_file_name_fmt"]

        self.save_path_errors.clear()

        for row in range(self.songs_table.rowCount()):
            info_item = self.songs_table.item(row, 0)
            if not info_item:
                MsgBox.critical(self, self.tr("错误"), self.tr("对应的引索{}不存在").format(row))
                continue
            info: SongInfo = info_item.data(Qt.ItemDataRole.UserRole)
            song_root_path: Path | None = info_item.data(Qt.ItemDataRole.UserRole + 1)
            save_path_text = ""

            if save2tag_mode in (LocalMatchSave2TagMode.ONLY_TAG, LocalMatchSave2TagMode.BOTH) and info.from_cue is False:
                save_path_text += self.tr("保存到标签")

            if info.from_cue is True or save2tag_mode != LocalMatchSave2TagMode.ONLY_TAG:
                save_path = get_local_match_save_path(
                    save_mode=save_mode,
                    file_name_mode=file_name_mode,
                    local_info=info,
                    lyrics_format=lyrics_format,
                    file_name_format=file_name_format,
                    langs=langs,
                    save_root_path=self.save_root_path,
                    allow_placeholder=True,
                    song_root_path=song_root_path,
                )
                if isinstance(save_path, int):
                    match save_path:
                        case -1:
                            save_path = self.tr("需要指定保存路径")
                        case -2:
                            save_path = self.tr("错误(需要歌词信息)")
                        case -3:
                            save_path = self.tr("需要指定歌曲根目录")
                        case _:
                            save_path = self.tr("未知错误")
                    self.save_path_errors.add(save_path)
                save_path_text += f" + {save_path!s}" if save_path_text else str(save_path)

            path_item = QTableWidgetItem(save_path_text)
            path_item.setToolTip(save_path_text)
            self.songs_table.setItem(row, 5, path_item)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        if not self.songs_table.geometry().contains(event.pos()):  # 判断否在表格内点击
            return
        selected_rows = self.songs_table.selectionModel().selectedRows()
        if not selected_rows:
            return
        menu = QMenu(self)
        if not self._matching and self.taskmanager.is_finished("local_match"):
            menu.addAction(self.tr("删除"), lambda rows=selected_rows: [self.songs_table.removeRow(row.row()) for row in reversed(rows)])
            #  反向删除,防止删除行后影响后续行号
            menu.addAction(self.tr("指定根目录"), lambda rows=selected_rows: self.select_root_path([row.row() for row in rows]))
        if len(selected_rows) == 1:
            info_item = self.songs_table.item(selected_rows[0].row(), 0)
            if not info_item:
                return
            menu.addAction(
                self.tr("打开歌曲目录"),
                lambda info_item=info_item: QDesktopServices.openUrl(QUrl.fromLocalFile(str(info_item.data(Qt.ItemDataRole.UserRole).path.parent))),
            )
            menu.addAction(self.tr("在搜索中打开"), lambda info_item=info_item: self.search_song.emit(info_item.data(Qt.ItemDataRole.UserRole)))
            if (
                (completion_status := info_item.data(Qt.ItemDataRole.UserRole + 2))  # 获取完成状态
                and isinstance(completion_status, LocalMatchingStatus)  # 检查是否为字典
                and (save_path := completion_status.path)
            ):  # 获取保存路径
                menu.addAction(self.tr("打开保存目录"), lambda save_path=save_path: QDesktopServices.openUrl(QUrl.fromLocalFile(save_path.parent)))
                menu.addAction(self.tr("打开歌词"), lambda save_path=save_path: QDesktopServices.openUrl(QUrl.fromLocalFile(save_path)))
        menu.exec_(event.globalPos())

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Delete and not self._matching and self.taskmanager.is_finished("local_match"):
            # 获取所有选中的行并删除
            selected_rows = {index.row() for index in self.songs_table.selectionModel().selectedRows()}
            for row in sorted(selected_rows, reverse=True):
                self.songs_table.removeRow(row)
        else:
            super().keyPressEvent(event)
