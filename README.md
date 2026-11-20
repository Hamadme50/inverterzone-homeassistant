# inverterzone for Home Assistant

Bring your solar inverter's data from the **inverterzone** app into Home Assistant: live solar, load, battery and grid readings every 15 seconds, and today's energy totals for the Energy dashboard.

The integration signs in to the inverterzone cloud once with your app email and password. It keeps only a sign-in token, never your password. You need an inverterzone dongle connected to your inverter and an inverterzone account that owns it.

## Install

### HACS / Marketplace

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Hamadme50&repository=inverterzone-homeassistant&category=integration)

Click the button above to add this repository to HACS in one step, or add it by hand:

1. In Home Assistant open **HACS** (the **Marketplace** in Home Assistant 2026.11 and later).
2. Until inverterzone is in the default list: open the menu (⋮) → **Custom repositories**, add `https://github.com/Hamadme50/inverterzone-homeassistant` with type **Integration**.
3. Search for **inverterzone**, install it, and restart Home Assistant.

### Manual

Copy `custom_components/inverterzone` into your Home Assistant `config/custom_components/` folder and restart.

## Set up

**Settings → Devices & services → Add integration → inverterzone**, then enter the email and password of your inverterzone app account. Each inverter on the account becomes a device.

If you change the account password, Home Assistant asks you to sign in again. Inverters added to the account later appear after you reload the integration.

Requires Home Assistant 2026.3 or later.

## What you get

**Live, every 15 seconds.** These are unavailable while the dongle is offline (no report for 3 minutes).

| Group | Sensors |
|---|---|
| Solar | Solar power; PV1/PV2/PV3 power, voltage and current (only the inputs your inverter has) |
| Load | Load power, apparent power, output voltage, current and frequency, load % |
| Battery | Battery %, voltage, power (+ charging / − discharging), charge and discharge current, status |
| Grid | Grid voltage, frequency, power, feed-in power; *Grid available* |
| Inverter | Mode, heat sink and inverter temperature; bus voltage, charging stage and fault (diagnostic) |
| Lithium BMS | State of charge, voltage and current limits, *BMS connected* (only when a BMS reports) |
| Dongle | *Online*, last reading time |

**Today's energy, every 30 minutes** (plus one refresh at 23:55 site time). All in kWh and reset at local midnight:
solar, solar to battery, grid import, grid to battery, grid export, battery charge, battery discharge, load, total supplied. Also today's peak solar and load power, and minutes without grid.

### Energy dashboard

**Settings → Dashboards → Energy:**

- *Grid consumption*: **Grid import today**; *Return to grid*: **Grid export today**
- *Solar production*: **Solar energy today**
- *Home battery storage*: in **Battery charge today**, out **Battery discharge today**

## Privacy

Data comes from the inverterzone cloud (`https://inverterzone.com/api/home`). Diagnostics downloads redact the token and email. Removing the integration deletes the stored token; to revoke every token, change the account password in the inverterzone app.

## API reference

The integration uses these endpoints; other tools may use them the same way. Every answer is `{ "success", "error", "message", "data" }`; failures use HTTP 400/401/403/404/500 with an `error` code.

| Call | Purpose |
|---|---|
| `POST /api/home/getConnected` `{"email","password"}` | Returns `{token, expiresAt, expiresIn, devices[]}`. The token is valid for one year. |
| `GET /api/home/getDevices` | The account's inverters: `[{mac, name, model, brand, online}]` |
| `GET /api/home/getSolarData?mac=` | The latest live reading |
| `GET /api/home/getEnergyData?mac=` | Today's energy totals (cached up to 5 minutes) |

Send the token as `Authorization: Bearer <token>`. Error codes: `INVALID_CREDENTIALS`, `TOKEN_MISSING`, `TOKEN_INVALID`, `TOKEN_EXPIRED`, `TOKEN_REVOKED` (password changed), `DEVICE_NOT_LINKED`, `NO_DATA`.

## Development

```bash
pip install -r requirements_test.txt
pytest
```
