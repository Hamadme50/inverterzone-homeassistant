/*
 * inverterzone dashboard cards for Home Assistant.
 *
 *   type: custom:inverterzone-flow-card    the app's realtime "flow" page
 *   type: custom:inverterzone-stats-card   the app's stats page (today)
 *
 * Optional option for both: device_id (an inverterzone device). Without it the
 * first inverterzone inverter is used. Plain Web Components, no build step.
 */

const VERSION = new URL(import.meta.url).searchParams.get("v") || "dev";
const PLATFORM = "inverterzone";
const asset = (name) => `${new URL(`images/${name}.webp`, import.meta.url).href}?v=${VERSION}`;

// ---------------------------------------------------------------- colours
// Same as the app's CustomColorScheme / flow skin.
const palette = (dark) => ({
  text: dark ? "#FFFFFF" : "#3A6372",
  solar: dark ? "#24DF34" : "#00B33C",
  charge: dark ? "#24DF34" : "#00B33C",
  discharge: "#FF5656",
  idle: dark ? "#FFFFFF" : "#3A6372",
  load: "#FF5656",
  grid: dark ? "#FFFFFF" : "#3A6372",
  wire: dark ? "#6FA8E8" : "#7BAFE0",
  accent: dark ? "#5AA9FF" : "#2F80ED",
  ok: dark ? "#34D399" : "#059669",
  battery: dark ? "#5AA9FF" : "#2F80ED",
  track: dark ? "#37474F" : "#E3E3E3",
});

// ---------------------------------------------------------------- helpers
const BAD = new Set(["unavailable", "unknown", "", undefined, null]);

function inverterDevices(hass) {
  const ids = [];
  for (const e of Object.values(hass?.entities || {})) {
    if (e.platform === PLATFORM && e.device_id && !ids.includes(e.device_id)) ids.push(e.device_id);
  }
  return ids;
}

function deviceName(hass, id) {
  const d = hass?.devices?.[id];
  return (d && (d.name_by_user || d.name)) || "Inverter";
}

/** translation_key -> entity_id for one inverter. */
function deviceEntities(hass, deviceId) {
  const map = {};
  for (const [entityId, e] of Object.entries(hass?.entities || {})) {
    if (e.platform === PLATFORM && e.device_id === deviceId && e.translation_key) {
      map[e.translation_key] = entityId;
    }
  }
  return map;
}

function stateOf(hass, entityId) {
  return entityId ? hass.states[entityId] : undefined;
}

function num(hass, entityId) {
  const s = stateOf(hass, entityId);
  if (!s || BAD.has(s.state)) return null;
  const v = Number(s.state);
  return Number.isFinite(v) ? v : null;
}

function text(hass, entityId) {
  const s = stateOf(hass, entityId);
  return !s || BAD.has(s.state) ? null : s.state;
}

function attr(hass, entityId, name) {
  const s = stateOf(hass, entityId);
  const v = s?.attributes?.[name];
  return v === undefined ? null : v;
}

/** "4.82 kW" or "820 W" (the app's skinPower). */
function power(w) {
  if (w === null || w === undefined) return "—";
  const a = Math.abs(w);
  return a >= 1000 ? `${(a / 1000).toFixed(2)} kW` : `${Math.round(a)} W`;
}

/** "12.3 kWh" (the app's formatKwh). */
function kwh(v) {
  if (v === null || v === undefined) return "--";
  return `${v.toFixed(Math.abs(v) >= 100 ? 0 : 1)} kWh`;
}

function one(v, unit) {
  if (v === null || v === undefined) return `— ${unit}`;
  return `${Math.round(v * 10) / 10} ${unit}`;
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

function signature(hass, entityIds) {
  return entityIds.map((id) => {
    const s = id && hass.states[id];
    return s ? `${s.state}|${s.last_updated}` : "-";
  }).join(";") + `|${hass?.themes?.darkMode}`;
}

function moreInfo(node, entityId) {
  if (!entityId) return;
  node.dispatchEvent(new CustomEvent("hass-more-info", { detail: { entityId }, bubbles: true, composed: true }));
}

const ICON = {
  thermometer: "M15 13V5A3 3 0 0 0 9 5V13A5 5 0 1 0 15 13M12 4A1 1 0 0 1 13 5V8H11V5A1 1 0 0 1 12 4Z",
  warning: "M13 14H11V9H13M13 18H11V16H13M1 21H23L12 2L1 21Z",
  battery: "M16 4H14V2H10V4H8A2 2 0 0 0 6 6V20A2 2 0 0 0 8 22H16A2 2 0 0 0 18 20V6A2 2 0 0 0 16 4Z",
  check: "M21 7L9 19L3.5 13.5L4.91 12.09L9 16.17L19.59 5.59L21 7Z",
  leaf: "M17 8C8 10 5.9 16.17 3.82 21.34L5.71 22L6.66 19.7C7.14 19.87 7.64 20 8 20C19 20 22 3 22 3C21 5 14 5.25 9 6.25C4 7.25 2 11.5 2 13.5C2 15.5 3.75 17.25 3.75 17.25C7 8 17 8 17 8Z",
  tree: "M11 21V16.74C10.53 16.91 10.03 17 9.5 17C7 17 5 15 5 12.5C5 11.23 5.5 10.09 6.36 9.27L6.17 8.5C6.17 6 8.17 4 10.67 4C12.04 4 13.27 4.6 14.08 5.56C14.86 5.21 15.71 5 16.62 5C20.16 5 23 7.84 23 11.38C23 14.92 20.16 17.75 16.62 17.75C15.7 17.75 14.82 17.55 14 17.2V21H11Z",
  clock: "M12 20A8 8 0 0 0 20 12A8 8 0 0 0 12 4A8 8 0 0 0 4 12A8 8 0 0 0 12 20M12 2A10 10 0 0 1 22 12A10 10 0 0 1 12 22C6.47 22 2 17.5 2 12A10 10 0 0 1 12 2M12.5 7V12.25L17 14.92L16.25 16.15L11 13V7H12.5Z",
  gridOff: "M8.28 5.45L6.5 4.55L7.76 2H16.23L17.5 4.55L15.72 5.44L15 4H9L8.28 5.45M18.62 8H14.09L13.3 6H10.7L9.91 8H5.38L4.1 10.55L5.89 11.44L6.62 10H17.38L18.1 11.45L19.89 10.56L18.62 8M17.77 22H15.7L15.46 21.1L12 15.9L8.53 21.1L8.3 22H6.23L9.12 11H11.19L10.83 12.35L12 14.1L13.16 12.35L12.81 11H14.88L17.77 22M11.2 15L10.47 13.9L9.72 16.76L11.2 15M14.28 16.76L13.53 13.9L12.8 15L14.28 16.76Z",
};
const svgIcon = (name, color, size = 20) =>
  `<svg viewBox="0 0 24 24" width="${size}" height="${size}" aria-hidden="true"><path fill="${color}" d="${ICON[name]}"/></svg>`;

const BASE_CSS = `
  :host { display: block; }
  [hidden] { display: none !important; }
  ha-card { display: block; padding: 12px 14px 14px; overflow: hidden; font-family: var(--ha-font-family-body, Roboto, Arial, sans-serif); }
  .muted { opacity: .6; }
  .box { border-radius: 16px; background: rgba(127, 127, 127, 0.08); }
  .empty { padding: 24px; text-align: center; opacity: .7; }
  .tabular { font-variant-numeric: tabular-nums; }
`;

class InverterzoneBaseCard extends HTMLElement {
  setConfig(config) {
    this._config = { ...config };
    this._sig = null;
    if (this._hass) this._refresh();
  }

  set hass(hass) {
    this._hass = hass;
    this._refresh();
  }

  get hass() {
    return this._hass;
  }

  _deviceId() {
    const ids = inverterDevices(this._hass);
    return this._config?.device_id && ids.includes(this._config.device_id) ? this._config.device_id : ids[0];
  }

  static getConfigElement() {
    return document.createElement("inverterzone-card-editor");
  }

  static getStubConfig(hass) {
    const id = inverterDevices(hass)[0];
    return id ? { device_id: id } : {};
  }

  _root() {
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    return this.shadowRoot;
  }

  _empty(message) {
    this._root().innerHTML = `<style>${BASE_CSS}</style><ha-card><div class="empty">${esc(message)}</div></ha-card>`;
    this._built = null;
  }
}

// ======================================================================= flow card
// Geometry from the app's flow skin (flow_realtimepage.dart), in a 400-wide box.
const W = 400;
const H = 432;
const HALF = 38; // icons are 76 px
const SOLAR_Y = 2 + HALF;
const INV_Y = 188;
const ROW_Y = 328;
const CX = W / 2;
const BAT_X = W * 0.18;
const GRID_X = W * 0.5;
const LOAD_X = W * 0.82;

const FLOW_KEYS = [
  "online", "solar_power", "pv1_voltage", "pv1_current", "pv2_voltage", "pv3_voltage",
  "battery_level", "battery_voltage", "battery_power", "battery_charge_current", "battery_discharge_current",
  "grid_power", "grid_voltage", "grid_frequency", "grid_available",
  "load_power", "load_percent", "load_current",
  "inverter_mode", "heat_sink_temperature", "inverter_temperature", "charging_stage", "bms_connected",
  "reading_time", "peak_solar_power_today", "peak_load_power_today", "solar_energy_today", "load_energy_today",
];

class InverterzoneFlowCard extends InverterzoneBaseCard {
  getCardSize() {
    return 10;
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6, rows: "auto" };
  }

  _refresh() {
    if (!this._hass || !this._config) return;
    const deviceId = this._deviceId();
    if (!deviceId) {
      this._empty("No inverterzone inverter found. Add the inverterzone integration first.");
      return;
    }
    const e = deviceEntities(this._hass, deviceId);
    const sig = signature(this._hass, FLOW_KEYS.map((k) => e[k])) + deviceId;
    if (sig === this._sig) return;
    this._sig = sig;
    if (this._built !== deviceId) this._build(deviceId, e);
    this._update(e);
  }

  _build(deviceId, e) {
    const root = this._root();
    const wirePath = {
      solar: `M${CX},${SOLAR_Y + HALF + 2} L${CX},${INV_Y - HALF - 2}`,
      grid: `M${CX},${INV_Y + HALF + 2} L${CX},${ROW_Y - HALF - 4}`,
      battery: `M${CX - HALF + 2},${INV_Y} L${BAT_X + 14},${INV_Y} Q${BAT_X},${INV_Y} ${BAT_X},${INV_Y + 14} L${BAT_X},${ROW_Y - HALF - 4}`,
      load: `M${CX + HALF - 2},${INV_Y} L${LOAD_X - 14},${INV_Y} Q${LOAD_X},${INV_Y} ${LOAD_X},${INV_Y + 14} L${LOAD_X},${ROW_Y - HALF - 4}`,
    };
    const node = (id, name, cx, cy) =>
      `<g class="node" data-node="${id}"><image href="${asset(name)}" x="${cx - HALF}" y="${cy - HALF}" width="${HALF * 2}" height="${HALF * 2}" preserveAspectRatio="xMidYMid meet"/>
       <rect x="${cx - HALF}" y="${cy - HALF}" width="${HALF * 2}" height="${HALF * 2}" fill="transparent"/></g>`;
    const bottomLabel = (id, title, cx) => {
      const y = ROW_Y + HALF + 6;
      return `<text class="lbl" x="${cx}" y="${y + 11}" text-anchor="middle">${title}</text>
        <text id="${id}-main" class="main" x="${cx}" y="${y + 30}" text-anchor="middle"></text>
        <text id="${id}-sub" class="sub" x="${cx}" y="${y + 48}" text-anchor="middle"></text>`;
    };
    root.innerHTML = `
      <style>${BASE_CSS}
        svg.diagram { display: block; width: 100%; height: auto; overflow: visible; }
        .wire { fill: none; stroke-width: 4; stroke-dasharray: 10 10; }
        .wire.idle { opacity: .3; }
        .wire.fwd { animation: iz-fwd .7s linear infinite; }
        .wire.rev { animation: iz-rev .7s linear infinite; }
        @keyframes iz-fwd { from { stroke-dashoffset: 0; } to { stroke-dashoffset: -20; } }
        @keyframes iz-rev { from { stroke-dashoffset: 0; } to { stroke-dashoffset: 20; } }
        .node { cursor: pointer; }
        text { font-family: inherit; }
        .lbl { font-size: 11px; font-weight: 600; opacity: .6; }
        .main { font-size: 16px; font-weight: 800; }
        .sub { font-size: 14px; }
        .badge text { font-size: 10px; font-weight: 700; fill: #fff; }
        .chip { display: inline-flex; align-items: center; gap: 4px; padding: 1px 6px; border-radius: 8px;
                font-size: 9px; font-weight: 700; white-space: nowrap; line-height: 14px; }
        .chips { display: flex; flex-direction: column; align-items: flex-end; gap: 22px; }
        .banner { display: flex; align-items: center; gap: 10px; padding: 12px 14px; margin-bottom: 10px;
                  border-radius: 14px; border: 1px solid rgba(255, 86, 86, .4); font-size: 13px; font-weight: 600; }
        .modebar { display: flex; align-items: center; gap: 12px; padding: 10px 18px; margin-top: 8px; }
        .modebar .temp { font-size: 16px; font-weight: 700; }
        .modebar .mode { margin-left: auto; text-align: right; min-width: 0; }
        .modebar .mode div:first-child { font-size: 11px; opacity: .6; font-weight: 600; }
        .modebar .mode div:last-child { font-size: 15px; font-weight: 700; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .stats { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 12px; }
        .stat { display: flex; align-items: center; gap: 10px; padding: 12px; cursor: pointer; min-width: 0; }
        .stat img { width: 34px; height: 34px; object-fit: contain; flex: none; }
        .stat .k { font-size: 11px; opacity: .6; font-weight: 600; }
        .stat .v { font-size: 15px; font-weight: 800; white-space: nowrap; }
      </style>
      <ha-card>
        <div id="banner" class="banner" hidden>${svgIcon("warning", "#FF5656")}<span id="banner-text"></span></div>
        <svg class="diagram" viewBox="0 0 ${W} ${H}" role="img" aria-label="Energy flow">
          <path id="w-solar" class="wire" d="${wirePath.solar}"/>
          <path id="w-grid" class="wire" d="${wirePath.grid}"/>
          <path id="w-battery" class="wire" d="${wirePath.battery}"/>
          <path id="w-load" class="wire" d="${wirePath.load}"/>
          <g text-anchor="end">
            <text class="lbl" x="${CX - HALF - 18}" y="${SOLAR_Y - 10}">Solar</text>
            <text id="solar-main" x="${CX - HALF - 18}" y="${SOLAR_Y + 12}" style="font-size:19px;font-weight:800"></text>
            <text id="solar-v" x="${CX - HALF - 18}" y="${SOLAR_Y + 32}" style="font-size:17px"></text>
            <text id="solar-a" x="${CX - HALF - 18}" y="${SOLAR_Y + 49}" style="font-size:14px"></text>
          </g>
          ${node("solar", "solar", CX, SOLAR_Y)}
          ${node("inverter", "inverter", CX, INV_Y)}
          ${node("battery", "battery", BAT_X, ROW_Y)}
          ${node("grid", "grid", GRID_X, ROW_Y)}
          ${node("load", "load", LOAD_X, ROW_Y)}
          <g id="pv-badge" class="badge" hidden>
            <circle cx="${CX - HALF + 6}" cy="${SOLAR_Y - HALF + 6}" r="10" fill="red"/>
            <text id="pv-badge-text" x="${CX - HALF + 6}" y="${SOLAR_Y - HALF + 10}" text-anchor="middle"></text>
          </g>
          <g id="grid-cross" hidden>
            <circle cx="${GRID_X - HALF + 6}" cy="${ROW_Y - HALF + 6}" r="10" fill="red"/>
            <path d="M${GRID_X - HALF + 2},${ROW_Y - HALF + 2} l8,8 m0,-8 l-8,8" stroke="#fff" stroke-width="2.2" stroke-linecap="round"/>
          </g>
          <foreignObject x="0" y="${INV_Y - 30}" width="${CX - HALF - 2}" height="70">
            <div xmlns="http://www.w3.org/1999/xhtml" class="chips">
              <span id="chip-stage" class="chip"></span>
              <span id="chip-bms" class="chip" hidden>BMS</span>
            </div>
          </foreignObject>
          ${bottomLabel("battery", "Battery", BAT_X)}
          ${bottomLabel("grid", "Grid", GRID_X)}
          ${bottomLabel("load", "Load", LOAD_X)}
        </svg>
        <div class="modebar box">
          <span id="temp-icon"></span>
          <span id="temp" class="temp tabular"></span>
          <div class="mode"><div>Mode</div><div id="mode"></div></div>
        </div>
        <div class="stats">
          <div class="stat box" data-key="peak_solar_power_today"><img src="${asset("solar")}" alt=""><div><div class="k">Peak Production</div><div id="st-peak-solar" class="v tabular"></div></div></div>
          <div class="stat box" data-key="peak_load_power_today"><img src="${asset("load")}" alt=""><div><div class="k">Peak Load</div><div id="st-peak-load" class="v tabular"></div></div></div>
          <div class="stat box" data-key="solar_energy_today"><img src="${asset("icon-solarpanel")}" alt=""><div><div class="k">Solar Today</div><div id="st-solar" class="v tabular"></div></div></div>
          <div class="stat box" data-key="load_energy_today"><img src="${asset("icon-home")}" alt=""><div><div class="k">Load Today</div><div id="st-load" class="v tabular"></div></div></div>
        </div>
      </ha-card>`;

    const tapTarget = {
      solar: "solar_power", inverter: "inverter_mode", battery: "battery_level", grid: "grid_power", load: "load_power",
    };
    root.querySelectorAll(".node").forEach((g) =>
      g.addEventListener("click", () => moreInfo(this, deviceEntities(this._hass, deviceId)[tapTarget[g.dataset.node]])),
    );
    root.querySelectorAll(".stat").forEach((s) =>
      s.addEventListener("click", () => moreInfo(this, deviceEntities(this._hass, deviceId)[s.dataset.key])),
    );
    this._built = deviceId;
  }

  _update(e) {
    const hass = this._hass;
    const root = this.shadowRoot;
    const c = palette(Boolean(hass.themes?.darkMode));
    const $ = (id) => root.getElementById(id);
    const v = (key) => num(hass, e[key]);

    const online = text(hass, e.online) !== "off";
    const solarW = v("solar_power");
    const solarV = v("pv1_voltage");
    const solarA = v("pv1_current");
    const batV = v("battery_voltage");
    const batW = v("battery_power");
    const batPct = v("battery_level");
    const chargeA = v("battery_charge_current") ?? 0;
    const dischargeA = v("battery_discharge_current") ?? 0;
    const gridW = v("grid_power");
    const gridHz = v("grid_frequency");
    const gridV = v("grid_voltage");
    const loadW = v("load_power");

    // Flow rules from the app's flow skin.
    const solarFlow = { active: (solarV ?? 0) > 10 && (solarW ?? 0) > 0, reverse: false };
    let charging = false;
    let discharging = false;
    if ((batV ?? 0) >= 7) {
      if (chargeA !== 0) charging = true;
      else if (dischargeA !== 0) discharging = true;
      else if ((solarW ?? 0) === 0 && (gridHz ?? 0) === 0) discharging = true;
    }
    const batteryFlow = { active: charging || discharging, reverse: discharging };
    const gridFlow = { active: (gridW ?? 0) !== 0, reverse: (gridW ?? 0) > 0 };
    const loadFlow = { active: (loadW ?? 0) > 0, reverse: false };

    const wire = (id, flow) => {
      const el = $(id);
      el.setAttribute("stroke", c.wire);
      el.setAttribute("class", `wire ${flow.active && online ? (flow.reverse ? "rev" : "fwd") : "idle"}`);
    };
    wire("w-solar", solarFlow);
    wire("w-battery", batteryFlow);
    wire("w-grid", gridFlow);
    wire("w-load", loadFlow);

    root.querySelectorAll("text").forEach((t) => t.setAttribute("fill", c.text));
    const set = (id, value, color) => {
      const el = $(id);
      el.textContent = value;
      if (color) el.setAttribute("fill", color);
    };

    // Solar, left of the panel.
    set("solar-main", power(solarW), c.solar);
    set("solar-v", `${solarV === null ? "—" : Math.trunc(solarV)} V`, c.solar);
    set("solar-a", one(solarA, "A"), c.solar);
    const pvCount = (v("pv3_voltage") ?? 0) > 5 ? "3" : (v("pv2_voltage") ?? 0) > 5 ? "2" : null;
    $("pv-badge").toggleAttribute("hidden", !pvCount);
    $("pv-badge-text").textContent = pvCount ?? "";

    // Battery.
    const batColor = !batteryFlow.active ? c.idle : batteryFlow.reverse ? c.discharge : c.charge;
    set("battery-main", `${power(batW)} · ${batPct === null ? "—" : Math.round(batPct)}%`, batColor);
    const chargeRaw = v("battery_charge_current");
    const dischargeRaw = v("battery_discharge_current");
    const batA = chargeRaw === null && dischargeRaw === null ? null : chargeA || dischargeA;
    set("battery-sub", `${one(batV, "V")} · ${one(batA, "A")}`, batColor);
    $("battery-sub").setAttribute("fill-opacity", ".85");

    // Grid: a minus sign when exporting, red cross when the grid is off.
    set("grid-main", `${(gridW ?? 0) < 0 ? "-" : ""}${power(gridW)}`, c.grid);
    set("grid-sub", `${one(gridV, "V")} · ${one(gridHz, "Hz")}`, c.grid);
    $("grid-sub").setAttribute("fill-opacity", ".85");
    const gridOff = text(hass, e.grid_available) === "off" || (gridHz !== null && gridHz < 20);
    $("grid-cross").toggleAttribute("hidden", !gridOff);

    // Load.
    set("load-main", power(loadW), c.load);
    set("load-sub", `${v("load_percent") === null ? "—" : Math.round(v("load_percent"))} % · ${one(v("load_current"), "A")}`, c.load);
    $("load-sub").setAttribute("fill-opacity", ".85");

    // Chips beside the inverter.
    const stage = text(hass, e.charging_stage);
    const chipStyle = (color) => `color:${c.text};background:rgba(127,127,127,.12);border:1px solid ${color}`;
    const stageChip = $("chip-stage");
    // Keeps its place when empty, so the BMS chip stays below the battery wire.
    stageChip.setAttribute("style", `${chipStyle("rgba(127,127,127,.25)")};visibility:${stage ? "visible" : "hidden"}`);
    stageChip.innerHTML = `${svgIcon("battery", c.grid, 10)} ${esc(stage ?? "")}`;
    const bms = text(hass, e.bms_connected);
    const bmsChip = $("chip-bms");
    bmsChip.hidden = !bms;
    const bmsColor = bms === "on" ? c.ok : "#9E9E9E";
    bmsChip.setAttribute("style", `color:${bmsColor};background:${bmsColor}24;border:1px solid ${bmsColor}b3`);
    bmsChip.innerHTML = `${bms === "on" ? svgIcon("check", bmsColor, 10) : ""}BMS`;

    // Offline banner.
    const banner = $("banner");
    banner.hidden = online;
    banner.style.color = c.text;
    if (!online) {
      const t = text(hass, e.reading_time);
      const when = t ? new Date(t).toLocaleTimeString(hass.locale?.language, { hour: "2-digit", minute: "2-digit" }) : null;
      $("banner-text").textContent = `Inverter offline${when ? ` · last reading ${when}` : ""}`;
    }

    // Mode bar.
    const temps = [v("heat_sink_temperature"), v("inverter_temperature")].filter((t) => t !== null && t !== 0);
    $("temp-icon").innerHTML = svgIcon("thermometer", c.accent, 26);
    $("temp").textContent = temps.length ? temps.map((t) => `${Math.round(t)}°C`).join(" | ") : "—";
    $("temp").style.color = c.text;
    const modeState = stateOf(hass, e.inverter_mode);
    $("mode").textContent = modeState && !BAD.has(modeState.state)
      ? (hass.formatEntityState ? hass.formatEntityState(modeState) : modeState.state)
      : "—";
    $("mode").style.color = c.text;

    // Stats tiles.
    $("st-peak-solar").textContent = power(v("peak_solar_power_today"));
    $("st-peak-load").textContent = power(v("peak_load_power_today"));
    $("st-solar").textContent = kwh(v("solar_energy_today"));
    $("st-load").textContent = kwh(v("load_energy_today"));
    root.querySelectorAll(".stat .k, .stat .v").forEach((el) => { el.style.color = c.text; });
  }
}

// ======================================================================= stats card
const STATS_KEYS = [
  "solar_energy_today", "load_energy_today", "grid_import_energy_today", "grid_export_energy_today",
  "battery_discharge_energy_today", "solar_to_battery_energy_today", "grid_to_battery_energy_today",
  "total_supplied_energy_today", "peak_solar_power_today", "peak_load_power_today", "grid_off_today",
];
const CHART_SERIES = [
  { key: "solar_power", name: "Solar", color: (c) => c.solar },
  { key: "load_power", name: "Load", color: (c) => c.load },
  { key: "battery_power", name: "Battery", color: (c) => c.battery },
  { key: "grid_power", name: "Grid", color: (c) => c.grid },
];
const CO2_KG_PER_KWH = 0.5;
const TREE_KG_CO2_PER_YEAR = 21;

/** The app's energyDelta: "▲ 8%", "▼ 15%", "Same", or null when there is nothing to compare. */
function energyDelta(cur, prev) {
  if (cur === null || prev === null || prev === 0) return null;
  if (Math.abs(cur - prev) < 0.1) return { text: "Same", up: null };
  const pct = Math.round(((cur - prev) / Math.abs(prev)) * 100);
  if (pct === 0) return { text: "Same", up: null };
  const shown = Math.abs(pct) > 999 ? "999%+" : `${Math.abs(pct)}%`;
  return { text: `${pct > 0 ? "▲" : "▼"} ${shown}`, up: pct > 0 };
}

/** The app's solarScore: share of the load that did not come straight from the grid. */
function solarScore(load, gridImport, gridCharging) {
  if (!load || load <= 0) return null;
  const fromGrid = Math.max(0, (gridImport ?? 0) - (gridCharging ?? 0));
  return Math.min(1, Math.max(0, 1 - fromGrid / load));
}

function minutesText(m) {
  if (m === null) return "—";
  if (m <= 0) return "None";
  const h = Math.floor(m / 60);
  const min = Math.round(m % 60);
  return h ? `${h} h${min ? ` ${min} min` : ""}` : `${min} min`;
}

class InverterzoneStatsCard extends InverterzoneBaseCard {
  constructor() {
    super();
    this._hours = 1;
    this._history = null;
  }

  getCardSize() {
    return 14;
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6, rows: "auto" };
  }

  connectedCallback() {
    this._timer = setInterval(() => this._loadHistory(), 60000);
    this._loadHistory();
  }

  disconnectedCallback() {
    clearInterval(this._timer);
  }

  _refresh() {
    if (!this._hass || !this._config) return;
    const deviceId = this._deviceId();
    if (!deviceId) {
      this._empty("No inverterzone inverter found. Add the inverterzone integration first.");
      return;
    }
    const e = deviceEntities(this._hass, deviceId);
    this._e = e;
    const sig = signature(this._hass, STATS_KEYS.map((k) => e[k])) + deviceId;
    if (this._built !== deviceId) {
      this._build(deviceId);
      this._history = null;
      this._loadHistory();
    }
    if (sig === this._sig) return;
    this._sig = sig;
    this._render();
  }

  _build(deviceId) {
    const root = this._root();
    root.innerHTML = `
      <style>${BASE_CSS}
        .section { padding: 16px 18px 14px; margin: 0 0 12px; }
        .title { font-size: 16px; font-weight: 700; }
        .sub { font-size: 12px; opacity: .75; font-weight: 500; margin-top: 2px; }
        .center { text-align: center; }
        .score { font-size: 30px; font-weight: 800; line-height: 1.1; }
        .bar { height: 8px; border-radius: 4px; overflow: hidden; margin-top: 12px; }
        .bar > div { height: 100%; border-radius: 4px; }
        .ends { display: flex; justify-content: space-between; font-size: 11px; opacity: .75; margin: 6px 0 10px; }
        .row { display: flex; align-items: center; padding: 9px 0; border-bottom: .6px solid rgba(127,127,127,.25); cursor: pointer; }
        .row:last-child { border-bottom: none; }
        .row .icon { width: 22px; display: flex; justify-content: center; flex: none; }
        .row .icon img { height: 20px; }
        .row .label { flex: 1; margin-left: 14px; font-size: 14px; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .row .value { font-size: 14.5px; font-weight: 700; margin-left: 10px; white-space: nowrap; }
        .row .delta { width: 64px; text-align: right; font-size: 12px; font-weight: 700; margin-left: 8px; white-space: nowrap; }
        .chart svg { display: block; width: 100%; height: auto; }
        .legend { display: flex; flex-wrap: wrap; gap: 12px; font-size: 12px; margin-top: 6px; justify-content: center; }
        .legend span::before { content: ""; display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 5px; background: var(--dot); vertical-align: -1px; }
        .hours { display: flex; justify-content: space-evenly; margin-top: 8px; }
        .hours button { font: inherit; font-size: 12px; font-weight: 600; padding: 6px 12px; border-radius: 16px; cursor: pointer;
                        border: 1px solid rgba(127,127,127,.35); background: transparent; color: inherit; }
        .hours button.on { border-color: transparent; color: #fff; }
        .nodata { text-align: center; padding: 28px 0; opacity: .6; font-size: 13px; }
      </style>
      <ha-card>
        <div id="score" class="section box"></div>
        <div id="energy" class="section box"></div>
        <div id="highlights" class="section box"></div>
        <div class="section box chart">
          <div class="title">Real-Time Chart</div>
          <div id="chart"></div>
          <div class="hours">${[1, 2, 4, 6].map((h) => `<button data-h="${h}">${h} Hours</button>`).join("")}</div>
        </div>
      </ha-card>`;
    root.querySelectorAll(".hours button").forEach((b) =>
      b.addEventListener("click", () => {
        this._hours = Number(b.dataset.h);
        this._history = null;
        this._renderChart();
        this._loadHistory();
      }),
    );
    root.addEventListener("click", (ev) => {
      const row = ev.target.closest?.("[data-entity]");
      if (row) moreInfo(this, row.dataset.entity);
    });
    this._built = deviceId;
  }

  _render() {
    const hass = this._hass;
    const e = this._e;
    const root = this.shadowRoot;
    const c = palette(Boolean(hass.themes?.darkMode));
    root.querySelector("ha-card").style.color = c.text;
    const v = (key) => num(hass, e[key]);
    const prev = (key) => {
      const p = attr(hass, e[key], "yesterday_same_time");
      return p === null ? null : Number(p);
    };

    const solar = v("solar_energy_today");
    const load = v("load_energy_today");
    const gridIn = v("grid_import_energy_today");
    const gridCharge = v("grid_to_battery_energy_today");
    const compareLabel = attr(hass, e.solar_energy_today, "compare_label");
    const hasPrev = prev("solar_energy_today") !== null;

    const deltaColor = (up, higherIsBetter) => {
      if (up === null || higherIsBetter === null || higherIsBetter === undefined) return c.text;
      return up === higherIsBetter ? c.solar : c.load;
    };
    const deltaHtml = (cur, p, higherIsBetter) => {
      if (!hasPrev) return "";
      const d = energyDelta(cur, p);
      const style = d ? `color:${deltaColor(d.up, higherIsBetter)};${d.up === null || higherIsBetter == null ? "opacity:.75" : ""}` : "";
      return `<div class="delta tabular" style="${style}">${d ? esc(d.text) : ""}</div>`;
    };
    const row = (icon, label, value, entityKey, delta = "") =>
      `<div class="row" data-entity="${esc(e[entityKey] ?? "")}">
         <div class="icon">${icon.startsWith("<") ? icon : `<img src="${asset(icon)}" alt="">`}</div>
         <div class="label">${esc(label)}</div><div class="value tabular">${esc(value)}</div>${delta}</div>`;

    // 1. Score: "Your home ran on solar + battery".
    const score = solarScore(load, gridIn, gridCharge);
    const prevLoad = hasPrev
      ? (prev("solar_energy_today") ?? 0) + (prev("grid_import_energy_today") ?? 0) + (prev("battery_discharge_energy_today") ?? 0)
        - (prev("solar_to_battery_energy_today") ?? 0) - (prev("grid_to_battery_energy_today") ?? 0) - (prev("grid_export_energy_today") ?? 0)
      : null;
    const prevScore = hasPrev ? solarScore(prevLoad, prev("grid_import_energy_today"), prev("grid_to_battery_energy_today")) : null;
    let points = "";
    if (score !== null && prevScore !== null && compareLabel) {
      const pts = Math.round((score - prevScore) * 100);
      const color = pts === 0 ? c.text : pts > 0 ? c.solar : c.load;
      points = `<div class="center" style="font-size:12px;font-weight:700;color:${color};margin-top:2px">${
        pts === 0 ? `Same as ${esc(compareLabel)}` : `${pts > 0 ? "▲" : "▼"} ${Math.abs(pts)} points vs ${esc(compareLabel)}`}</div>`;
    }
    const rate = attr(hass, e.solar_energy_today, "rate_per_kwh");
    const saved = solar !== null && rate !== null ? solar * Number(rate) : null;
    const currency = hass.config?.currency;
    let savedText = "—";
    if (saved !== null) {
      try {
        savedText = currency
          ? new Intl.NumberFormat(hass.locale?.language, { style: "currency", currency, maximumFractionDigits: 0 }).format(saved)
          : Math.round(saved).toLocaleString();
      } catch (_) {
        savedText = Math.round(saved).toLocaleString();
      }
    }
    const co2 = solar === null ? null : solar * CO2_KG_PER_KWH;
    const trees = co2 === null ? 0 : co2 / TREE_KG_CO2_PER_YEAR;
    root.getElementById("score").innerHTML = `
      ${score === null ? "" : `
        <div class="center" style="font-size:13px;opacity:.75;font-weight:500">Your home ran on solar + battery</div>
        <div class="center score tabular" style="color:${c.solar};margin-top:4px">${Math.round(score * 100)}%</div>
        ${points}
        <div class="bar" style="background:${c.track}"><div style="width:${Math.round(score * 100)}%;background:${c.solar}"></div></div>
        <div class="ends"><span>Solar + battery</span><span>Grid ${100 - Math.round(score * 100)}%</span></div>`}
      ${row("icon-dollars", "Saved", savedText, "solar_energy_today", deltaHtml(solar, prev("solar_energy_today"), true))}
      ${row(svgIcon("leaf", c.solar), "CO2 avoided", co2 === null ? "—" : `${co2 >= 100 ? Math.round(co2) : co2.toFixed(1)} kg`, "solar_energy_today")}
      ${trees >= 1 ? row(svgIcon("tree", c.solar), "Like planting", `${Math.round(trees)} trees`, "solar_energy_today") : ""}`;

    // 2. Energy, compared with yesterday at this time.
    const energyRow = (icon, label, key, higherIsBetter) =>
      row(icon, label, kwh(v(key)), key, deltaHtml(v(key), prev(key), higherIsBetter));
    const exportKwh = v("grid_export_energy_today");
    root.getElementById("energy").innerHTML = `
      <div class="title">Energy</div>
      ${hasPrev && compareLabel ? `<div class="sub">Compared with ${esc(compareLabel)}</div>` : ""}
      <div style="height:8px"></div>
      ${energyRow("icon-solarpanel", "Solar energy", "solar_energy_today", true)}
      ${energyRow("icon-home", "Load consumed", "load_energy_today", null)}
      ${energyRow("icon-power-line", (exportKwh ?? 0) > 0 ? "Grid import" : "Grid energy", "grid_import_energy_today", false)}
      ${energyRow("icon-batterypower", "Battery used", "battery_discharge_energy_today", null)}
      ${energyRow("icon-solarbattery", "Solar charging", "solar_to_battery_energy_today", null)}
      ${energyRow("icon-charging", "Grid charging", "grid_to_battery_energy_today", null)}
      ${energyRow("icon-natural-disaster", "Total energy", "total_supplied_energy_today", null)}
      ${(exportKwh ?? 0) > 0 ? `<div class="title" style="margin-top:18px">Net metering</div>
        ${energyRow("icon-power-line", "Grid export", "grid_export_energy_today", true)}` : ""}`;

    // 3. Highlights.
    const peak = (key) => {
      const w = v(key);
      const t = attr(hass, e[key], "time");
      return w === null ? "—" : `${power(w)}${t ? ` at ${t}` : ""}`;
    };
    root.getElementById("highlights").innerHTML = `
      <div class="title">Highlights</div><div style="height:8px"></div>
      ${row("icon-solarpanel", "Peak solar", peak("peak_solar_power_today"), "peak_solar_power_today")}
      ${row("icon-home", "Peak load", peak("peak_load_power_today"), "peak_load_power_today")}
      ${row(svgIcon("gridOff", c.text), "Grid off", minutesText(v("grid_off_today")), "grid_off_today")}`;

    this._renderChart();
  }

  async _loadHistory() {
    const hass = this._hass;
    const e = this._e;
    if (!hass?.callWS || !e || !this.isConnected) return;
    const ids = CHART_SERIES.map((s) => e[s.key]).filter(Boolean);
    if (!ids.length) return;
    const hours = this._hours;
    const end = new Date();
    const start = new Date(end.getTime() - hours * 3600 * 1000);
    try {
      const res = await hass.callWS({
        type: "history/history_during_period",
        start_time: start.toISOString(),
        end_time: end.toISOString(),
        entity_ids: ids,
        minimal_response: true,
        no_attributes: true,
        significant_changes_only: false,
      });
      if (hours !== this._hours) return; // a newer range was picked meanwhile
      this._history = { start: start.getTime(), end: end.getTime(), data: res || {} };
    } catch (err) {
      this._history = { start: start.getTime(), end: end.getTime(), data: {}, error: String(err?.message || err) };
    }
    this._renderChart();
  }

  _renderChart() {
    const root = this.shadowRoot;
    const hass = this._hass;
    if (!root || !hass || !this._e) return;
    const c = palette(Boolean(hass.themes?.darkMode));
    root.querySelectorAll(".hours button").forEach((b) => {
      const on = Number(b.dataset.h) === this._hours;
      b.classList.toggle("on", on);
      b.style.background = on ? c.accent : "transparent";
    });
    const box = root.getElementById("chart");
    if (!box) return;
    const h = this._history;
    if (!h) {
      box.innerHTML = `<div class="nodata">Loading…</div>`;
      return;
    }
    const series = CHART_SERIES.map((s) => {
      const id = this._e[s.key];
      const points = (h.data[id] || [])
        .map((p) => ({ t: (p.lu ?? p.lc ?? 0) * 1000, v: Number(p.s) }))
        .filter((p) => Number.isFinite(p.v))
        .map((p) => ({ t: Math.max(p.t, h.start), v: p.v / 1000 }));
      return { ...s, id, points };
    }).filter((s) => s.points.length);
    if (!series.length) {
      box.innerHTML = `<div class="nodata">${h.error ? esc(h.error) : "No readings in this period yet."}</div>`;
      return;
    }
    const VW = 400;
    const VH = 200;
    const L = 34;
    const R = 8;
    const T = 8;
    const B = 22;
    const all = series.flatMap((s) => s.points.map((p) => p.v));
    let max = Math.max(0.5, ...all);
    let min = Math.min(0, ...all);
    const step = max - min > 6 ? 2 : max - min > 3 ? 1 : 0.5;
    max = Math.ceil(max / step) * step;
    min = Math.floor(min / step) * step;
    const x = (t) => L + ((t - h.start) / (h.end - h.start)) * (VW - L - R);
    const y = (val) => T + (1 - (val - min) / (max - min)) * (VH - T - B);
    const grid = [];
    for (let g = min; g <= max + 1e-9; g += step) {
      grid.push(`<line x1="${L}" x2="${VW - R}" y1="${y(g)}" y2="${y(g)}" stroke="${c.text}" stroke-opacity="${g === 0 ? 0.35 : 0.12}"/>
        <text x="${L - 6}" y="${y(g) + 3}" text-anchor="end" font-size="9" fill="${c.text}" fill-opacity=".7">${Math.round(g * 10) / 10}</text>`);
    }
    const timeFmt = (t) => new Date(t).toLocaleTimeString(hass.locale?.language, { hour: "2-digit", minute: "2-digit" });
    const ticks = [h.start, (h.start + h.end) / 2, h.end].map((t, i) =>
      `<text x="${x(t)}" y="${VH - 6}" font-size="9" fill="${c.text}" fill-opacity=".7" text-anchor="${["start", "middle", "end"][i]}">${timeFmt(t)}</text>`);
    const lines = series.map((s) => {
      // A step line: each reading holds until the next one, up to now.
      let d = "";
      s.points.forEach((p, i) => {
        const px = x(p.t).toFixed(1);
        const py = y(p.v).toFixed(1);
        d += i === 0 ? `M${px},${py}` : `H${px}V${py}`;
      });
      d += `H${x(h.end).toFixed(1)}`;
      return `<path d="${d}" fill="none" stroke="${s.color(c)}" stroke-width="1.8" stroke-linejoin="round"/>`;
    });
    box.innerHTML = `
      <svg viewBox="0 0 ${VW} ${VH}" role="img" aria-label="Power over the last ${this._hours} hours">
        <text x="4" y="12" font-size="9" fill="${c.text}" fill-opacity=".7">kW</text>
        ${grid.join("")}${lines.join("")}${ticks.join("")}
      </svg>
      <div class="legend">${series.map((s) => `<span style="--dot:${s.color(c)}">${s.name}</span>`).join("")}</div>`;
  }
}

// ======================================================================= editor
class InverterzoneCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = { ...config };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  _render() {
    if (!this._hass || !this._config) return;
    const ids = inverterDevices(this._hass);
    const current = this._config.device_id || ids[0] || "";
    const key = ids.join(",") + current;
    if (key === this._key) return;
    this._key = key;
    this.innerHTML = `
      <style>
        .iz-editor { display: flex; flex-direction: column; gap: 6px; padding: 8px 0; }
        .iz-editor select { font: inherit; padding: 10px; border-radius: 6px; border: 1px solid var(--divider-color, #ccc);
                            background: var(--card-background-color, #fff); color: var(--primary-text-color, #000); }
        .iz-editor label { font-size: 12px; color: var(--secondary-text-color, #666); }
      </style>
      <div class="iz-editor">
        <label for="iz-device">Inverter</label>
        ${ids.length
          ? `<select id="iz-device">${ids.map((id) => `<option value="${esc(id)}" ${id === current ? "selected" : ""}>${esc(deviceName(this._hass, id))}</option>`).join("")}</select>`
          : "<div>No inverterzone inverter found. Add the inverterzone integration first.</div>"}
      </div>`;
    this.querySelector("select")?.addEventListener("change", (ev) => {
      this._config = { ...this._config, device_id: ev.target.value };
      this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: this._config }, bubbles: true, composed: true }));
    });
  }
}

// ======================================================================= sidebar page
// The "inverterzone" page in Home Assistant's sidebar: both cards, no dashboard editing.
// Side by side on wide screens; Realtime / Stats tabs (like the app) on phones.
const PANEL_DEVICE_KEY = "inverterzone-panel-device";
const PANEL_WIDE_PX = 900;

class InverterzonePanel extends HTMLElement {
  constructor() {
    super();
    this._tab = "realtime";
  }

  set hass(hass) {
    this._hass = hass;
    this._update();
  }

  set narrow(narrow) {
    this._narrow = narrow;
    this._update();
  }

  set panel(panel) {
    this._panel = panel;
  }

  set route(route) {
    this._route = route;
  }

  connectedCallback() {
    this._resize = new ResizeObserver(() => this._update());
    this._resize.observe(this);
    this._update();
  }

  disconnectedCallback() {
    this._resize?.disconnect();
  }

  _savedDevice() {
    try {
      return localStorage.getItem(PANEL_DEVICE_KEY);
    } catch (_) {
      return null;
    }
  }

  _saveDevice(id) {
    try {
      localStorage.setItem(PANEL_DEVICE_KEY, id);
    } catch (_) {
      // Private mode or blocked storage: the choice just isn't remembered.
    }
  }

  _build() {
    const root = this.attachShadow({ mode: "open" });
    root.innerHTML = `
      <style>
        :host { display: block; min-height: 100vh; background: var(--primary-background-color, #fafafa);
                color: var(--primary-text-color, #212121); font-family: var(--ha-font-family-body, Roboto, Arial, sans-serif); }
        [hidden] { display: none !important; }
        .toolbar { position: sticky; top: 0; z-index: 2; display: flex; align-items: center; gap: 8px; box-sizing: border-box;
                   height: var(--header-height, 56px); padding: 0 12px;
                   background: var(--app-header-background-color, var(--primary-color, #03a9f4));
                   color: var(--app-header-text-color, #fff); border-bottom: var(--app-header-border-bottom, none); }
        .title { flex: 1; margin-left: 4px; font-size: 20px; font-weight: 400; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        select { font: inherit; font-size: 14px; max-width: 45%; padding: 6px 8px; border-radius: 8px; color: inherit;
                 background: rgba(255, 255, 255, .15); border: 1px solid rgba(255, 255, 255, .35); }
        select option { color: #212121; }
        .tabs { display: flex; justify-content: center; gap: 8px; padding: 12px 16px 0; }
        .tabs button { flex: 1; max-width: 220px; padding: 9px 12px; border-radius: 20px; cursor: pointer; font: inherit;
                       font-size: 14px; font-weight: 600; color: inherit; background: transparent; border: 1px solid rgba(127, 127, 127, .35); }
        .tabs button.on { color: #fff; background: #00B33C; border-color: transparent; }
        .content { display: flex; flex-wrap: wrap; justify-content: center; align-items: flex-start; gap: 16px; padding: 16px; }
        .col { width: 100%; max-width: 460px; min-width: 0; }
        .empty { padding: 48px 16px; text-align: center; opacity: .7; }
      </style>
      <div class="toolbar">
        <span id="menu"></span>
        <div class="title">inverterzone</div>
        <select id="device" aria-label="Inverter" hidden></select>
      </div>
      <div id="tabs" class="tabs" hidden>
        <button data-tab="realtime">Realtime</button>
        <button data-tab="stats">Stats</button>
      </div>
      <div id="content" class="content">
        <div id="col-realtime" class="col"></div>
        <div id="col-stats" class="col"></div>
      </div>
      <div id="empty" class="empty" hidden>No inverterzone inverter found. Add the inverterzone integration first.</div>`;

    // Home Assistant's own menu button: opens the sidebar on phones.
    this._menu = document.createElement("ha-menu-button");
    root.getElementById("menu").appendChild(this._menu);

    this._flow = document.createElement("inverterzone-flow-card");
    this._stats = document.createElement("inverterzone-stats-card");
    root.getElementById("col-realtime").appendChild(this._flow);
    root.getElementById("col-stats").appendChild(this._stats);

    root.getElementById("device").addEventListener("change", (ev) => {
      this._device = ev.target.value;
      this._saveDevice(this._device);
      this._update();
    });
    root.querySelectorAll(".tabs button").forEach((b) =>
      b.addEventListener("click", () => {
        this._tab = b.dataset.tab;
        this._update();
      }),
    );
  }

  _update() {
    if (!this._hass) return;
    if (!this.shadowRoot) this._build();
    const root = this.shadowRoot;
    const hass = this._hass;

    this._menu.hass = hass;
    this._menu.narrow = this._narrow;

    const ids = inverterDevices(hass);
    root.getElementById("empty").hidden = ids.length > 0;
    root.getElementById("content").hidden = ids.length === 0;
    if (!ids.length) {
      root.getElementById("tabs").hidden = true;
      return;
    }

    const saved = this._savedDevice();
    const id = ids.includes(this._device) ? this._device : ids.includes(saved) ? saved : ids[0];

    // Inverter picker, only when there is a choice.
    const select = root.getElementById("device");
    select.hidden = ids.length < 2;
    const optionsKey = ids.map((d) => `${d}=${deviceName(hass, d)}`).join("|");
    if (optionsKey !== this._optionsKey) {
      this._optionsKey = optionsKey;
      select.innerHTML = ids.map((d) => `<option value="${esc(d)}">${esc(deviceName(hass, d))}</option>`).join("");
    }
    select.value = id;

    if (id !== this._configured) {
      this._configured = id;
      this._flow.setConfig({ type: "custom:inverterzone-flow-card", device_id: id });
      this._stats.setConfig({ type: "custom:inverterzone-stats-card", device_id: id });
    }
    this._flow.hass = hass;
    this._stats.hass = hass;

    // Side by side when there is room, otherwise app-style tabs.
    const tabs = Boolean(this._narrow) || (this.clientWidth > 0 && this.clientWidth < PANEL_WIDE_PX);
    root.getElementById("tabs").hidden = !tabs;
    root.querySelectorAll(".tabs button").forEach((b) => b.classList.toggle("on", b.dataset.tab === this._tab));
    root.getElementById("col-realtime").hidden = tabs && this._tab !== "realtime";
    root.getElementById("col-stats").hidden = tabs && this._tab !== "stats";
  }
}

// ======================================================================= register
const define = (name, cls) => {
  if (!customElements.get(name)) customElements.define(name, cls);
};
define("inverterzone-flow-card", InverterzoneFlowCard);
define("inverterzone-stats-card", InverterzoneStatsCard);
define("inverterzone-card-editor", InverterzoneCardEditor);
define("inverterzone-panel", InverterzonePanel);

window.customCards = window.customCards || [];
for (const card of [
  {
    type: "inverterzone-flow-card",
    name: "inverterzone flow",
    description: "Live energy flow between solar, battery, grid and load, like the inverterzone app.",
  },
  {
    type: "inverterzone-stats-card",
    name: "inverterzone stats",
    description: "Today's solar score, energy totals with yesterday's comparison, highlights and a live power chart.",
  },
]) {
  if (!window.customCards.some((c) => c.type === card.type)) {
    window.customCards.push({ ...card, preview: true, documentationURL: "https://github.com/Hamadme50/inverterzone-homeassistant" });
  }
}

console.info(`%c inverterzone cards %c ${VERSION} `, "background:#00B33C;color:#fff;border-radius:3px 0 0 3px", "background:#3A6372;color:#fff;border-radius:0 3px 3px 0");
