# SPDX-FileCopyrightText: Copyright (C) 2024-2025 沉默の金 <cmzj@cmzj.org>
# SPDX-License-Identifier: GPL-3.0-only
"""Persist explicitly selected page controls independently of transient task data."""

from pathlib import Path

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QCheckBox, QComboBox, QFileDialog, QLineEdit, QSpinBox, QWidget

from LDDC.common.data.config import cfg
from LDDC.common.logger import logger
from LDDC.gui.components.custom_widgets import CheckBoxListWidget
from LDDC.gui.components.msg_box import MsgBox


class PageOptions(QObject):
    def __init__(self, view: QWidget, name: str, controls: tuple[str, ...], paths: tuple[str, ...] = ()) -> None:
        super().__init__(view)
        self.view = view
        self.name = name
        self.controls = controls
        self.paths = paths
        self.loading = True
        state = cfg["page_options"].get(name, {})
        self.directories = state.get("directories", {}) if isinstance(state, dict) else {}
        if not isinstance(self.directories, dict):
            self.directories = {}
        self.restore(state)
        for name in controls:
            widget = getattr(view, name)
            if isinstance(widget, QComboBox):
                widget.currentIndexChanged.connect(self.save)
            elif isinstance(widget, QCheckBox):
                widget.toggled.connect(self.save)
            elif isinstance(widget, QSpinBox):
                widget.valueChanged.connect(self.save)
            elif isinstance(widget, QLineEdit):
                widget.textChanged.connect(self.save)
            elif isinstance(widget, CheckBoxListWidget):
                widget.data_changed.connect(self.save)
        self.loading = False

    def restore(self, state: dict) -> None:
        if not isinstance(state, dict):
            return
        for name in self.paths:
            value = state.get(name)
            if isinstance(value, str):
                setattr(self.view, name, Path(value) if value else None)
        for name in self.controls:
            widget, value = getattr(self.view, name), state.get(name)
            if isinstance(widget, QComboBox) and type(value) is int and 0 <= value < widget.count():
                widget.setCurrentIndex(value)
            elif isinstance(widget, QCheckBox) and type(value) is bool:
                widget.setChecked(value)
            elif isinstance(widget, QSpinBox) and type(value) is int and widget.minimum() <= value <= widget.maximum():
                widget.setValue(value)
            elif isinstance(widget, QLineEdit) and isinstance(value, str):
                widget.setText(value)
            elif isinstance(widget, CheckBoxListWidget) and isinstance(value, dict):
                checked, order = value.get("checked"), value.get("order")
                if not isinstance(checked, list) or not isinstance(order, list):
                    continue
                allowed = widget.get_order()
                order = list(dict.fromkeys(item for item in order if isinstance(item, str) and item in allowed))
                widget.set_soures(order + [item for item in allowed if item not in order])
                for index in range(widget.count()):
                    widget.itemWidget(widget.item(index)).setChecked(widget.get_order()[index] in checked)

    def collect(self) -> dict:
        state = {"directories": dict(self.directories)}
        for name in self.paths:
            value = getattr(self.view, name)
            state[name] = str(value) if value is not None else ""
        for name in self.controls:
            widget = getattr(self.view, name)
            if isinstance(widget, QComboBox):
                state[name] = widget.currentIndex()
            elif isinstance(widget, QCheckBox):
                state[name] = widget.isChecked()
            elif isinstance(widget, QSpinBox):
                state[name] = widget.value()
            elif isinstance(widget, QLineEdit):
                state[name] = widget.text()
            elif isinstance(widget, CheckBoxListWidget):
                state[name] = {"checked": widget.get_data(), "order": widget.get_order()}
        return state

    def save(self, *_args: object) -> None:
        if self.loading:
            return
        pages = dict(cfg["page_options"])
        pages[self.name] = self.collect()
        try:
            cfg.apply_settings({"page_options": pages})
        except OSError as error:
            logger.exception("保存页面选项失败")
            MsgBox.warning(self.view, self.tr("保存选项失败"), str(error))

    def remember_dialog(self, dialog: QFileDialog, key: str) -> None:
        directory = self.directories.get(key)
        if isinstance(directory, str) and directory:
            dialog.setDirectory(directory)

        def selected(paths: list[str]) -> None:
            if paths:
                path = Path(paths[0])
                self.directories[key] = str(path if dialog.fileMode() == QFileDialog.FileMode.Directory else path.parent)
                self.save()

        dialog.filesSelected.connect(selected)
