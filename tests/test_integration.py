"""Config flow and sensor tests against a real Home Assistant core."""

from pathlib import Path

from freezegun.api import FrozenDateTimeFactory
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.kindle_books.const import DOMAIN

FEED = "https://www.goodreads.com/review/list_rss/12345"
READ = (Path(__file__).parent / "fixtures/read_shelf.xml").read_text()
EMPTY = "<rss><channel/></rss>"
READING = """<rss><channel><item>
  <title>The Three-Body Problem</title><book_id>20518872</book_id>
  <author_name>Cixin Liu</author_name>
  <book_large_image_url>https://i.gr-assets.com/tbp.jpg</book_large_image_url>
  <user_date_added>Tue, 16 Sep 2026 20:00:00 +0000</user_date_added>
</item></channel></rss>"""


def _mock_feeds(aioclient_mock: AiohttpClientMocker) -> None:
    aioclient_mock.get(FEED, params={"shelf": "read", "page": "1"}, text=READ)
    aioclient_mock.get(FEED, params={"shelf": "read", "page": "2"}, text=EMPTY)
    aioclient_mock.get(FEED, params={"shelf": "currently-reading", "page": "1"}, text=READING)
    aioclient_mock.get(FEED, params={"shelf": "currently-reading", "page": "2"}, text=EMPTY)


async def test_config_flow(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    _mock_feeds(aioclient_mock)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "user_id": "https://www.goodreads.com/user/show/12345-matt",
            "read_shelf": "read",
            "reading_shelf": "currently-reading",
        },
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["user_id"] == "12345"


async def test_config_flow_errors(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    aioclient_mock.get(FEED, params={"shelf": "read", "page": "1"}, status=404)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    base = {"read_shelf": "read", "reading_shelf": "currently-reading"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**base, "user_id": "matt"}
    )
    assert result["errors"] == {"user_id": "invalid_user_id"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**base, "user_id": "12345"}
    )
    assert result["errors"] == {"base": "user_not_found"}


async def test_sensors(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to("2026-09-30 12:00:00+00:00")
    _mock_feeds(aioclient_mock)
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="12345",
        data={"user_id": "12345", "read_shelf": "read", "reading_shelf": "currently-reading"},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    reading = hass.states.get("sensor.kindle_books_currently_reading")
    assert reading.state == "The Three-Body Problem"
    assert reading.attributes["author"] == "Cixin Liu"
    assert reading.attributes["entity_picture"] == "https://i.gr-assets.com/tbp.jpg"

    last = hass.states.get("sensor.kindle_books_last_finished")
    assert last.state == "Project Hail Mary"

    total = hass.states.get("sensor.kindle_books_books_read")
    assert total.state == "2"
    assert [b["title"] for b in total.attributes["books"]] == ["Project Hail Mary", "Dune"]

    assert hass.states.get("sensor.kindle_books_books_read_this_year").state == "1"

    assert await hass.config_entries.async_unload(entry.entry_id)
