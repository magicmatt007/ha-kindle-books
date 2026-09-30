"""Client for Goodreads shelf RSS feeds.

Amazon has no public Kindle API, but Kindle syncs reading activity to
Goodreads (owned by Amazon), and every Goodreads shelf is exposed as an
RSS feed. This module has no Home Assistant imports so it can be tested
on its own.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any

import aiohttp

FEED_URL = "https://www.goodreads.com/review/list_rss/{user_id}"
MAX_PAGES = 20
USER_ID_RE = re.compile(
    r"(?:goodreads\.com/(?:user/show|review/list|review/list_rss)/)?(\d+)"
)
KEY_RE = re.compile(r"[?&;]key=([A-Za-z0-9_-]+)")  # ";" covers "&amp;" from page source


class GoodreadsError(Exception):
    """Base error."""


class GoodreadsUserNotFound(GoodreadsError):
    """The user does not exist, or the profile is private and no key was given."""


@dataclass
class Book:
    """A book entry on a shelf."""

    book_id: str
    title: str
    author: str
    cover: str | None
    link: str | None
    isbn: str | None
    pages: int | None
    published: str | None
    average_rating: float | None
    user_rating: int | None
    read_at: datetime | None
    added_at: datetime | None

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable dict for state attributes."""
        data = asdict(self)
        for key in ("read_at", "added_at"):
            if data[key] is not None:
                data[key] = data[key].isoformat()
        return data


def parse_user_id(value: str) -> str:
    """Accept a numeric id or a Goodreads profile URL and return the id."""
    match = USER_ID_RE.search(value.strip())
    if not match:
        raise ValueError(f"Could not find a Goodreads user id in {value!r}")
    return match.group(1)


def parse_feed_key(value: str) -> str | None:
    """Return the private feed key from a Goodreads RSS link, if present.

    Goodreads adds a secret ``key`` to the RSS links on your own "My Books"
    page. With it the feed can be read even when the profile is private.
    """
    match = KEY_RE.search(value.strip())
    return match.group(1) if match else None


def _text(item: ET.Element, tag: str) -> str | None:
    el = item.find(tag)
    if el is None or el.text is None:
        return None
    text = el.text.strip()
    return text or None


def _date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None


def _int(value: str | None) -> int | None:
    try:
        return int(value) if value else None
    except ValueError:
        return None


def _float(value: str | None) -> float | None:
    try:
        return float(value) if value else None
    except ValueError:
        return None


def parse_feed(xml_text: str) -> list[Book]:
    """Parse a Goodreads shelf RSS document into books."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as err:
        raise GoodreadsError(f"Invalid RSS feed: {err}") from err

    books: list[Book] = []
    for item in root.iter("item"):
        cover = (
            _text(item, "book_large_image_url")
            or _text(item, "book_medium_image_url")
            or _text(item, "book_image_url")
        )
        books.append(
            Book(
                book_id=_text(item, "book_id") or _text(item, "guid") or "",
                title=_text(item, "title") or "Unknown title",
                author=_text(item, "author_name") or "Unknown author",
                cover=cover,
                link=_text(item, "link"),
                isbn=_text(item, "isbn"),
                pages=_int(_text(item, "book/num_pages")),
                published=_text(item, "book_published"),
                average_rating=_float(_text(item, "average_rating")),
                user_rating=_int(_text(item, "user_rating")) or None,
                read_at=_date(_text(item, "user_read_at")),
                added_at=_date(_text(item, "user_date_added")),
            )
        )
    return books


class GoodreadsClient:
    """Fetch shelves for one Goodreads user."""

    def __init__(
        self, session: aiohttp.ClientSession, user_id: str, key: str | None = None
    ) -> None:
        self._session = session
        self.user_id = user_id
        self._key = key

    async def _fetch_page(self, shelf: str, page: int) -> str:
        url = FEED_URL.format(user_id=self.user_id)
        params = {"shelf": shelf, "page": str(page)}
        if self._key:
            params["key"] = self._key
        try:
            async with self._session.get(
                url, params=params, timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status in (401, 403, 404):
                    raise GoodreadsUserNotFound(self.user_id)
                resp.raise_for_status()
                return await resp.text()
        except aiohttp.ClientError as err:
            # Don't include the URL: it can carry the private feed key.
            status = getattr(err, "status", None)
            detail = f"HTTP {status}" if status else type(err).__name__
            raise GoodreadsError(f"Error fetching shelf {shelf!r}: {detail}") from None

    async def get_shelf(self, shelf: str, max_pages: int = MAX_PAGES) -> list[Book]:
        """Return every book on a shelf, following pagination."""
        books: list[Book] = []
        seen: set[str] = set()
        for page in range(1, max_pages + 1):
            page_books = [
                b for b in parse_feed(await self._fetch_page(shelf, page))
                if b.book_id not in seen
            ]
            if not page_books:
                break
            seen.update(b.book_id for b in page_books)
            books.extend(page_books)
        return books
