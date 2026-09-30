"""Sensors for Kindle Books."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import KindleBooksConfigEntry
from .api import Book
from .const import CONF_MAX_BOOKS, CONF_USER_ID, DEFAULT_MAX_BOOKS, DOMAIN
from .coordinator import KindleBooksCoordinator, ReadingData

MAX_STATE_LEN = 255


def _title(book: Book | None) -> str | None:
    return book.title[:MAX_STATE_LEN] if book else None


def _read_this_year(data: ReadingData) -> list[Book]:
    year = dt_util.now().year
    return [b for b in data.read if b.read_at and b.read_at.year == year]


@dataclass(frozen=True, kw_only=True)
class KindleSensorDescription(SensorEntityDescription):
    """Describes a Kindle Books sensor."""

    value_fn: Callable[[ReadingData], Any]
    book_fn: Callable[[ReadingData], Book | None] = lambda _: None
    list_fn: Callable[[ReadingData], list[Book]] | None = None


SENSORS: tuple[KindleSensorDescription, ...] = (
    KindleSensorDescription(
        key="currently_reading",
        translation_key="currently_reading",
        icon="mdi:book-open-page-variant",
        value_fn=lambda d: _title(d.reading[0] if d.reading else None),
        book_fn=lambda d: d.reading[0] if d.reading else None,
        list_fn=lambda d: d.reading,
    ),
    KindleSensorDescription(
        key="last_finished",
        translation_key="last_finished",
        icon="mdi:book-check",
        value_fn=lambda d: _title(d.read[0] if d.read else None),
        book_fn=lambda d: d.read[0] if d.read else None,
    ),
    KindleSensorDescription(
        key="books_read",
        translation_key="books_read",
        icon="mdi:bookshelf",
        native_unit_of_measurement="books",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda d: len(d.read),
        list_fn=lambda d: d.read,
    ),
    KindleSensorDescription(
        key="books_read_this_year",
        translation_key="books_read_this_year",
        icon="mdi:calendar-check",
        native_unit_of_measurement="books",
        value_fn=lambda d: len(_read_this_year(d)),
        list_fn=_read_this_year,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KindleBooksConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(KindleBooksSensor(coordinator, d) for d in SENSORS)


class KindleBooksSensor(CoordinatorEntity[KindleBooksCoordinator], SensorEntity):
    """A sensor backed by the Goodreads shelves."""

    _attr_has_entity_name = True
    entity_description: KindleSensorDescription

    def __init__(
        self, coordinator: KindleBooksCoordinator, description: KindleSensorDescription
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        user_id = coordinator.entry.data[CONF_USER_ID]
        self._attr_unique_id = f"{user_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, user_id)},
            name="Kindle books",
            manufacturer="Goodreads",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=f"https://www.goodreads.com/user/show/{user_id}",
        )

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def entity_picture(self) -> str | None:
        book = self.entity_description.book_fn(self.coordinator.data)
        return book.cover if book else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        attrs: dict[str, Any] = {}
        if book := self.entity_description.book_fn(data):
            attrs.update(book.as_dict())
        if self.entity_description.list_fn:
            limit = self.coordinator.entry.options.get(CONF_MAX_BOOKS, DEFAULT_MAX_BOOKS)
            attrs["books"] = [b.as_dict() for b in self.entity_description.list_fn(data)[:limit]]
        return attrs
