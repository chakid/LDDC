# SPDX-FileCopyrightText: Copyright (C) 2026 LDDC contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Offline regression checks for search provider failures and QQ sessions."""

import atexit
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic
from types import ModuleType
from unittest.mock import patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"
for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
    os.environ.pop(name, None)
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

import httpx
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from LDDC.common.data.cache import cache
from LDDC.common.data.cache import _atexit as close_cache
from LDDC.common.data.config import cfg
from LDDC.common.exceptions import APIRequestError
from LDDC.common.models import APIResultList, SearchInfo, SearchType, SongInfo, Source
from LDDC.common.thread import threadpool
from LDDC.core.api.lyrics import LyricsAPI
from LDDC.core.api.lyrics.kg import KGAPI
from LDDC.core.api.lyrics.ne import NEAPI
from LDDC.core.api.lyrics.qm import QMAPI
from LDDC.gui.view.search import SearchWidgetBase

app = QApplication.instance() or QApplication([])

# Constructing the dispatcher must not request a QQ session for unrelated sources.
with (
    patch.object(KGAPI, "init"),
    patch.object(NEAPI, "init"),
    patch.object(QMAPI, "init", side_effect=AssertionError("eager QQ initialization")),
):
    dispatcher = LyricsAPI()
    dispatcher.init()
    expected = APIResultList([], SearchInfo(Source.KG, "知足", SearchType.SONG, 1))
    with patch.object(dispatcher.cloud_apis[Source.KG], "search", return_value=expected):
        assert dispatcher.search(Source.KG, "知足", SearchType.SONG) is expected

# A failed session remains retryable; a successful one is reused on later requests.
requests = []


def respond(request: httpx.Request) -> httpx.Response:
    import json

    method = json.loads(request.content)["request"]["method"]
    requests.append(method)
    if requests == ["GetSession"]:
        return httpx.Response(200, json={"code": 2001})
    data = {"session": {"uid": "test", "sid": "test", "userip": "127.0.0.1"}} if method == "GetSession" else {}
    return httpx.Response(200, json={"code": 0, "request": {"code": 0, "data": data}})


qm = QMAPI()
qm.client.close()
qm.client = httpx.Client(transport=httpx.MockTransport(respond))
try:
    qm.request("Search", "test", {})
except APIRequestError:
    pass
else:
    raise AssertionError("QQ session failure was swallowed")
assert not qm.inited
qm.request("Search", "test", {})
qm.request("Search", "test", {})
assert qm.inited
assert requests == ["GetSession", "GetSession", "Search", "Search"]
qm.client.close()

view = SearchWidgetBase()
view.search_keyword_lineEdit.setText("知足")
cfg["multi_search_sources"] = ["QM", "KG"]
phase = "partial"


def search(source: Source, keyword: str, search_type: SearchType, page: int = 1) -> APIResultList:
    if source == Source.QM or phase == "all_failed":
        raise APIRequestError("qm API请求错误,错误码:2001")
    songs = [SongInfo(source=source, title=keyword)] if phase != "empty" else []
    return APIResultList(songs, SearchInfo(source, keyword, search_type, page), (0, len(songs) - 1, len(songs)))


def wait_finished(task_type: str = "search") -> None:
    deadline = monotonic() + 10
    while not view.task_manager.is_finished(task_type):
        assert monotonic() < deadline, "Search did not finish"
        QTest.qWait(10)
    app.processEvents()


with (
    patch("LDDC.gui.view.search.search", side_effect=search),
    patch("LDDC.gui.view.search.MsgBox.error") as error,
    patch("LDDC.gui.view.search.MsgBox.warning") as warning,
):
    view.search()
    wait_finished()
    assert view.results_tableWidget.rowCount() == 1
    assert view.search_pushButton.isEnabled()
    error.assert_not_called()

    phase = "all_failed"
    view.search()
    wait_finished()
    assert view.results_tableWidget.rowCount() == 0
    assert view.search_pushButton.isEnabled()
    assert error.call_count == 1
    assert isinstance(error.call_args.args[1], APIRequestError)
    warning.assert_not_called()

    # A single selected source must still report its real failure.
    cfg["multi_search_sources"] = ["QM"]
    error.reset_mock()
    view.search()
    wait_finished()
    assert error.call_count == 1
    assert view.search_pushButton.isEnabled()
    cfg["multi_search_sources"] = ["QM", "KG"]

    phase = "empty"
    error.reset_mock()
    view.search()
    wait_finished()
    error.assert_not_called()
    assert warning.call_count == 1

    # Pagination failures must remove the loading row and display an exception.
    view.path = [APIResultList(
        [SongInfo(source=Source.QM, title="知足")],
        SearchInfo(Source.QM, "知足", SearchType.SONG, 1),
        (0, 0, 2),
    )]
    view.results_tableWidget.setRowCount(1)
    view._check_search_more()
    wait_finished("search_more")
    assert error.call_count == 1
    assert isinstance(error.call_args.args[1], APIRequestError)
    assert view.results_tableWidget.rowCount() == 1

threadpool.waitForDone(10000)
view.close()
for api in dispatcher.cloud_apis.values():
    client = getattr(api, "client", None)
    if isinstance(client, httpx.Client):
        client.close()
atexit.unregister(close_cache)
close_cache()
temporary.cleanup()
print("PASS: provider isolation, QQ session retry/reuse, partial/all/empty search results, pagination failure")
