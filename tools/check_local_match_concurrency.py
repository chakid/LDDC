# SPDX-FileCopyrightText: Copyright (C) 2024-2025 沉默の金 <cmzj@cmzj.org>
# SPDX-License-Identifier: GPL-3.0-only
"""Offline checks for local matching, isolated from the user's configuration."""

import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier, Lock
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
temporary = TemporaryDirectory()
paths = ModuleType("LDDC.common.paths")
for name in ("config_dir", "data_dir", "cache_dir", "log_dir", "auto_save_dir", "default_save_lyrics_dir"):
    directory = Path(temporary.name) / name
    directory.mkdir()
    setattr(paths, name, directory)
paths.command_line = None
sys.modules[paths.__name__] = paths

from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer

app = QCoreApplication(sys.argv)

from LDDC.common.data.cache import cache
from LDDC.common.data.config import cfg
from LDDC.common.exceptions import LyricsNotFoundError
from LDDC.common.models import FileNameMode, LyricsFormat, SaveMode, SongInfo, Source
from LDDC.common.task_manager import TaskManager
from LDDC.common.thread import in_other_thread, threadpool
from LDDC.gui.workers.local_match import LocalMatchingStatusType, LocalMatchSave2TagMode, LocalMatchWorker


def make_worker(concurrency: int, count: int) -> LocalMatchWorker:
    cfg["local_match_concurrency"] = concurrency
    worker = LocalMatchWorker(
        infos_root_paths=[(SongInfo(Source.Local, title=str(i), path=Path(temporary.name) / f"{i}.flac"), None) for i in range(count)],
        save_mode=SaveMode.SPECIFY,
        file_name_mode=FileNameMode.SONG,
        save2tag_mode=LocalMatchSave2TagMode.ONLY_FILE,
        lyrics_format=LyricsFormat(0),
        langs=["orig"],
        save_root_path=Path(temporary.name),
        min_score=60,
        sources=[Source.QM],
        skip_existing_lyrics=False,
    )
    worker.taskmanager = TaskManager({"match": []})
    worker.task_type = "match"
    worker.taskid = worker.taskmanager.add_task("match")
    return worker


def lyrics(info: SongInfo, instrumental: bool = False) -> SimpleNamespace:
    return SimpleNamespace(is_inst=lambda: instrumental, to=lambda **_: info.title, info=SimpleNamespace(songinfo=info))


def run(worker: LocalMatchWorker) -> tuple[list, list]:
    statuses, totals = [], []
    worker.progress.connect(lambda text, value, maximum, status: statuses.append((value, status)) if status else None)
    worker.finished.connect(lambda *counts: totals.append(counts))
    worker.run_task()
    app.processEvents()
    return statuses, totals


# Exercise Qt event loops and callbacks into the song threads, as auto_fetch does.
for concurrency in (1, 5, 20):
    worker = make_worker(concurrency, concurrency * 2)
    barrier = Barrier(concurrency)
    lock = Lock()
    state = {"active": 0, "peak": 0}

    def fetch(info: SongInfo, **_: object) -> SimpleNamespace:
        with lock:
            state["active"] += 1
            state["peak"] = max(state["peak"], state["active"])
        barrier.wait(timeout=5)
        loop = QEventLoop()
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(loop.quit)
        timer.start(5000)
        result = []

        def done(value: SimpleNamespace) -> None:
            result.append(value)
            loop.quit()

        in_other_thread(lambda: lyrics(info), done, lambda error: loop.quit())
        loop.exec()
        timer.stop()
        assert result, "Network callback could not return to the song's Qt event loop"
        with lock:
            state["active"] -= 1
        return result[0]

    with patch("LDDC.gui.workers.local_match.auto_fetch", side_effect=fetch):
        statuses, totals = run(worker)
    assert state["peak"] == concurrency
    assert totals == [(concurrency * 2, concurrency * 2, 0, 0)], totals
    assert [value for value, _ in statuses] == list(range(1, concurrency * 2 + 1))
    assert {status.index for _, status in statuses} == set(range(concurrency * 2))
    for _, status in statuses:
        assert status.path.read_text() == str(status.index)

# Error/skip results remain attached to their original rows when completed out of order.
worker = make_worker(5, 5)
worker.skip_existing_lyrics = True


def mixed_fetch(info: SongInfo, **_: object) -> SimpleNamespace:
    if info.title == "1":
        raise LyricsNotFoundError("test")
    if info.title == "2":
        raise TimeoutError
    return lyrics(info, instrumental=info.title == "3")


with (
    patch("LDDC.gui.workers.local_match.auto_fetch", side_effect=mixed_fetch),
    patch.object(worker, "check_skip_existing_lyrics", side_effect=lambda info, _: info.title == "0"),
):
    statuses, totals = run(worker)
assert totals == [(5, 1, 2, 2)], totals
assert {status.index: status.status for _, status in statuses} == {
    0: LocalMatchingStatusType.SKIP_EXISTING,
    1: LocalMatchingStatusType.AUTO_FETCH_FAIL,
    2: LocalMatchingStatusType.AUTO_FETCH_FAIL,
    3: LocalMatchingStatusType.SKIP_INST,
    4: LocalMatchingStatusType.SUCCESS,
}

# Cancel during downloads: drain active work, don't save or start the remaining songs.
worker = make_worker(5, 30)
barrier = Barrier(5)
calls = []


def cancel_fetch(info: SongInfo, **_: object) -> SimpleNamespace:
    with lock:
        calls.append(info.title)
        if len(calls) == 5:
            worker.taskmanager.cancel()
    barrier.wait(timeout=5)
    return lyrics(info)


with (
    patch("LDDC.gui.workers.local_match.auto_fetch", side_effect=cancel_fetch),
    patch("LDDC.gui.workers.local_match.get_local_match_save_path") as save_path,
    patch("LDDC.gui.workers.local_match.write_lyrics") as write,
):
    statuses, totals = run(worker)
assert len(calls) == 5
assert not statuses and totals == [(0, 0, 0, 0)]
write.assert_not_called()
save_path.assert_not_called()
assert make_worker(100, 0).concurrency == 20
assert make_worker(0, 0).concurrency == 1
assert run(make_worker(5, 0))[1] == [(0, 0, 0, 0)]
threadpool.waitForDone()
cache.close()
print("Local matching checks passed: concurrency 1/5/20, Qt callbacks, saved files, progress, skips, failures and cancellation.")
