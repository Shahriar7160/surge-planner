// S.U.R.G.E. deployment planner: pick a candidate site → set confirmed patients → adjust the generated wards.
import { makeBrief, makeLayout, checkLayout, KIT, toLonLat, briefsGhCsv, people, communityProgramme, communityLayout } from "./engine.js";

const $ = (id) => document.getElementById(id);
const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const fmt = (v, d = 0) => Number(v).toLocaleString("en-GB", { maximumFractionDigits: d, minimumFractionDigits: d });
const SITE_CAP = 120;                       // step 2: at most 10 modules (120 confirmed beds) per site

const SHOULD_LABEL = {
  cell_coverage: "Phone coverage", near_hospital: "Near a hospital", helipad_space: "Helipad space",
  rainy_access: "Rainy-season access", border_flow: "Border flow", waste_downhill: "Waste runs downhill",
  burial_space: "Land to spare", community_acceptance: "Away from forest", fuel_supply: "Fuel and markets",
};
const ROOM_LABEL = {
  triage: "triage", family_visiting: "family", patient_corridor: "", patient_discharge: "discharge",
  laundry: "laundry", morgue: "morgue", incinerator_waste: "incinerator", admin_data: "admin", lab: "lab",
  pharmacy: "pharmacy", stores: "stores", staff_rest: "staff rest", water_treatment: "water", generator: "generator",
  loading_zone: "loading", staff_dormitory: "staff dormitory", burial_area: "burial area",
};
const SLIDERS = [
  ["MAX_MODULES_PER_ROW", "Modules per row", 2, 8, 1, "", "shorter rows, shorter staff walks"],
  ["BAY", "Structural bay", 4.8, 7.2, 0.6, " m", "every support room is whole bays"],
  ["ROW_GAP", "Gap between rows", 2, 6, 0.5, " m", "one-way corridor between ward rows"],
  ["PATIENT_CORRIDOR", "Patient corridor", 2, 5, 0.5, " m", ""],
  ["GREEN_COL_BAYS", "Low-risk column", 1, 3, 1, " bays", "admin, lab, pharmacy, stores, staff rest"],
  ["FENCE_GAP", "Double fence gap", 1, 3, 0.5, " m", ""],
  ["OUTER_MARGIN", "Margin to outer fence", 3, 12, 1, " m", ""],
];

const S = {
  site: null, limit: 90, rain: false, confirmed: 120, kit: { ...KIT }, rotation: 0, mirrored: false,
  showOutside: false, view: "plan", brief: null, layout: null, checks: null,
  phase: "ward", comm: null,                // "ward" (2014) or "after" (the outbreak is over)
};
const GROUP_LABEL = { care: "care", work: "work", gather: "gather", learn: "learn", garden: "garden", street: "street", service: "service" };
let D = {};                                 // data
let map, layers = {};
let three = null;

// ---------------------------------------------------------------- data
async function load() {
  const get = (p) => fetch(p).then((r) => { if (!r.ok) throw new Error(`${p}: ${r.status}`); return r; });
  const [cand, patches, lay, travel, module] = await Promise.all(
    ["candidates", "patches", "layers", "travel", "module"].map((n) => get(`data/${n}.json`).then((r) => r.json())));
  const bytes = (b64) => Uint8Array.from(atob(b64), (ch) => ch.charCodeAt(0));
  D = { meta: cand.meta, C: cand.candidates, P: patches, L: lay, M: module, T: { dry: bytes(travel.dry), rain: bytes(travel.rain) } };
  const scores = D.C.map((c) => c.score);
  D.smin = Math.min(...scores); D.smax = Math.max(...scores);
  const order = [...D.C].sort((a, b) => b.score - a.score);
  order.forEach((c, i) => (c.rank = i + 1));
  D.briefBySite = Object.fromEntries(D.L.sites.map((s) => [s.site_id, s]));
}

function minutes(c, p) { return (S.rain ? D.T.rain : D.T.dry)[c.id * D.P.length + p]; }
function catchment(c) {
  const served = [];
  D.P.forEach((p, i) => { const t = minutes(c, i); if (t <= S.limit) served.push({ ...p, t }); });
  return {
    served, people: served.reduce((a, p) => a + p.pop, 0),
    demand: served.reduce((a, p) => a + p.peak_beds, 0),
    cases: served.reduce((a, p) => a + p.cases_total, 0),
  };
}
function defaultConfirmed(c) {
  if (c.surge) return D.briefBySite[c.surge].peak_confirmed_beds;
  const d = catchment(c).demand;
  return Math.max(6, Math.min(SITE_CAP, Math.round(d)));
}

// ---------------------------------------------------------------- map
function mix(a, b, t) {
  const p = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
  const A = p(a), B = p(b);
  return "#" + A.map((v, i) => Math.round(v + (B[i] - v) * t).toString(16).padStart(2, "0")).join("");
}
function scoreColor(s) {
  const t = (s - D.smin) / (D.smax - D.smin || 1);
  return mix(css("--ramp-lo"), css("--accent"), t);
}

function initMap() {
  map = L.map("map", { preferCanvas: true, zoomSnap: 0.25, attributionControl: true, minZoom: 8, maxZoom: 19 });
  map.attributionControl.setPrefix(false).addAttribution("Roads: OSM 2014 · Boundaries: geoBoundaries · Sites: S.U.R.G.E.");
  layers.land = L.geoJSON(D.L.prefectures, { interactive: false }).addTo(map);
  layers.roads = L.geoJSON(D.L.roads, { interactive: false }).addTo(map);
  layers.patches = L.layerGroup().addTo(map);
  layers.hosp = L.layerGroup().addTo(map);
  layers.links = L.layerGroup().addTo(map);
  layers.cands = L.layerGroup().addTo(map);
  layers.foot = L.layerGroup().addTo(map);
  layers.surge = L.layerGroup();                 // shown only after the first pick, for comparison
  layers.sel = L.layerGroup().addTo(map);

  D.C.forEach((c) => {
    const m = L.circleMarker([c.lat, c.lon], { radius: 3.6, weight: 0.6 });
    m.bindTooltip(() => `<b>${c.near}</b> · score ${c.score.toFixed(2)} · rank ${c.rank} of ${D.C.length}`, { direction: "top" });
    m.on("click", () => select(c));
    m._c = c;
    layers.cands.addLayer(m);
  });
  D.C.filter((c) => c.surge).forEach((c) => {
    const m = L.circleMarker([c.lat, c.lon], { radius: 9, weight: 2.5 });
    m.bindTooltip(c.surge, { permanent: true, direction: "right", offset: [8, 0], className: "site-label" });
    m.on("click", () => select(c));
    layers.surge.addLayer(m);
  });
  D.P.forEach((p) => {
    const m = L.circleMarker([p.lat, p.lon], { radius: 2, weight: 0, interactive: true });
    m.bindTooltip(() => `${p.name} · ${fmt(p.pop)} people · peak ${fmt(p.peak_beds, 1)} beds`, { direction: "top" });
    m._p = p;
    layers.patches.addLayer(m);
  });
  D.L.hospitals.features.forEach((f) => {
    const [lon, lat] = f.geometry.coordinates;
    const m = L.circleMarker([lat, lon], { radius: f.properties.level >= 4 ? 4.5 : 2.5, weight: 0 });
    m.bindTooltip(f.properties.name, { direction: "top" });
    layers.hosp.addLayer(m);
  });
  restyleMap();
  zoomAll();
  const detail = () => {
    const near = map.getZoom() >= 14;
    for (const k of ["links", "sel"]) near ? map.removeLayer(layers[k]) : layers[k].addTo(map);
  };
  map.on("zoomend", detail);
}

function restyleMap() {
  const land = css("--land"), line = css("--land-line"), road = css("--road"), main = css("--road-main");
  layers.land.setStyle({ color: line, weight: 1, fillColor: land, fillOpacity: 1 });
  layers.roads.setStyle((f) => {
    const t = f.properties.t;
    const big = ["trunk", "primary", "secondary"].includes(t);
    return { color: big ? main : road, weight: big ? 2 : t === "tertiary" ? 1.3 : 0.7, opacity: 0.9 };
  });
  layers.cands.eachLayer((m) => m.setStyle({ color: css("--panel"), fillColor: scoreColor(m._c.score), fillOpacity: 1 }));
  layers.surge.eachLayer((m) => m.setStyle({ color: css("--ink"), fillColor: css("--panel"), fillOpacity: 1 }));
  if (!S.site) layers.patches.eachLayer((m) => m.setStyle({ radius: 2, fillColor: css("--muted"), fillOpacity: 0.5 }));
  layers.hosp.eachLayer((m) => m.setStyle({ fillColor: css("--green"), fillOpacity: 0.9 }));
  drawCatchment();
  drawFootprint();
}

function zoomAll() { map.fitBounds([[8.0, -10.83], [9.23, -9.03]], { padding: [10, 10] }); }
function zoomSite() {
  if (!S.layout) return;
  const [fx, fy, fw, fh] = S.layout.fences.outer;
  const r = Math.max(fw, fh) * 1.2;
  map.fitBounds([[S.site.lat - r / 110570, S.site.lon - r / 109400], [S.site.lat + r / 110570, S.site.lon + r / 109400]]);
}

function drawCatchment() {
  if (!S.site) return;
  const c = S.site, cm = catchment(c);
  const served = new Map(cm.served.map((p) => [p.id, p]));
  const amber = css("--amber"), muted = css("--muted"), accent = css("--accent");
  layers.patches.eachLayer((m) => {
    const p = served.get(m._p.id);
    m.setStyle(p ? { radius: 3 + Math.sqrt(p.peak_beds) * 1.6, fillColor: amber, fillOpacity: 0.75 }
                 : { radius: 2, fillColor: muted, fillOpacity: 0.5 });
  });
  layers.links.clearLayers();
  cm.served.forEach((p) => layers.links.addLayer(L.polyline([[c.lat, c.lon], [p.lat, p.lon]],
    { color: accent, weight: 1, opacity: 0.45, interactive: false })));
  layers.sel.clearLayers();
  layers.sel.addLayer(L.circleMarker([c.lat, c.lon], { radius: 13, color: accent, weight: 3, fill: false, interactive: false }));
}

const shown = () => (S.phase === "after" && S.comm ? S.comm.layout : S.layout);

function footprintFeatures() {
  const L_ = shown(), [fx, fy, fw, fh] = L_.fences.outer, cx = fx + fw / 2, cy = fy + fh / 2;
  const ring = (x, y, w, h) => [[x, y], [x + w, y], [x + w, y + h], [x, y + h], [x, y]]
    .map(([a, b]) => toLonLat(a, b, S.site, S.rotation, S.mirrored, cx, cy));
  const parts = L_.rects.filter((r) => S.showOutside || !["staff_dormitory", "burial_area"].includes(r.name));
  const feats = parts.map((r) => ({ type: "Feature", properties: { name: r.name, zone: r.zone, kind: r.kind, ward: r.ward || null, program: r.program || null },
    geometry: { type: "Polygon", coordinates: [ring(r.x, r.y, r.w, r.h)] } }));
  feats.push({ type: "Feature", properties: { name: "outer_fence", zone: "fence", kind: "fence" },
    geometry: { type: "Polygon", coordinates: [ring(fx, fy, fw, fh)] } });
  return feats;
}
function zoneColor(r) {
  if (r.kind === "ward_module") return css(`--${r.ward}`);
  if (r.program || r.kind === "community_module") return css(`--g-${r.zone}`);
  return css(`--${r.zone === "service" ? "service" : r.zone}`);
}
function drawFootprint() {
  if (!S.layout) return;
  layers.foot.clearLayers();
  for (const f of footprintFeatures()) {
    const ll = f.geometry.coordinates[0].map(([lon, lat]) => [lat, lon]);
    const fence = f.properties.zone === "fence";
    layers.foot.addLayer(L.polygon(ll, fence
      ? { color: css("--ink"), weight: 1.5, dashArray: "4 3", fill: false, interactive: false }
      : { color: css("--ink"), weight: 0.4, fillColor: zoneColor(f.properties), fillOpacity: 0.9, interactive: false }));
  }
}

// ---------------------------------------------------------------- panel
function siteCard() {
  const c = S.site, cm = catchment(c);
  const should = D.meta.should;
  const top = should.map((k, i) => [k, c.should[i], D.meta.weights[i]]);
  const surgeOpts = D.L.sites.map((s) => `<option value="${s.site_id}" ${c.surge === s.site_id ? "selected" : ""}>${s.site_id} · ${s.near}</option>`).join("");
  $("site-card").innerHTML = `
    <div class="site-name"><strong>${c.near}</strong>
      ${c.surge ? `<span class="chip surge">optimised ${c.surge}</span>` : `<span class="chip">candidate #${c.id}</span>`}
      <span class="chip">rank ${c.rank} / ${D.C.length}</span></div>
    <p class="note">Passed all ten MUST filters (${fmt(D.meta.funnel[0]?.remaining ?? 68885)} grid cells → ${D.C.length}).
      ${c.near_km} km from ${c.near} · ${c.lat.toFixed(4)}°, ${c.lon.toFixed(4)}°</p>
    <dl class="facts">
      <div><dt>SHOULD score</dt><dd>${c.score.toFixed(2)}</dd></div>
      <div><dt>To hospital</dt><dd>${fmt(c.t_hospital_h * 60)} min</dd></div>
      <div><dt>To road</dt><dd>${fmt(c.road_m)} m</dd></div>
    </dl>
    <ul class="bars" aria-label="SHOULD criteria">${top.map(([k, v, w]) => `
      <li><span>${SHOULD_LABEL[k]} <span class="w">×${w}</span></span><span class="track"><span class="fill" style="width:${v * 100}%"></span></span><span class="v">${v.toFixed(2)}</span></li>`).join("")}
    </ul>
    <label class="field">Jump to an optimised site
      <select id="jump"><option value="">Choose…</option>${surgeOpts}</select></label>`;
  $("jump").onchange = (e) => { const c2 = D.C.find((x) => x.surge === e.target.value); if (c2) { select(c2); zoomSite(); } };
  const season = S.rain ? "rainy" : "dry";
  $("catchment").innerHTML = `Reaches <b>${cm.served.length}</b> of ${D.P.length} settlements
    (${fmt(cm.people)} people) within ${S.limit / 60} h in the ${season} season. Their modelled peak demand adds up to
    <b>${fmt(cm.demand, 1)}</b> confirmed beds. Neighbouring sites share some of it, so the suggested value is capped at
    one site's capacity (${SITE_CAP} beds = 10 modules).`;
}

function moduleCard() {
  const m = D.M, mt = m.metrics, hrs = m.deployment.reduce((a, s) => a + s.crew_min, 0) / 60;
  return `<div class="modcard"><h3>Ward module · ${m.label}</h3>
    <figure class="fold"><img src="data/fold.gif" alt="The ward skin folding from one flat sheet into the vault and back" loading="lazy">
      <figcaption>Folding study: edge lengths fixed, hinge angles driven, feet anchored. One flat sheet → vault → flat pack.</figcaption></figure>
    <p class="note">Chosen from 58 fold variants (step 6): aluminium frame that folds flat, ${D.M.faces.length} washable triangular
    panels of ${mt.unique_panels} shapes (${mt.panels} sheet pieces) that fold from one flat sheet (angle error ${mt.flat_fold_err_deg}°),
    roof facets ≥ ${Math.round(mt.min_slope_deg)}° because the wettest month of 2014 had
    ${m.rule.wettest_month_mm} mm of rain. About ${fmt(hrs, 0)} crew-hours to deploy.</p></div>`;
}

function communityPanel() {
  const k = S.comm, p = k.people;
  const rows = k.prog.map((x) => `<tr><td><i class="sw" style="background:var(--g-${x.group})"></i>${x.space}</td>
    <td>${x.people == null ? "1 per site" : fmt(x.people)}</td><td><b>${x.modules}</b></td></tr>`).join("");
  $("brief").innerHTML = `
    <p class="note">${S.site.surge ? "This site's share of" : "Settlements within reach:"} <b>${fmt(p.cases)}</b> cases since Dec 2013 →
      ${fmt(p.survivors)} survivors, ${fmt(p.children)} children who lost a parent or caregiver, ${fmt(p.households)} affected households.</p>
    <table class="prog"><thead><tr><th>Space</th><th>People</th><th>Modules</th></tr></thead><tbody>${rows}</tbody></table>
    <dl class="kv">
      <div><dt>Modules needed</dt><dd>${k.need}</dd></div>
      <div><dt>Reused from the ward</dt><dd>${Math.min(k.need, k.have)}</dd></div>
      <div><dt>${k.need > k.have ? "New from stock" : "Back to stock"}</dt><dd>${Math.abs(k.need - k.have)}</dd></div>
      <div><dt>Red fence</dt><dd>removed</dd></div>
    </dl>
    <p class="note">Same frames, new skin: timber louvres below 1.2 m for cross-ventilation, translucent diamonds above.</p>`;
}

function briefPanel() {
  if (S.phase === "after") return communityPanel();
  const b = S.brief, c = S.site, ck = S.checks;
  const w = Object.fromEntries(b.wards.map((x) => [x.ward, x]));
  const fits = b.area.plot_m2 <= c.buildable_m2;
  $("brief").innerHTML = `
    <div class="modules">
      ${["suspect", "probable", "confirmed"].map((k) => `<div class="mod ${k}"><b>${w[k].modules}</b><span>${k} · ${w[k].beds} beds</span></div>`).join("")}
    </div>
    <dl class="kv">
      <div><dt>Beds</dt><dd>${b.beds_total}</dd></div>
      <div><dt>Modules</dt><dd>${b.modules_total}</dd></div>
      <div><dt>Staff</dt><dd>${b.staff_total} (${b.staff_per_shift}/shift)</dd></div>
      <div><dt>Water</dt><dd>${fmt(b.supplies.water_l_day / 1000)} m³/day</dd></div>
      <div><dt>Power</dt><dd>${b.supplies.power_kw} kW</dd></div>
      <div><dt>PPE sets</dt><dd>${fmt(b.supplies.ppe_sets_day)}/day</dd></div>
      <div><dt>Plot needed</dt><dd>${fmt(b.area.plot_m2 / 10000, 2)} ha</dd></div>
      <div><dt>Land within 300 m</dt><dd>${fmt(c.buildable_m2 / 10000, 1)} ha</dd></div>
    </dl>
    ${fits ? "" : `<p class="warn">The plot does not fit the buildable land around this site. Choose a site with more land or split the demand.</p>`}
    ${S.confirmed > SITE_CAP ? `<p class="warn">${fmt(S.confirmed)} confirmed patients is more than one site's capacity (${SITE_CAP}). The layout is still generated; in the plan, a second site would share the load.</p>` : ""}
    ${moduleCard()}`;
}

function buildSliders() {
  $("sliders").innerHTML = SLIDERS.map(([k, label, min, max, step, unit, hint]) => `
    <label class="slider" for="k-${k}"><span>${label} <output id="o-${k}"></output></span>
      <input id="k-${k}" type="range" min="${min}" max="${max}" step="${step}" value="${S.kit[k]}">
      ${hint ? `<small>${hint}</small>` : ""}</label>`).join("");
  SLIDERS.forEach(([k, , , , , unit]) => {
    const el = $(`k-${k}`), out = $(`o-${k}`);
    const show = () => (out.textContent = `${fmt(S.kit[k], k === "BAY" ? 1 : String(S.kit[k]).includes(".") ? 1 : 0)}${unit}`);
    show();
    el.oninput = () => { S.kit[k] = Number(el.value); show(); update(); };
  });
}

function syncPlacementInputs() {
  $("rotation").value = S.rotation; $("rotation-out").textContent = `${fmt(S.rotation)}°`;
  $("mirrored").checked = S.mirrored;
}

function checksPanel() {
  if (S.phase === "after") {
    const k = S.comm, [, , fw, fh] = k.layout.fences.outer;
    const ov = k.layout.rects.filter((a, i, R) => R.slice(i + 1).some((b) => Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x) > .01
      && Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y) > .01)).length;
    $("checks").innerHTML = [[true, "Modules", `${k.need} (${Math.min(k.need, k.have)} reused)`], [!ov, "Overlaps", ov],
      [true, "Fenced", `${Math.round(fw)} × ${Math.round(fh)} m`], [true, "Red fence", "removed"]]
      .map(([ok, l, v]) => `<li class="${ok ? "ok" : "bad"}">${l} <b>${v}</b></li>`).join("");
    $("design-title").textContent = `${S.site.surge ?? "Candidate"} · ${S.site.near} · after the outbreak`;
    $("design-sub").textContent = `Community centre: the same kit and rules, a new brief sized by survivors and bereaved families`;
    return;
  }
  const k = S.checks, b = S.brief, c = S.site;
  const items = [
    [k.beds_match, "Beds", `${k.beds_in_layout} / ${k.beds_in_brief}`],
    [!k.overlaps.length, "Overlaps", k.overlaps.length],
    [!k.red_green_contacts.length, "Red–green contact", k.red_green_contacts.length],
    [k.staff_walk_ok, "Longest staff walk", `${fmt(k.max_staff_walk_m, 1)} / ${KIT.MAX_STAFF_WALK_M} m`],
    [true, "Patient route", `${fmt(k.patient_path_m, 1)} m`],
    [true, "Fenced", `${k.fenced_size_m[0]} × ${k.fenced_size_m[1]} m`],
    [b.area.plot_m2 <= c.buildable_m2, "Plot fits", b.area.plot_m2 <= c.buildable_m2 ? "yes" : "no"],
  ];
  $("checks").innerHTML = items.map(([ok, label, v]) => `<li class="${ok ? "ok" : "bad"}">${label} <b>${v}</b></li>`).join("");
  $("design-title").textContent = `${c.surge ?? "Candidate"} · ${c.near}`;
  $("design-sub").textContent = `${b.beds_total} beds in ${b.modules_total} ward modules of 12 · rows of up to ${S.kit.MAX_MODULES_PER_ROW} · ` +
    (k.ok ? "all layout rules pass" : "a layout rule fails, see below");
}

// ---------------------------------------------------------------- plan (SVG)
function planSVG() {
  const L_ = shown(), after = S.phase === "after";
  const parts = L_.rects.filter((r) => S.showOutside || !["staff_dormitory", "burial_area"].includes(r.name));
  const [fx, fy, fw, fh] = L_.fences.outer;
  let x0 = Math.min(fx, ...parts.map((r) => r.x)), y0 = Math.min(fy, ...parts.map((r) => r.y));
  let x1 = Math.max(fx + fw, ...parts.map((r) => r.x + r.w)), y1 = Math.max(fy + fh, ...parts.map((r) => r.y + r.h));
  const pad = 10; x0 -= pad; y0 -= pad + 4; x1 += pad; y1 += pad + 6;
  const Y = (y) => y1 - y + y0;                       // flip: road at the bottom
  const fs = Math.max(2, Math.min(3.4, (x1 - x0) / 38));
  const fill = (r) => r.kind === "ward_module" ? `var(--${r.ward})` : r.program ? `var(--g-${r.zone})`
    : r.kind === "corridor" ? "var(--accent-soft)" : `var(--${r.zone})`;
  const rects = parts.map((r) => {
    const label = r.program ? (["washroom", "storage", "covered street"].includes(r.program) ? "" : r.program)
      : r.kind === "ward_module" ? r.name.split("_M")[0][0].toUpperCase() + r.name.split("_M")[1]
      : r.kind === "donning" ? "don" : r.kind === "doffing" ? "doff" : r.kind === "store" ? "PPE" : ROOM_LABEL[r.name] ?? r.name;
    const tall = r.h > r.w * 1.5 && r.w < 10;
    const cx = r.x + r.w / 2, cy = Y(r.y + r.h / 2);
    let size = r.kind === "ward_module" || ["donning", "doffing", "store"].includes(r.kind) ? fs * 0.75 : fs;
    const room = (tall ? r.h : r.w) - 1;
    size = Math.min(size, room / (0.58 * Math.max(1, label.length)), (tall ? r.w : r.h) * 0.6);
    const op = r.kind === "ward_module" || r.kind === "corridor" ? 1 : 0.82;
    const txt = label && size >= 1.1 ? `<text x="${cx}" y="${cy}" font-size="${size}" text-anchor="middle" dominant-baseline="central"
      ${tall ? `transform="rotate(-90 ${cx} ${cy})"` : ""} ${r.ward === "confirmed" || (r.program && ["care", "learn", "gather"].includes(r.zone)) ? 'style="fill:#fff"' : ""}>${label}</text>` : "";
    return `<g><title>${r.name.replace(/_/g, " ")} · ${fmt(r.w, 1)} × ${fmt(r.h, 1)} m</title>
      <rect x="${r.x}" y="${Y(r.y + r.h)}" width="${r.w}" height="${r.h}" style="fill:${fill(r)};fill-opacity:${op};stroke:var(--ink);stroke-width:.15"/>${txt}</g>`;
  }).join("");
  const red = L_.fences.red_inner;
  const flow = L_.patient_flow.map(([x, y]) => `${x},${Y(y)}`).join(" ");
  const sb = 10, sbx = x0 + 3, sby = Y(y0) - 3;
  return `<svg viewBox="${x0} ${Y(y1)} ${x1 - x0} ${y1 - y0}" role="img" aria-label="Generated ward layout plan">
    <defs><marker id="arr" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="4" markerHeight="4" orient="auto-start-reverse">
      <path d="M0,0 L10,5 L0,10 z" style="fill:var(--accent)"/></marker></defs>
    <rect x="${fx}" y="${Y(fy + fh)}" width="${fw}" height="${fh}" style="fill:none;stroke:var(--ink);stroke-width:.35;stroke-dasharray:1.6 1"/>
    ${rects}
    ${red ? `<rect x="${red[0]}" y="${Y(red[1] + red[3])}" width="${red[2]}" height="${red[3]}" style="fill:none;stroke:var(--red);stroke-width:.3;stroke-dasharray:.6 .6"/>` : ""}
    <polyline points="${flow}" style="fill:none;stroke:${after ? "var(--muted)" : "var(--accent)"};stroke-width:.7" ${after ? "" : 'marker-end="url(#arr)"'}/>
    <text x="${fx}" y="${Y(fy + fh) - 2}" font-size="${fs}" style="fill:var(--muted)">outer fence ${fmt(fw)} × ${fmt(fh)} m · ${after ? "the red fence is gone; the patient route is a covered street" : "patient route in blue · red fence dotted"}</text>
    <text x="${(x0 + x1) / 2}" y="${Y(y0) - 2}" font-size="${fs}" text-anchor="middle" style="fill:var(--muted)">road side ↓ · ${after ? "everyone enters at the old triage, now the reception" : "patients enter at triage"}</text>
    <line x1="${sbx}" y1="${sby}" x2="${sbx + sb}" y2="${sby}" style="stroke:var(--ink);stroke-width:.5"/>
    <text x="${sbx + sb / 2}" y="${sby - 1}" font-size="${fs * 0.8}" text-anchor="middle">10 m</text>
  </svg>`;
}

// ---------------------------------------------------------------- 3D
function init3D() {
  const el = $("three");
  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(2, devicePixelRatio));
  el.appendChild(renderer.domElement);
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(35, 1, 1, 5000);
  const controls = new THREE.OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  scene.add(new THREE.HemisphereLight(0xffffff, 0x8899aa, 0.85));
  const sun = new THREE.DirectionalLight(0xffffff, 0.55); sun.position.set(-80, 160, 60); scene.add(sun);
  const group = new THREE.Group(); scene.add(group);
  three = { el, renderer, scene, camera, controls, group, framed: false };
  const resize = () => {
    const w = el.clientWidth, h = el.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix();
  };
  new ResizeObserver(resize).observe(el); resize();
  const loop = () => { if (S.view === "3d") { controls.update(); renderer.render(scene, camera); } requestAnimationFrame(loop); };
  loop();
}
let MODULE_GEO = null;
function moduleGeometry() {
  if (MODULE_GEO) return MODULE_GEO;
  const V = D.M.vertices, pos = [];
  for (const f of D.M.faces) for (let i = 1; i < f.length - 1; i++)
    for (const k of [f[0], f[i], f[i + 1]]) pos.push(V[k][0], V[k][2], -V[k][1]);   // plan (x, y, z) → three (x, z, −y)
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
  g.computeVertexNormals();
  MODULE_GEO = { mesh: g, edges: new THREE.EdgesGeometry(g, 1) };
  return MODULE_GEO;
}

function build3D() {
  if (!three) init3D();
  const { group, scene, camera, controls } = three;
  group.children.forEach((o) => { if (MODULE_GEO && (o.geometry === MODULE_GEO.mesh || o.geometry === MODULE_GEO.edges)) return; o.geometry?.dispose(); o.material?.dispose(); });
  group.clear();
  scene.background = new THREE.Color(css("--bg"));
  const K = S.kit, mat = (c, o = 1) => new THREE.MeshLambertMaterial({ color: new THREE.Color(c), transparent: o < 1, opacity: o });
  const LY = shown(), after = S.phase === "after";
  const parts = LY.rects.filter((r) => S.showOutside || !["staff_dormitory", "burial_area"].includes(r.name));
  const G = moduleGeometry(), lineMat = new THREE.LineBasicMaterial({ color: new THREE.Color(css("--ink")), transparent: true, opacity: 0.22 });
  for (const r of parts) {
    let mesh;
    if (r.kind === "ward_module" || r.kind === "community_module") {
      // the origami module (step 6), tiled along a merged room such as the hall
      const col = r.kind === "ward_module" ? css(`--${r.ward}`) : css(`--g-${r.zone}`);
      const m = mat(col);
      m.side = THREE.DoubleSide;
      for (let t = 0; t < Math.max(1, Math.round(r.w / D.M.span)); t++) {
        const o = new THREE.Mesh(G.mesh, m);
        o.position.set(r.x + t * D.M.span, 0, -r.y);
        o.scale.set(Math.min(r.w, D.M.span) / D.M.span, 1, r.h / D.M.length);
        group.add(o);
        const e = new THREE.LineSegments(G.edges, lineMat);
        e.position.copy(o.position); e.scale.copy(o.scale); group.add(e);
      }
      continue;
    } else {
      const h = r.kind === "corridor" ? 0.2 : ["staff_dormitory", "burial_area", "loading_zone"].includes(r.name) ? 0.1 : K.SERVICE_H;
      const g = new THREE.BoxGeometry(r.w, h, r.h);
      const zc = r.program ? css(`--g-${r.zone}`) : css(`--${r.zone}`);
      mesh = new THREE.Mesh(g, mat(r.kind === "corridor" ? (after ? css("--g-street") : css("--accent")) : zc, r.kind === "corridor" && !after ? 0.6 : 1));
      mesh.position.set(r.x + r.w / 2, h / 2, -(r.y + r.h / 2));
    }
    group.add(mesh);
    const edges = new THREE.LineSegments(new THREE.EdgesGeometry(mesh.geometry), new THREE.LineBasicMaterial({ color: new THREE.Color(css("--ink")), transparent: true, opacity: 0.25 }));
    edges.position.copy(mesh.position); group.add(edges);
  }
  const loop = (x, y, w, h, color, z = 0.05) => new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(
    [[x, y], [x + w, y], [x + w, y + h], [x, y + h]].map(([a, b]) => new THREE.Vector3(a, z, -b))),
    new THREE.LineBasicMaterial({ color: new THREE.Color(color) }));
  const [fx, fy, fw, fh] = LY.fences.outer;
  group.add(loop(fx, fy, fw, fh, css("--ink")));
  if (LY.fences.red_inner) group.add(loop(...LY.fences.red_inner, css("--red")));
  if (!after) group.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(LY.patient_flow.map(([x, y]) => new THREE.Vector3(x, 0.4, -y))),
    new THREE.LineBasicMaterial({ color: new THREE.Color(css("--accent")) })));
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(fw + 80, fh + 80), mat(css("--land")));
  ground.rotation.x = -Math.PI / 2; ground.position.set(fx + fw / 2, -0.02, -(fy + fh / 2)); group.add(ground);
  const cx = fx + fw / 2, cz = -(fy + fh / 2), R = Math.max(fw, fh);
  controls.target.set(cx, 0, cz);
  if (!three.framed) { camera.position.set(cx - R * 0.7, R * 0.85, cz + R * 1.05); three.framed = true; }
}

// ---------------------------------------------------------------- update
function update({ catchmentOnly = false } = {}) {
  if (!S.site) return;
  siteCard();
  drawCatchment();
  if (catchmentOnly) return;
  S.brief = makeBrief(S.confirmed);
  S.layout = makeLayout(S.brief, S.kit);
  S.checks = checkLayout(S.layout, S.brief, S.kit);
  const cases = S.site.surge ? D.briefBySite[S.site.surge].cases : catchment(S.site).cases;
  const p = people(cases), prog = communityProgramme(p);
  S.comm = { people: p, prog, need: prog.reduce((a, x) => a + x.modules, 0), have: S.brief.modules_total,
    layout: communityLayout(S.brief, prog, S.kit) };
  briefPanel();
  checksPanel();
  $("plan").innerHTML = planSVG();
  if (S.view === "3d") build3D();
  drawFootprint();
}

function setConfirmed(v) {
  S.confirmed = Math.max(1, Math.min(1000, Math.round(Number(v) * 10) / 10 || 1));
  $("confirmed").value = S.confirmed;
  $("confirmed-range").value = Math.min(360, S.confirmed);
}

function emptyCard() {
  $("site-card").innerHTML = `<div class="pick-hint">
    <p><strong>Pick a candidate site on the map.</strong></p>
    <ol>
      <li>Each dot is one of the ${D.C.length} sites that passed all ten MUST filters (out of
        ${fmt(D.meta.funnel[0]?.remaining ?? 68885)} grid cells). Darker blue means a higher SHOULD score.</li>
      <li>Hover a dot to see its score; click it to choose it.</li>
      <li>After your pick, the four sites the optimiser chose appear as rings, so you can compare.</li>
    </ol></div>`;
}

function select(c) {
  S.site = c;
  document.body.classList.add("has-site");
  if (!map.hasLayer(layers.surge)) layers.surge.addTo(map);
  S.rotation = Math.round(((c.rotation_deg + 540) % 360) - 180);
  S.mirrored = c.mirrored;
  syncPlacementInputs();
  setConfirmed(defaultConfirmed(c));
  update();
}

// ---------------------------------------------------------------- copy
async function copy(text, what) {
  const fb = $("copy-fallback");
  try {
    await navigator.clipboard.writeText(text);
    fb.hidden = true;
    $("copied").textContent = `Copied ${what}.`;
  } catch {
    fb.hidden = false; fb.value = text; fb.focus(); fb.select();
    $("copied").textContent = `Your browser blocked the clipboard. The ${what} is selected below: press Ctrl+C (⌘C).`;
  }
}

// ---------------------------------------------------------------- wire up
function wire() {
  $("limit").onchange = (e) => { S.limit = Number(e.target.value); update({ catchmentOnly: true }); };
  const season = (rain) => {
    S.rain = rain;
    $("dry").classList.toggle("on", !rain); $("rain").classList.toggle("on", rain);
    $("dry").setAttribute("aria-pressed", !rain); $("rain").setAttribute("aria-pressed", rain);
    update({ catchmentOnly: true });
  };
  $("dry").onclick = () => season(false); $("rain").onclick = () => season(true);
  $("confirmed").onchange = (e) => { setConfirmed(e.target.value); update(); };
  $("confirmed-range").oninput = (e) => { setConfirmed(e.target.value); update(); };
  $("use-model").onclick = () => { setConfirmed(defaultConfirmed(S.site)); update(); };
  $("rotation").oninput = (e) => { S.rotation = Number(e.target.value); syncPlacementInputs(); drawFootprint(); };
  $("mirrored").onchange = (e) => { S.mirrored = e.target.checked; drawFootprint(); };
  $("auto-place").onclick = () => { S.rotation = Math.round(((S.site.rotation_deg + 540) % 360) - 180); S.mirrored = S.site.mirrored; syncPlacementInputs(); drawFootprint(); };
  $("reset").onclick = () => { S.kit = { ...KIT }; buildSliders(); update(); };
  $("show-outside").onchange = (e) => { S.showOutside = e.target.checked; update(); };
  $("zoom-site").onclick = zoomSite; $("zoom-all").onclick = zoomAll;
  const tab = (v) => {
    S.view = v;
    $("tab-plan").classList.toggle("on", v === "plan"); $("tab-3d").classList.toggle("on", v === "3d");
    $("tab-plan").setAttribute("aria-selected", v === "plan"); $("tab-3d").setAttribute("aria-selected", v === "3d");
    $("plan").hidden = v !== "plan"; $("three").hidden = v !== "3d";
    if (v === "3d") build3D();
  };
  $("tab-plan").onclick = () => tab("plan"); $("tab-3d").onclick = () => tab("3d");
  const phase = (v) => {
    S.phase = v;
    $("phase-ward").classList.toggle("on", v === "ward"); $("phase-after").classList.toggle("on", v === "after");
    $("phase-ward").setAttribute("aria-pressed", v === "ward"); $("phase-after").setAttribute("aria-pressed", v === "after");
    document.body.classList.toggle("after", v === "after");
    if (three) three.framed = false;
    update();
  };
  $("phase-ward").onclick = () => phase("ward"); $("phase-after").onclick = () => phase("after");
  $("copy-csv").onclick = () => copy(briefsGhCsv(S.site.surge ?? `C${S.site.id}`, S.site.near, S.brief,
    { ...S.site, rotation_deg: S.rotation, mirrored: S.mirrored }), "CSV row");
  $("copy-json").onclick = () => copy(JSON.stringify({ site: S.site, inputs: { confirmed: S.confirmed, kit: S.kit, rotation: S.rotation, mirrored: S.mirrored },
    brief: S.brief, layout: S.layout, checks: S.checks, after_the_outbreak: S.comm }, null, 1), "layout JSON");
  $("copy-geo").onclick = () => copy(JSON.stringify({ type: "FeatureCollection", features: footprintFeatures() }), "GeoJSON");
  const retheme = () => { restyleMap(); if (S.view === "3d") build3D(); };
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", retheme);
  new MutationObserver(retheme).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
}

(async function main() {
  try {
    await load();
  } catch (e) {
    $("site-card").innerHTML = `<p class="warn">The site data did not load (${e.message}). Serve this folder over HTTP, for example with <code>python -m http.server</code> in <code>rework/web</code>.</p>`;
    return;
  }
  buildSliders();
  wire();
  initMap();
  emptyCard();
  window.SURGE = { map, data: D, state: S, select };   // handy in the browser console
})();
