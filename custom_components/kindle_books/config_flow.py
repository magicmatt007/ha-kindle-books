"""Config flow for Kindle Books."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    GoodreadsClient,
    GoodreadsError,
    GoodreadsUserNotFound,
    parse_feed_key,
    parse_user_id,
)
from .const import (
    CONF_FEED_KEY,
    CONF_MAX_BOOKS,
    CONF_READ_SHELF,
    CONF_READING_SHELF,
    CONF_SCAN_INTERVAL,
    CONF_USER_ID,
    DEFAULT_MAX_BOOKS,
    DEFAULT_READ_SHELF,
    DEFAULT_READING_SHELF,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)


class KindleBooksConfigFlow(ConfigFlow, domain=DOMAIN):
    """Ask for the Goodreads account that Kindle syncs to."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                user_id = parse_user_id(user_input[CONF_USER_ID])
            except ValueError:
                errors[CONF_USER_ID] = "invalid_user_id"
            else:
                await self.async_set_unique_id(user_id)
                self._abort_if_unique_id_configured()
                key = parse_feed_key(user_input[CONF_USER_ID])
                client = GoodreadsClient(
                    async_get_clientsession(self.hass), user_id, key
                )
                try:
                    await client.get_shelf(user_input[CONF_READ_SHELF], max_pages=1)
                except GoodreadsUserNotFound:
                    errors["base"] = "user_not_found"
                except GoodreadsError:
                    errors["base"] = "cannot_connect"
                else:
                    return self.async_create_entry(
                        title=f"Kindle books ({user_id})",
                        data={
                            **user_input,
                            CONF_USER_ID: user_id,
                            CONF_FEED_KEY: key,
                        },
                    )

        schema = vol.Schema(
            {
                vol.Required(CONF_USER_ID): str,
                vol.Required(CONF_READ_SHELF, default=DEFAULT_READ_SHELF): str,
                vol.Required(CONF_READING_SHELF, default=DEFAULT_READING_SHELF): str,
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(schema, user_input),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return KindleBooksOptionsFlow()


class KindleBooksOptionsFlow(OptionsFlow):
    """Tune polling and how many books are exposed."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        opts = self.config_entry.options
        data = self.config_entry.data
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_READ_SHELF,
                        default=opts.get(CONF_READ_SHELF, data.get(CONF_READ_SHELF, DEFAULT_READ_SHELF)),
                    ): str,
                    vol.Required(
                        CONF_READING_SHELF,
                        default=opts.get(CONF_READING_SHELF, data.get(CONF_READING_SHELF, DEFAULT_READING_SHELF)),
                    ): str,
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=opts.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    ): vol.All(vol.Coerce(int), vol.Range(min=15, max=1440)),
                    vol.Required(
                        CONF_MAX_BOOKS,
                        default=opts.get(CONF_MAX_BOOKS, DEFAULT_MAX_BOOKS),
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=200)),
                }
            ),
        )
