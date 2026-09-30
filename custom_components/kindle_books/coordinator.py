"""Data update coordinator for Kindle Books."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import Book, GoodreadsClient, GoodreadsError
from .const import (
    CONF_READ_SHELF,
    CONF_READING_SHELF,
    CONF_SCAN_INTERVAL,
    DEFAULT_READ_SHELF,
    DEFAULT_READING_SHELF,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class ReadingData:
    """Books on the tracked shelves."""

    read: list[Book]
    reading: list[Book]


class KindleBooksCoordinator(DataUpdateCoordinator[ReadingData]):
    """Poll the Goodreads shelves."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: GoodreadsClient
    ) -> None:
        interval = timedelta(
            minutes=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=max(interval, MIN_SCAN_INTERVAL),
        )
        self.client = client
        self.entry = entry

    def _shelf(self, key: str, default: str) -> str:
        return self.entry.options.get(key, self.entry.data.get(key, default))

    async def _async_update_data(self) -> ReadingData:
        try:
            read = await self.client.get_shelf(
                self._shelf(CONF_READ_SHELF, DEFAULT_READ_SHELF)
            )
            reading = await self.client.get_shelf(
                self._shelf(CONF_READING_SHELF, DEFAULT_READING_SHELF)
            )
        except GoodreadsError as err:
            raise UpdateFailed(str(err)) from err

        # Most recently finished first; books without a read date go last.
        read.sort(
            key=lambda b: (b.read_at or b.added_at).timestamp()
            if (b.read_at or b.added_at)
            else 0,
            reverse=True,
        )
        # Most recently started first.
        reading.sort(
            key=lambda b: b.added_at.timestamp() if b.added_at else 0, reverse=True
        )
        return ReadingData(read=read, reading=reading)
