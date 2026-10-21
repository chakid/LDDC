# SPDX-FileCopyrightText: Copyright (C) 2024-2025 沉默の金 <cmzj@cmzj.org>
# SPDX-License-Identifier: GPL-3.0-only
"""Verify all four pages retain their options across a separate process restart."""

import json
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from types import ModuleType
from unittest.mock import patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUTPUT = ROOT / "tests" / "artifacts"
OUTPUT.mkdir(parents=True, exist_ok=True)
verify = len(sys.argv) > 1
temporary = None if verify else TemporaryDirectory(dir=OUTPUT, ignore_cleanup_errors=True)
session = Path(sys.argv[1]) if verify else Path(temporary.name)
paths = ModuleType("LDDC.common.paths")
for name in ("config_dir", "data_dir", "cache_dir", "log_dir", "auto_save_dir", "default_save_lyrics_dir"):
    directory = session / name
    directory.mkdir(exist_ok=True)
    setattr(paths, name, directory)
paths.command_line = None
sys.modules[paths.__name__] = paths

from PySide6.QtWidgets import QApplication, QFileDialog

app = QApplication([])

from LDDC.common.data.cache import cache
from LDDC.common.data.config import cfg
from LDDC.gui.view.batch_convert import BatchConvertWidget
from LDDC.gui.view.local_match import LocalMatchWidget
from LDDC.gui.view.open_lyrics import OpenLyricsWidget
from LDDC.gui.view.search import SearchWidget

cfg.write_config()
before = cfg.config_path.read_bytes()
views = [SearchWidget(), LocalMatchWidget(), OpenLyricsWidget(), BatchConvertWidget()]
assert cfg.config_path.read_bytes() == before, "Restoring controls must not rewrite saved options"

if verify:
    expected = json.loads((session / "expected.json").read_text(encoding="utf-8"))
    actual = {view.page_options.name: view.page_options.collect() for view in views}
    assert actual == expected, {key: (actual[key], expected[key]) for key in expected if actual[key] != expected[key]}
    # Translating labels must preserve the selected search type and saved options.
    views[0].retranslateUi()
    actual = {view.page_options.name: view.page_options.collect() for view in views}
    assert actual == expected, {key: (actual[key], expected[key]) for key in expected if actual[key] != expected[key]}
    assert cfg.config_path.read_bytes() == before
    assert not views[1].save_path_errors
    print("Fresh process restored all four pages, source order, paths, and search type.")
else:
    for view in views:
        for name in view.page_options.controls:
            widget = getattr(view, name)
            if name.endswith("comboBox"):
                widget.setCurrentIndex(widget.count() - 1)
            elif name.endswith("checkBox") or name.endswith("checkbox"):
                widget.setChecked(not widget.isChecked())
            elif name.endswith("spinBox"):
                widget.setValue(88 if name == "min_score_spinBox" else 123)
            elif name.endswith("lineEdit"):
                widget.setText(str(session / "output") if name == "save_path_lineEdit" else "saved keyword")
    search, local, opened, batch = views
    search.source_comboBox.setCurrentIndex(1)
    search.search_type_comboBox.setCurrentIndex(search.search_type_comboBox.count() - 1)
    listing = local.source_listWidget
    for index in range(listing.count()):
        checkbox = listing.itemWidget(listing.item(index))
        checkbox.setChecked(not checkbox.isChecked())
    listing.insertItem(0, listing.takeItem(listing.count() - 1))
    listing.data_changed.emit()

    for view in (local, batch):
        with patch.object(QFileDialog, "open"):
            view.select_save_root_path()
        dialog = view.findChildren(QFileDialog)[-1]
        dialog.fileSelected.emit(str(session / "output"))
        assert view.save_root_path == (session / "output").resolve()

    for view in views:
        dialog = QFileDialog(view)
        dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        view.page_options.remember_dialog(dialog, "test_input")
        dialog.filesSelected.emit([str(session / "input" / "example.lrc")])

    expected = {view.page_options.name: view.page_options.collect() for view in views}
    assert json.loads(cfg.config_path.read_text(encoding="utf-8"))["page_options"] == expected
    (session / "expected.json").write_text(json.dumps(expected, ensure_ascii=False), encoding="utf-8")
    subprocess.run([sys.executable, str(Path(__file__).resolve()), str(session.resolve())], check=True, cwd=ROOT)

    # Malformed saved values fall back safely without affecting the other pages.
    cfg.apply_settings({"page_options": {"local_match": {
        "save_mode_comboBox": 999, "min_score_spinBox": "bad", "source_listWidget": {"order": [], "checked": None},
    }}})
    fallback = LocalMatchWidget()
    assert fallback.save_mode_comboBox.currentIndex() == 0
    assert fallback.min_score_spinBox.value() == 60
    assert fallback.source_listWidget.get_data() == ["QM", "KG", "NE"]
    assert not fallback.retry_failed_button.isEnabled()
    print("Page options checks passed: automatic saving, restart, dialog directories, translation and malformed values.")

cache.close()
