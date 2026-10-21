# SPDX-FileCopyrightText: Copyright (C) 2024-2025 沉默の金 <cmzj@cmzj.org>
# SPDX-License-Identifier: GPL-3.0-only
"""Offline GUI regression checks for matching completion and failed-row retries."""

import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from time import monotonic
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUTPUT = ROOT / "tests" / "artifacts"
OUTPUT.mkdir(parents=True, exist_ok=True)
temporary = TemporaryDirectory(dir=OUTPUT, ignore_cleanup_errors=True)
paths = ModuleType("LDDC.common.paths")
for name in ("config_dir", "data_dir", "cache_dir", "log_dir", "auto_save_dir", "default_save_lyrics_dir"):
    directory = Path(temporary.name) / name
    directory.mkdir()
    setattr(paths, name, directory)
paths.command_line = None
sys.modules[paths.__name__] = paths

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv)

from LDDC.common.data.cache import cache
from LDDC.common.data.config import cfg
from LDDC.common.exceptions import LyricsNotFoundError
from LDDC.common.models import APIResultList, FileNameMode, Lyrics, SaveMode, SearchInfo, SearchType, SongInfo, Source
from LDDC.common.thread import threadpool
from LDDC.core.auto_fetch import auto_fetch
from LDDC.gui.components.page_layouts import refine_local_match
from LDDC.gui.view.local_match import LocalMatchWidget
from LDDC.gui.workers.local_match import LocalMatchingStatus, LocalMatchingStatusType, LocalMatchSave2TagMode

cfg["local_match_concurrency"] = 1
view = LocalMatchWidget()
refine_local_match(view)
view.resize(1000, 680)
view.show()
view.save_mode_comboBox.setCurrentIndex(SaveMode.SONG.value)
view.filename_mode_comboBox.setCurrentIndex(FileNameMode.SONG.value)
view.save2tag_mode_comboBox.setCurrentIndex(LocalMatchSave2TagMode.ONLY_FILE.value)
infos = [(SongInfo(Source.Local, title=str(i), path=Path(temporary.name) / f"{i}.flac"), None) for i in range(4)]
view.add2table(infos)
assert not view.retry_failed_button.isEnabled()
calls = []
phase = 0


def fetch(info: SongInfo, **_: object) -> SimpleNamespace:
    calls.append(info.title)
    if phase in (1, 2) and "use_cache" in _:
        assert _["use_cache"] is False
    if phase == 0 and info.title == "1":
        raise TimeoutError
    if phase == 0 and info.title == "3":
        raise OSError("simulated save failure")
    if phase == 1 and info.title == "1":
        raise LyricsNotFoundError("still unavailable")
    return SimpleNamespace(
        is_inst=lambda: phase == 0 and info.title == "2",
        to=lambda **_: info.title,
        info=SimpleNamespace(songinfo=info),
    )


def wait_until(predicate) -> None:
    deadline = monotonic() + 10
    while not predicate():
        assert monotonic() < deadline, "Matching did not finish"
        QTest.qWait(10)
    app.processEvents()


def wait_finished() -> None:
    wait_until(lambda: not view._matching and view.taskmanager.is_finished())
    assert view.start_cancel_pushButton.isEnabled()
    assert view.progressBar.maximum() == 1 and view.progressBar.value() == 1


def status(row: int) -> LocalMatchingStatus:
    return view.songs_table.item(row, 0).data(Qt.ItemDataRole.UserRole + 2)


with patch("LDDC.gui.workers.local_match.auto_fetch", side_effect=fetch):
    view.start_cancel_pushButton.click()
    assert not view.retry_failed_button.isEnabled()
    wait_finished()
    assert calls == ["0", "1", "2", "3"]
    assert view.failed_rows() == [1, 3]
    assert view.retry_failed_button.isEnabled()
    assert "匹配完成" in view.status_label.text()
    assert "匹配失败2首" in view.status_label.text()
    original_success, original_skip = status(0), status(2)

    # Retry save failures too, even if an earlier attempt left a partial file.
    phase = 1
    calls.clear()
    view.skip_existing_lyrics_checkbox.setChecked(True)
    (Path(temporary.name) / "3.lrc").write_text("partial", encoding="utf-8")
    view.retry_failed_button.click()
    assert not view.retry_failed_button.isEnabled()
    wait_finished()
    assert calls == ["1", "3"]
    assert view.failed_rows() == [1]
    assert status(0) == original_success and status(2) == original_skip
    assert status(3).status == LocalMatchingStatusType.SUCCESS
    assert status(3).index == 3

    # Removing a row changes the original row indices; retry must use current rows.
    view.songs_table.removeRow(0)
    phase = 2
    calls.clear()
    view.retry_failed_button.click()
    wait_finished()
    assert calls == ["1"] and not view.failed_rows()
    assert status(0).status == LocalMatchingStatusType.SUCCESS
    assert status(0).index == 0
    assert not view.retry_failed_button.isEnabled()
    assert "匹配成功" in view.status_label.text()
    assert view.progressBar.format() == "匹配成功"

# Cancel a retry while a fetch is active. Keep the failed row available for retry.
view.update_status(LocalMatchingStatus(LocalMatchingStatusType.AUTO_FETCH_FAIL, 0, "test"))
started, release = Event(), Event()


def blocking_fetch(info: SongInfo, **_: object) -> SimpleNamespace:
    started.set()
    assert release.wait(10)
    return fetch(info)


with patch("LDDC.gui.workers.local_match.auto_fetch", side_effect=blocking_fetch):
    view.retry_failed_button.click()
    wait_until(started.is_set)
    view.start_cancel_pushButton.click()
    assert not view.retry_failed_button.isEnabled()
    assert not view.start_cancel_pushButton.isEnabled()
    release.set()
    wait_finished()
assert "已取消" in view.status_label.text()
assert view.failed_rows() == [0] and view.retry_failed_button.isEnabled()
with patch("LDDC.gui.workers.local_match.auto_fetch", side_effect=fetch):
    view.retry_failed_button.click()
    wait_finished()
assert not view.failed_rows() and not view.retry_failed_button.isEnabled()
view.update_status(LocalMatchingStatus(LocalMatchingStatusType.SAVE_FAIL, 0, "test"))
assert view.retry_failed_button.isEnabled()
view.songs_table.removeRow(0)
assert not view.retry_failed_button.isEnabled()

# A fresh match must reach the providers even when the cached API is available.
song = SongInfo(Source.QM, title="Fresh search", duration=180000, id="test")
result = APIResultList([song], SearchInfo(Source.QM, song.title, SearchType.SONG, 1), ranges=(1, 1, 1))
lyric = Lyrics(song)
with (
    patch("LDDC.core.auto_fetch.search", side_effect=AssertionError("cached search used")),
    patch("LDDC.core.auto_fetch.get_lyrics", side_effect=AssertionError("cached lyrics used")),
    patch("LDDC.core.auto_fetch.lyrics_api.search", return_value=result) as fresh_search,
    patch("LDDC.core.auto_fetch.lyrics_api.get_lyrics", return_value=lyric) as fresh_lyrics,
):
    assert auto_fetch(song, sources=[Source.QM], use_cache=False) is lyric
    fresh_search.assert_called_once()
    fresh_lyrics.assert_called_once()
view.grab().save(str(OUTPUT / "local-match-completed.png"))
view.hide()
threadpool.waitForDone()
cache.close()
print("Matching GUI checks passed: completion, failed-only retries, row mapping, partial files, deletion and cancellation.")
