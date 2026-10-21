# SPDX-FileCopyrightText: Copyright (C) 2024-2025 沉默の金 <cmzj@cmzj.org>
# SPDX-License-Identifier: GPL-3.0-only
"""Exercise message dialog buttons, dismissal, scrolling, and both palettes offline."""

import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from types import ModuleType

native = '--native' in sys.argv
os.environ['QT_QPA_PLATFORM'] = 'windows' if native else 'offscreen'
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUTPUT = ROOT / 'tests' / 'artifacts' / 'message_dialogs'
OUTPUT.mkdir(parents=True, exist_ok=True)
session = TemporaryDirectory(dir=OUTPUT, ignore_cleanup_errors=True)
paths = ModuleType('LDDC.common.paths')
for name in ('config_dir', 'data_dir', 'cache_dir', 'log_dir', 'auto_save_dir', 'default_save_lyrics_dir'):
    directory = Path(session.name) / name
    directory.mkdir(exist_ok=True)
    setattr(paths, name, directory)
paths.command_line = None
sys.modules[paths.__name__] = paths

from PySide6.QtCore import QCoreApplication, QEvent, QLibraryInfo, Qt, QTranslator
from PySide6.QtGui import QFontDatabase
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox, QScrollArea, QToolButton, QWidget

app = QApplication([])
app.setQuitOnLastWindowClosed(False)
translator = QTranslator()
translator.load('qtbase_zh_CN.qm', QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath))
app.installTranslator(translator)
# The offscreen Windows plugin has no system font discovery.
if sys.platform == 'win32' and not native:
    for filename in ('msyh.ttc', 'msyhbd.ttc', 'segoeui.ttf'):
        QFontDatabase.addApplicationFont(str(Path(os.environ['WINDIR']) / 'Fonts' / filename))

from LDDC.common.data.config import cfg
from LDDC.gui.components.msg_box import MsgBox, _msg_boxs
from LDDC.gui.components.theme import apply_theme

parent = QWidget()
parent.resize(1000, 700)
parent.show()
app.processEvents()


def flush():
    app.processEvents()
    if native:
        QTest.qWait(80)
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


for scheme in ('light', 'dark'):
    dict.__setitem__(cfg, 'color_scheme', scheme)
    apply_theme(parent)
    for kind in ('warning', 'critical', 'information'):
        getattr(MsgBox, kind)(parent, '警告' if kind == 'warning' else '提示', '请先下载并预览歌词')
        flush()
        dialog = _msg_boxs[-1][0]
        assert dialog.isVisible()
        assert dialog.windowModality() == Qt.WindowModality.WindowModal
        assert dialog.windowFlags() & Qt.WindowType.FramelessWindowHint
        assert not dialog.windowFlags() & Qt.WindowType.WindowTitleHint
        assert dialog.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        assert dialog.frameGeometry() == dialog.geometry(), 'No native title bar or outer frame'
        assert dialog.defaultButton().property('role') == 'primary'
        assert dialog.findChild(QLabel, 'messageTitle').text() == dialog.windowTitle()
        for button in dialog.buttons():
            assert button.parentWidget().rect().contains(button.geometry()), 'Buttons must not be clipped'
        preview = dialog.grab()
        assert preview.toImage().pixelColor(0, 0).alpha() == 0, 'The card margin must remain transparent'
        preview.save(str(OUTPUT / f'{"native_" if native else ""}{scheme}_{kind}.png'))
        if native:
            import ctypes

            get_style = ctypes.windll.user32.GetWindowLongW
            get_style.argtypes = [ctypes.c_void_p, ctypes.c_int]
            get_style.restype = ctypes.c_long
            hwnd = int(dialog.winId())
            assert get_style(hwnd, -16) & 0x00C00000 == 0, 'Windows must not add WS_CAPTION'
            assert get_style(hwnd, -20) & 0x00080000, 'Windows alpha requires WS_EX_LAYERED'
        print(scheme, kind, dialog.size().toTuple())
        dialog.defaultButton().click()
        flush()
        assert not _msg_boxs

    answers = []
    MsgBox.question(parent, '退出匹配', '正在匹配歌词，是否退出？',
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No, answers.append)
    flush()
    dialog = _msg_boxs[-1][0]
    dialog.grab().save(str(OUTPUT / f'{scheme}_question.png'))
    QTest.keyClick(dialog, Qt.Key.Key_Return)
    flush()
    assert answers == [QMessageBox.StandardButton.No]
    assert not _msg_boxs

    answers.clear()
    MsgBox.question(parent, '退出匹配', '正在匹配歌词，是否退出？',
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No, answers.append)
    flush()
    _msg_boxs[-1][0].button(QMessageBox.StandardButton.Yes).click()
    flush()
    assert answers == [QMessageBox.StandardButton.Yes]
    assert not _msg_boxs

    for dismiss in ('escape', 'close'):
        answers.clear()
        MsgBox.question(parent, '退出匹配', '正在匹配歌词，是否退出？',
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No, answers.append)
        flush()
        dialog = _msg_boxs[-1][0]
        if dismiss == 'escape':
            QTest.keyClick(dialog, Qt.Key.Key_Escape)
        else:
            dialog.findChild(QToolButton, 'messageClose').click()
        flush()
        assert answers == [QMessageBox.StandardButton.No], (dismiss, answers)
        assert not _msg_boxs

    MsgBox.warning(parent, '部分歌曲无法处理', '\n'.join(f'{i}: C:/Music/专辑/较长的歌曲文件名.flac' for i in range(90)))
    flush()
    dialog = _msg_boxs[-1][0]
    area = dialog.findChild(QScrollArea)
    assert area is not None and area.verticalScrollBar().maximum() > 0
    assert parent.screen().availableGeometry().contains(dialog.frameGeometry())
    dialog.grab().save(str(OUTPUT / f'{scheme}_long.png'))
    dialog.close()
    flush()
    assert not _msg_boxs

MsgBox.information(None, '提示', '歌词保存成功')
flush()
assert _msg_boxs[-1][0].windowModality() == Qt.WindowModality.NonModal
_msg_boxs[-1][0].close()
flush()
assert not _msg_boxs
for size in (9, 12):
    dict.__setitem__(cfg, 'ui_font_size', size)
    MsgBox.warning(parent, '文件读取失败', 'C:/' + '较长的文件路径' * 120 + '.flac')
    flush()
    dialog = _msg_boxs[-1][0]
    area = dialog.findChild(QScrollArea)
    assert area is not None and area.verticalScrollBar().maximum() > 0
    assert parent.screen().availableGeometry().contains(dialog.frameGeometry())
    dialog.close()
    flush()
    assert not _msg_boxs
parent.close()
session.cleanup()
print('Passed: both palettes, all message types, default button, Escape, close, long content, and standalone cleanup.')
