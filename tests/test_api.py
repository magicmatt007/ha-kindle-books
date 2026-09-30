"""Tests for the Goodreads feed parser (no Home Assistant needed)."""

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
_spec = importlib.util.spec_from_file_location(
    "kindle_books_api", ROOT / "custom_components/kindle_books/api.py"
)
api = importlib.util.module_from_spec(_spec)
sys.modules["kindle_books_api"] = api
_spec.loader.exec_module(api)

FIXTURE = (Path(__file__).parent / "fixtures/read_shelf.xml").read_text()


def test_parse_feed_full_item():
    book = api.parse_feed(FIXTURE)[0]
    assert book.book_id == "54493401"
    assert book.title == "Project Hail Mary"
    assert book.author == "Andy Weir"
    assert book.cover == "https://i.gr-assets.com/phm._SY475_.jpg"
    assert book.pages == 476
    assert book.user_rating == 5
    assert book.average_rating == 4.52
    assert book.read_at == datetime(2026, 9, 13, tzinfo=timezone.utc)
    assert book.as_dict()["read_at"] == "2026-09-13T00:00:00+00:00"


def test_parse_feed_sparse_item():
    book = api.parse_feed(FIXTURE)[1]
    assert book.cover == "https://i.gr-assets.com/dune.jpg"  # falls back to small
    assert book.pages is None
    assert book.isbn is None
    assert book.user_rating is None  # 0 means unrated
    assert book.read_at is None
    assert book.added_at is not None


def test_parse_feed_invalid():
    with pytest.raises(api.GoodreadsError):
        api.parse_feed("<html>not rss")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("12345", "12345"),
        (" 12345 ", "12345"),
        ("https://www.goodreads.com/user/show/12345-matt", "12345"),
        ("https://www.goodreads.com/review/list/12345-matt?shelf=read", "12345"),
    ],
)
def test_parse_user_id(value, expected):
    assert api.parse_user_id(value) == expected


def test_parse_rss_link():
    link = "https://www.goodreads.com/review/list_rss/12345?key=AbC-123_x&shelf=%23ALL%23"
    assert api.parse_user_id(link) == "12345"
    assert api.parse_feed_key(link) == "AbC-123_x"
    assert api.parse_feed_key("https://www.goodreads.com/user/show/12345-matt") is None


def test_parse_user_id_invalid():
    with pytest.raises(ValueError):
        api.parse_user_id("matt")


class _FakeResp:
    def __init__(self, status, body):
        self.status, self._body = status, body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def raise_for_status(self):
        pass

    async def text(self):
        return self._body


class _FakeSession:
    def __init__(self, pages, status=200):
        self.pages, self.status, self.calls = pages, status, []

    def get(self, url, params, timeout):
        self.calls.append(params)
        page = int(params["page"])
        body = self.pages[page - 1] if page <= len(self.pages) else "<rss><channel/></rss>"
        return _FakeResp(self.status, body)


async def test_get_shelf_paginates_until_empty():
    session = _FakeSession([FIXTURE])
    books = await api.GoodreadsClient(session, "1").get_shelf("read")
    assert [b.title for b in books] == ["Project Hail Mary", "Dune"]
    assert [c["page"] for c in session.calls] == ["1", "2"]


async def test_get_shelf_stops_on_repeated_page():
    session = _FakeSession([FIXTURE, FIXTURE, FIXTURE])
    books = await api.GoodreadsClient(session, "1").get_shelf("read")
    assert len(books) == 2
    assert len(session.calls) == 2


async def test_get_shelf_sends_key():
    session = _FakeSession([FIXTURE])
    await api.GoodreadsClient(session, "1", "secret").get_shelf("read")
    assert all(c["key"] == "secret" for c in session.calls)


async def test_get_shelf_not_found():
    session = _FakeSession([], status=404)
    with pytest.raises(api.GoodreadsUserNotFound):
        await api.GoodreadsClient(session, "1").get_shelf("read")
