"""The Kindle Books integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import GoodreadsClient
from .const import CONF_FEED_KEY, CONF_USER_ID
from .coordinator import KindleBooksCoordinator

PLATFORMS = [Platform.SENSOR]

type KindleBooksConfigEntry = ConfigEntry[KindleBooksCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: KindleBooksConfigEntry) -> bool:
    """Set up Kindle Books from a config entry."""
    client = GoodreadsClient(
        async_get_clientsession(hass),
        entry.data[CONF_USER_ID],
        entry.data.get(CONF_FEED_KEY),
    )
    coordinator = KindleBooksCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: KindleBooksConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload(hass: HomeAssistant, entry: KindleBooksConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
