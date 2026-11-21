"""Tests for the dashboard cards: how they are served and the data they read."""

from __future__ import annotations

from pathlib import Path
import re
from unittest.mock import AsyncMock, MagicMock, patch

from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from custom_components.inverterzone import CARDS_DIR, CARDS_URL, PANEL_URL_PATH
from custom_components.inverterzone.const import DOMAIN

from .conftest import setup_integration

CARDS_JS = CARDS_DIR / "inverterzone-cards.js"
MANIFEST_VERSION = "1.2.0"
CARDS_JS_URL = f"{CARDS_URL}/inverterzone-cards.js?v={MANIFEST_VERSION}"


async def test_cards_and_sidebar_page(hass: HomeAssistant) -> None:
    """With a web server: the cards are served and loaded, and the sidebar page is added."""
    hass.http = MagicMock()
    hass.http.async_register_static_paths = AsyncMock()

    with (
        patch("homeassistant.components.frontend.add_extra_js_url") as add_js,
        patch("homeassistant.components.panel_custom.async_register_panel") as add_panel,
    ):
        assert await async_setup_component(hass, DOMAIN, {})

    (paths,) = hass.http.async_register_static_paths.call_args.args
    assert paths[0].url_path == CARDS_URL
    assert Path(paths[0].path) == CARDS_DIR
    add_js.assert_called_once_with(hass, CARDS_JS_URL)

    add_panel.assert_awaited_once()
    panel = add_panel.call_args.kwargs
    assert panel["frontend_url_path"] == PANEL_URL_PATH
    assert panel["webcomponent_name"] == "inverterzone-panel"
    assert panel["sidebar_title"] == "inverterzone"
    assert panel["module_url"] == CARDS_JS_URL
    assert panel["require_admin"] is False
    assert 'define("inverterzone-panel"' in CARDS_JS.read_text(encoding="utf-8")


async def test_sidebar_page_already_registered(hass: HomeAssistant) -> None:
    """A page left over from an earlier setup does not stop the integration."""
    hass.http = MagicMock()
    hass.http.async_register_static_paths = AsyncMock()

    with (
        patch("homeassistant.components.frontend.add_extra_js_url"),
        patch(
            "homeassistant.components.panel_custom.async_register_panel",
            side_effect=ValueError("Overwriting panel inverterzone"),
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, {})


def test_card_images_exist() -> None:
    """Every image the cards ask for is shipped."""
    names = set(re.findall(r'asset\("([\w-]+)"\)', CARDS_JS.read_text(encoding="utf-8")))
    names |= set(re.findall(r'row\(\s*"(icon-[\w-]+)"', CARDS_JS.read_text(encoding="utf-8")))
    names |= set(re.findall(r'(?:energyRow|row)\("(icon-[\w-]+)"', CARDS_JS.read_text(encoding="utf-8")))
    assert names, "no images found in the card script"
    missing = [n for n in sorted(names) if not (CARDS_DIR / "images" / f"{n}.webp").is_file()]
    assert not missing


def test_cards_read_existing_translation_keys() -> None:
    """The cards find entities by translation key; each key they use must exist."""
    strings = (CARDS_DIR.parent / "strings.json").read_text(encoding="utf-8")
    js = CARDS_JS.read_text(encoding="utf-8")
    block = re.search(r"const FLOW_KEYS = \[(.*?)\];", js, re.S).group(1)
    block += re.search(r"const STATS_KEYS = \[(.*?)\];", js, re.S).group(1)
    keys = set(re.findall(r'"([a-z0-9_]+)"', block))
    assert keys
    missing = [k for k in sorted(keys) if f'"{k}"' not in strings]
    assert not missing


async def test_stats_attributes(
    hass: HomeAssistant, mock_cloud: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    """Energy sensors carry yesterday's figure, the rate and the peak times for the stats card."""
    await setup_integration(hass, config_entry)
    p = "sensor.home_inverter_"

    solar = hass.states.get(p + "solar_energy_today").attributes
    assert solar["yesterday_same_time"] == 10.1
    assert solar["compare_label"] == "Yesterday"
    assert solar["rate_per_kwh"] == 60

    assert hass.states.get(p + "grid_import_today").attributes["yesterday_same_time"] == 3.6
    assert hass.states.get(p + "grid_export_today").attributes["yesterday_same_time"] == 0.0
    assert hass.states.get(p + "battery_charge_today").attributes["yesterday_same_time"] == 4.1
    assert hass.states.get(p + "peak_solar_power_today").attributes["time"] == "12:35"
    assert hass.states.get(p + "peak_load_power_today").attributes["time"] == "19:05"
    # Live sensors have no extra attributes.
    assert "yesterday_same_time" not in hass.states.get(p + "solar_power").attributes
