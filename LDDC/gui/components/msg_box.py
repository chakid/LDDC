# SPDX-FileCopyrightText: Copyright (C) 2024-2025 沉默の金 <cmzj@cmzj.org>
# SPDX-License-Identifier: GPL-3.0-only

# 非堵塞的消息框
import contextlib
from collections.abc import Callable, Iterable
from typing import Any

from PySide6.QtCore import QCoreApplication, QObject, Qt, Slot
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QAbstractButton, QMessageBox, QWidget

from LDDC.gui.components.message_dialog import MessageDialog

_msg_boxs: list[tuple[QMessageBox, QWidget | None, Callable | None]] = []


@Slot(QAbstractButton)
def button_clicked(button: QAbstractButton) -> None:
    """处理消息框的按钮点击事件的槽函数

    :param button: 按钮
    """
    msg_box = button.window()
    if not isinstance(msg_box, QMessageBox):
        return

    for box, parent, func in _msg_boxs:
        if box == msg_box:
            break
    else:
        return
    if isinstance(parent, QWidget):
        parent.setFocus()
    if isinstance(func, Callable):
        with contextlib.suppress(Exception):
            func(msg_box.standardButton(button))


def _release_msg_box(msg: QMessageBox) -> None:
    """Release boxes on every exit path, including Escape and the close button."""
    for index, (box, _, _) in enumerate(_msg_boxs):
        if box is msg:
            _msg_boxs.pop(index)
            break
    msg.deleteLater()


class MsgBox(QObject):
    @staticmethod
    def init_msg_box(parent: QWidget | None, title: str, text: str) -> QMessageBox:
        """初始化消息框"""
        msg = MessageDialog(parent)
        msg.setWindowIcon(QIcon(":/LDDC/img/icon/logo.png"))
        if parent is not None:
            msg.setWindowModality(Qt.WindowModality.WindowModal)
        else:
            msg.setWindowModality(Qt.WindowModality.NonModal)
        msg.setWindowTitle(title)
        msg.setText(text)
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.setDefaultButton(QMessageBox.StandardButton.Ok)
        msg.buttonClicked.connect(button_clicked)
        msg.finished.connect(lambda _: _release_msg_box(msg))
        return msg

    @staticmethod
    def information(parent: QWidget | None, title: str, text: str) -> None:
        """创建一个信息消息框

        :param parent: 父窗口
        :param title: 标题
        :param text: 内容
        """
        msg = MsgBox.init_msg_box(parent, title, text)
        msg.setIcon(QMessageBox.Icon.Information)
        _msg_boxs.append((msg, parent, None))
        msg.show()

    @staticmethod
    def warning(parent: QWidget | None, title: str, text: str) -> None:
        """创建一个警告消息框

        :param parent: 父窗口
        :param title: 标题
        :param text: 内容
        """
        msg = MsgBox.init_msg_box(parent, title, text)
        msg.setIcon(QMessageBox.Icon.Warning)
        _msg_boxs.append((msg, parent, None))
        msg.show()

    @staticmethod
    def critical(parent: QWidget | None, title: str, text: str) -> None:
        """创建一个错误消息框

        :param parent: 父窗口
        :param title: 标题
        :param text: 内容
        """
        msg = MsgBox.init_msg_box(parent, title, text)
        msg.setIcon(QMessageBox.Icon.Critical)
        _msg_boxs.append((msg, parent, None))
        msg.show()

    @staticmethod
    def error(parent: QWidget | None, e: Exception | Iterable[Exception], title: str | None = None, msg: str = "") -> None:
        """创建一个错误消息框

        :param parent: 父窗口
        :param e: 错误
        :param title: 标题
        :param msg: 消息
        """
        title = title if title else QCoreApplication.translate("MsgBox", "错误")
        MsgBox.critical(parent, title, "".join((f"{msg}\n" if msg else "") + f"{e.__class__.__name__}: {e!s}" for e in (e,) if e))

    @staticmethod
    def get_error_slot(parent: QWidget | None, title: str | None = None, msg: str = "") -> Callable[[Exception], None]:
        """创建一个创建错误消息框的槽函数

        :param parent: 父窗口
        :param title: 标题
        :param msg: 消息
        """

        def error_slot(e: Exception) -> None:
            MsgBox.error(parent, e, title, msg)

        return error_slot

    @staticmethod
    def question(
        parent: QWidget | None,
        title: str,
        text: str,
        button0: QMessageBox.StandardButton,
        button1: QMessageBox.StandardButton,
        func: Callable[[QMessageBox.StandardButton], Any],
    ) -> None:
        """创建一个询问消息框

        :param parent: 父窗口
        :param title: 标题
        :param text: 内容
        :param button0: 所有按键
        :param button1: 默认按键
        :param func: 按键回调函数,调用时会按键类型
        """
        msg = MsgBox.init_msg_box(parent, title, text)
        msg.setIcon(QMessageBox.Icon.Question)
        msg.setStandardButtons(button0)
        msg.setDefaultButton(button1)
        _msg_boxs.append((msg, parent, func))
        msg.show()
