// S.U.R.G.E. engine in the browser: the same rules as pipeline/s3_run.py (brief) and pipeline/s4_layout.py (layout).
// Plain functions, no dependencies, so it runs in the page and in Node (tests).

// ---------------------------------------------------------------- step 3: ratios (pipeline/s3_params.py)
export const RATIOS = {
  BEDS_PER_MODULE: 12,
  MIN_MODULES_PER_WARD: 1,
  WARD_SPLIT: { suspect: 0.25, probable: 0.15, confirmed: 0.60 },
  STAFF: {
    clinical_confirmed: [2.0, 0], clinical_suspect_probable: [1.0, 0], hygiene: [1.0, 4], lab: [0.03, 4],
    pharmacy_logistics: [0.3, 4], admin_psychosocial: [0.1, 4], security: [0.0, 6],
  },                                       // [per_bed, fixed]
  SHIFTS: 3,
  DORM_SHARE: 0.3,
  SUPPLY: { water_l_per_bed: 400, water_l_per_staff: 50, power_kw_per_bed: 1.0, power_kw_base: 15,
            waste_kg_per_bed: 8, ppe_per_clinical: 2, chlorine_l_per_bed: 20 },
  SPACES: [  // name, zone, fixed, per_bed, per_ward
    ["triage", "amber", 30, 0.4, 0], ["ward_suspect", "red", 0, 9, 0], ["ward_probable", "red", 0, 9, 0],
    ["ward_confirmed", "red", 0, 9, 0], ["donning", "green", 0, 0, 15], ["doffing_decon", "amber", 0, 0, 20],
    ["patient_discharge", "amber", 12, 0, 0], ["morgue", "red", 0, 0.6, 0], ["lab", "green", 40, 0, 0],
    ["pharmacy", "green", 20, 0.3, 0], ["stores", "green", 30, 0.5, 0], ["laundry", "amber", 20, 0.4, 0],
    ["staff_rest", "green", 0, 0, 0], ["staff_dormitory", "service", 0, 0, 0], ["admin_data", "green", 20, 0.1, 0],
    ["family_visiting", "amber", 30, 0, 0], ["water_treatment", "service", 40, 0, 0], ["generator", "service", 25, 0, 0],
    ["incinerator_waste", "red", 25, 0.1, 0], ["loading_zone", "service", 150, 0, 0], ["burial_area", "service", 0, 0, 0],
  ],
  CIRCULATION: 1.30,
  SITE_COVERAGE: 0.35,
  CASE_FATALITY: 0.6,
};

const r1 = (v) => Math.round(v * 10) / 10;

/** Ward brief for one site from its peak confirmed beds (port of s3_run.brief). */
export function makeBrief(confirmed, Q = RATIOS, split = Q.WARD_SPLIT) {
  const modules = (b) => Math.max(Q.MIN_MODULES_PER_WARD, Math.ceil(b / Q.BEDS_PER_MODULE - 1e-9));
  const total = confirmed / split.confirmed;
  const wards = ["suspect", "probable", "confirmed"].map((name) => {
    const b = name === "confirmed" ? confirmed : total * split[name];
    const m = modules(b);
    return { ward: name, beds_needed: r1(b), modules: m, beds: m * Q.BEDS_PER_MODULE };
  });
  const by = Object.fromEntries(wards.map((w) => [w.ward, w.beds]));
  const all = by.suspect + by.probable + by.confirmed;
  const staff = {};
  for (const [k, [per, fixed]] of Object.entries(Q.STAFF)) {
    const b = k === "clinical_confirmed" ? by.confirmed : k === "clinical_suspect_probable" ? by.suspect + by.probable : all;
    staff[k] = Math.ceil(fixed + per * b - 1e-9);
  }
  const staffTotal = Object.values(staff).reduce((a, b) => a + b, 0);
  const onShift = Math.ceil(staffTotal / Q.SHIFTS);
  const resident = Math.ceil(staffTotal * Q.DORM_SHARE - 1e-9);
  const clinical = staff.clinical_confirmed + staff.clinical_suspect_probable;
  const S = Q.SUPPLY;
  const supplies = {
    water_l_day: Math.round(S.water_l_per_bed * all + S.water_l_per_staff * staffTotal),
    power_kw: Math.round(S.power_kw_per_bed * all + S.power_kw_base),
    medical_waste_kg_day: Math.round(S.waste_kg_per_bed * all),
    ppe_sets_day: Math.round(S.ppe_per_clinical * clinical),
    chlorine_l_day: Math.round(S.chlorine_l_per_bed * all),
  };
  const deaths90 = (confirmed / 10) * 90 * Q.CASE_FATALITY;
  const spaces = Q.SPACES.map(([name, zone, fixed, perBed, perWard]) => {
    let a;
    if (name.startsWith("ward_")) a = perBed * by[name.slice(5)];
    else if (name === "morgue") a = Math.max(2, Math.ceil(by.confirmed / 10)) * 6;
    else if (name === "staff_rest") a = 1.5 * onShift;
    else if (name === "staff_dormitory") a = 6 * resident;
    else if (name === "burial_area") a = 3 * deaths90;
    else a = fixed + perBed * all + perWard * wards.length;
    return { space: name, zone, area_m2: r1(a) };
  });
  const built = spaces.filter((s) => s.zone !== "service" || ["water_treatment", "generator"].includes(s.space))
    .reduce((a, s) => a + s.area_m2, 0);
  const gross = built * Q.CIRCULATION;
  const outdoor = spaces.filter((s) => ["loading_zone", "burial_area", "staff_dormitory"].includes(s.space))
    .reduce((a, s) => a + s.area_m2, 0);
  const plot = gross / Q.SITE_COVERAGE + outdoor;
  return {
    peak_confirmed_beds: r1(confirmed), wards, modules_total: wards.reduce((a, w) => a + w.modules, 0),
    beds_total: all, staff, staff_total: staffTotal, staff_per_shift: onShift, staff_resident: resident,
    supplies, spaces, area: { built_net_m2: Math.round(built), built_gross_m2: Math.round(gross), plot_m2: Math.round(plot) },
  };
}

// ---------------------------------------------------------------- step 4: kit of parts (pipeline/s4_params.py)
export const KIT = {
  BAY: 6, MODULE_W: 6, MODULE_D: 18, MODULE_H: 2.8, MODULE_RIDGE: 4.6, SERVICE_H: 3,
  MAX_MODULES_PER_ROW: 5, ROW_GAP: 3, PATIENT_CORRIDOR: 3, GREEN_COL_BAYS: 2, FENCE_GAP: 1, OUTER_MARGIN: 6,
  MAX_STAFF_WALK_M: 45,
};

const rd = (v) => Math.round(v * 100) / 100;
const rect = (name, zone, x, y, w, h, kind = "space", extra = {}) =>
  ({ name, zone, x: rd(x), y: rd(y), w: rd(w), h: rd(h), kind, ...extra });

/** Ward layout in local metres (port of s4_layout.layout). Road along the bottom, patients walk +y. */
export function makeLayout(brief, G = KIT) {
  const sp = Object.fromEntries(brief.spaces.map((s) => [s.space, s]));
  const bays = (area, depth = G.BAY) => Math.max(1, Math.ceil(area / depth / G.BAY - 1e-9)) * G.BAY;
  const R = [], flow = [], rows = [];
  const greenW = G.GREEN_COL_BAYS * G.BAY;
  const xRed = greenW + G.FENCE_GAP;
  const xMod = xRed + G.BAY;

  const nRow = Math.min(G.MAX_MODULES_PER_ROW, Math.max(...brief.wards.map((w) => w.modules)));
  const triageW = Math.max(bays(sp.triage.area_m2), 2 * G.BAY);
  let y = 0;
  R.push(rect("triage", "amber", xRed, y, triageW, G.BAY));
  R.push(rect("family_visiting", "amber", xRed + triageW, y, bays(sp.family_visiting.area_m2), G.BAY));
  flow.push([xRed + G.BAY, y + G.BAY / 2]);
  y += G.BAY + G.ROW_GAP;

  const xCorr = xMod + nRow * G.MODULE_W;
  flow.push([xCorr + G.PATIENT_CORRIDOR / 2, G.BAY / 2]);
  for (const ward of brief.wards) {
    let k = 0;
    while (k < ward.modules) {
      const m = Math.min(nRow, ward.modules - k);
      const ry = y, n = rows.length + 1;
      R.push(rect(`donning_${ward.ward}_${n}`, "green", xRed, ry, G.BAY, G.BAY, "donning"));
      R.push(rect(`ppe_store_${n}`, "green", xRed, ry + G.BAY, G.BAY, G.BAY, "store"));
      R.push(rect(`doffing_${ward.ward}_${n}`, "amber", xRed, ry + 2 * G.BAY, G.BAY, G.BAY, "doffing"));
      for (let j = 0; j < m; j++)
        R.push(rect(`${ward.ward}_M${k + j + 1}`, "red", xMod + j * G.MODULE_W, ry, G.MODULE_W, G.MODULE_D,
          "ward_module", { ward: ward.ward, beds: 12 }));
      rows.push({ ward: ward.ward, y: ry, modules: m });
      flow.push([xCorr + G.PATIENT_CORRIDOR / 2, ry + G.MODULE_D / 2]);
      k += m;
      y += G.MODULE_D + G.ROW_GAP;
    }
  }
  R.push(rect("patient_corridor", "red", xCorr, G.BAY, G.PATIENT_CORRIDOR, y - G.BAY - G.ROW_GAP, "corridor"));

  const yt = y;
  R.push(rect("patient_discharge", "amber", xRed, yt, G.BAY, G.BAY));
  const wL = bays(sp.laundry.area_m2);
  R.push(rect("laundry", "amber", xRed + G.BAY, yt, wL, G.BAY));
  const wM = bays(sp.morgue.area_m2);
  const mx = Math.max(xCorr + G.PATIENT_CORRIDOR - wM, xRed + G.BAY + wL + G.FENCE_GAP);
  R.push(rect("morgue", "red", mx, yt, wM, G.BAY));
  R.push(rect("incinerator_waste", "red", Math.max(xCorr + G.PATIENT_CORRIDOR, mx + wM) + G.FENCE_GAP, yt,
    bays(sp.incinerator_waste.area_m2), G.BAY));
  flow.push([xCorr + G.PATIENT_CORRIDOR / 2, yt + G.BAY / 2]);
  let top = yt + G.BAY;

  let gy = 0;
  for (const name of ["admin_data", "lab", "pharmacy", "stores", "staff_rest"]) {
    const h = bays(sp[name].area_m2, greenW);
    R.push(rect(name, "green", 0, gy, greenW, h));
    gy += h;
  }
  top = Math.max(top, gy);

  let sx = 0;
  const sy = -G.OUTER_MARGIN - G.BAY;
  for (const name of ["water_treatment", "generator"]) {
    const w = bays(sp[name].area_m2);
    R.push(rect(name, "service", sx, sy, w, G.BAY));
    sx += w + G.BAY;
  }
  R.push(rect("loading_zone", "service", sx, sy - G.BAY, bays(sp.loading_zone.area_m2, 2 * G.BAY), 2 * G.BAY));

  const right = Math.max(...R.map((r) => r.x + r.w));
  R.push(rect("staff_dormitory", "service", right + 2 * G.OUTER_MARGIN, 0, bays(sp.staff_dormitory.area_m2, 2 * G.BAY), 2 * G.BAY));
  const bw = bays(Math.max(sp.burial_area.area_m2, 36), 3 * G.BAY);
  R.push(rect("burial_area", "service", right + 2 * G.OUTER_MARGIN, top - 3 * G.BAY, bw, 3 * G.BAY));

  const clinic = R.filter((r) => r.zone !== "service");
  const x0 = Math.min(...clinic.map((r) => r.x)) - G.OUTER_MARGIN;
  const y0 = Math.min(...clinic.map((r) => r.y)) - G.OUTER_MARGIN;
  const x1 = Math.max(...clinic.map((r) => r.x + r.w)) + G.OUTER_MARGIN;
  const y1 = Math.max(...clinic.map((r) => r.y + r.h)) + G.OUTER_MARGIN;
  const fences = {
    outer: [x0, y0, x1 - x0, y1 - y0],
    red_inner: [xRed - G.FENCE_GAP / 2, G.BAY + G.ROW_GAP / 2, x1 - G.OUTER_MARGIN - xRed + G.FENCE_GAP,
      top - G.BAY - G.ROW_GAP / 2],
  };
  return { rects: R, patient_flow: flow, rows, fences, kit: { ...G } };
}

const touch = (a, b, tol = 0.01) => {
  const ox = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x);
  const oy = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y);
  return (ox > tol && Math.abs(oy) <= tol) || (oy > tol && Math.abs(ox) <= tol) || (ox > tol && oy > tol);
};

/** Rule checks (port of s4_layout.check). */
export function checkLayout(L, brief, G = KIT) {
  const R = L.rects;
  const iface = new Set(["donning", "doffing", "store"]);
  const bad = [], overlaps = [];
  for (let i = 0; i < R.length; i++) for (let j = i + 1; j < R.length; j++) {
    const a = R[i], b = R[j];
    if (new Set([a.zone, b.zone]).size === 2 && [a.zone, b.zone].includes("red") && [a.zone, b.zone].includes("green")
        && touch(a, b) && !iface.has(a.kind) && !iface.has(b.kind)) bad.push([a.name, b.name]);
    if (Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x) > 0.01 && Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y) > 0.01)
      overlaps.push([a.name, b.name]);
  }
  const mods = R.filter((r) => r.kind === "ward_module");
  const beds = mods.reduce((a, r) => a + r.beds, 0);
  const walk = Math.max(...mods.map((r) => r.x + r.w - (L.fences.red_inner[0] + G.BAY)));
  const [, , fw, fh] = L.fences.outer;
  const f = L.patient_flow;
  let path = 0;
  for (let i = 1; i < f.length; i++) path += Math.hypot(f[i][0] - f[i - 1][0], f[i][1] - f[i - 1][1]);
  return {
    beds_in_layout: beds, beds_in_brief: brief.beds_total, beds_match: beds === brief.beds_total,
    red_green_contacts: bad, overlaps, max_staff_walk_m: r1(walk), staff_walk_ok: walk <= G.MAX_STAFF_WALK_M,
    patient_path_m: r1(path), fenced_size_m: [Math.round(fw), Math.round(fh)], fenced_area_m2: Math.round(fw * fh),
    ok: beds === brief.beds_total && !bad.length && !overlaps.length && walk <= G.MAX_STAFF_WALK_M,
  };
}

// ---------------------------------------------------------------- map placement (pipeline/s4_run.py)
export const MX = 111320 * Math.cos((8.615 * Math.PI) / 180), MY = 110570;

/** Local layout metres → lon/lat, centred on the site, rotated and optionally mirrored. */
export function toLonLat(x, y, site, rotationDeg, mirrored, cx, cy) {
  let u = x - cx; const v = y - cy;
  if (mirrored) u = -u;
  const t = (rotationDeg * Math.PI) / 180;
  const X = u * Math.cos(t) - v * Math.sin(t), Y = u * Math.sin(t) + v * Math.cos(t);
  return [site.lon + X / MX, site.lat + Y / MY];
}

/** One row of data/s4/gh/briefs_gh.csv, so a web result can be opened in the Grasshopper definition. */
export function briefsGhCsv(id, near, brief, site) {
  const sp = Object.fromEntries(brief.spaces.map((s) => [s.space, s.area_m2]));
  const names = ["triage", "family_visiting", "laundry", "morgue", "incinerator_waste", "admin_data", "lab", "pharmacy",
    "stores", "staff_rest", "water_treatment", "generator", "loading_zone", "staff_dormitory", "burial_area"];
  const head = ["site_id", "near", "modules_suspect", "modules_probable", "modules_confirmed", "beds_total",
    ...names.map((n) => `area_${n}`), "rotation_deg", "mirrored", "lon", "lat"];
  const w = Object.fromEntries(brief.wards.map((x) => [x.ward, x.modules]));
  const row = [id, near, w.suspect, w.probable, w.confirmed, brief.beds_total, ...names.map((n) => sp[n]),
    site.rotation_deg, site.mirrored ? 1 : 0, site.lon, site.lat];
  return head.join(",") + "\n" + row.join(",") + "\n";
}

// ---------------------------------------------------------------- step 7: after the outbreak (pipeline/s7_*.py)
export const COMMUNITY = {
  CASE_FATALITY: 0.6, CHILDREN_PER_DEATH: 1.5, CASES_PER_HOUSEHOLD: 1.5, HALL_MODULES: 2,
  PROGRAMME: [  // name, group, people basis, people per module
    ["clinic", "care", "survivors", 450], ["counselling", "care", "survivors+households", 450],
    ["workshop", "work", "households", 120], ["hall", "gather", "site", 0], ["kitchen", "gather", "site", 0],
    ["classroom", "learn", "children", 90],
  ],
  GROUP_ORDER: ["care", "work", "gather", "learn"],
  CONVERT: {
    triage: ["reception", "gather"], family_visiting: ["café", "gather"], patient_corridor: ["covered street", "street"],
    patient_discharge: ["toilets", "service"], laundry: ["laundry", "service"], morgue: ["memorial garden", "garden"],
    incinerator_waste: ["memorial garden", "garden"], admin_data: ["admin", "care"], lab: ["clinic lab", "care"],
    pharmacy: ["pharmacy", "care"], stores: ["stores", "service"], staff_rest: ["library", "learn"],
    water_treatment: ["water", "service"], generator: ["solar + generator", "service"], loading_zone: ["market square", "gather"],
    staff_dormitory: ["teachers' housing", "service"], burial_area: ["cemetery and memorial park", "garden"],
  },
  ROW_HEAD: { donning: ["washroom", "service"], store: ["storage", "service"], doffing: ["washroom", "service"] },
};

/** People affected in a catchment from its cumulative cases (port of s7_community.people). */
export function people(cases, C = COMMUNITY) {
  const deaths = cases * C.CASE_FATALITY;
  return { cases, survivors: cases - deaths, deaths, children: deaths * C.CHILDREN_PER_DEATH,
    households: cases / C.CASES_PER_HOUSEHOLD };
}

/** Community programme: modules per space (port of s7_community.programme). */
export function communityProgramme(p, C = COMMUNITY) {
  return C.PROGRAMME.map(([space, group, basis, per]) => {
    if (basis === "site") return { space, group, people: null, modules: space === "hall" ? C.HALL_MODULES : 1 };
    const who = basis.split("+").reduce((a, b) => a + p[b], 0);
    return { space, group, people: Math.round(who), per_module: per, modules: Math.max(1, Math.ceil(who / per - 1e-9)) };
  });
}

/** The step 4 generator with programme groups as wards, then every part converted (port of s7 community_layout). */
export function communityLayout(brief, prog, G = KIT, C = COMMUNITY) {
  const groups = C.GROUP_ORDER.map((g) => ({ ward: g, modules: prog.filter((p) => p.group === g).reduce((a, p) => a + p.modules, 0) }))
    .filter((g) => g.modules);
  const L = makeLayout({ ...brief, wards: groups }, G);
  const queue = Object.fromEntries(C.GROUP_ORDER.map((g) => [g, prog.filter((p) => p.group === g).flatMap((p) => Array(p.modules).fill(p.space))]));
  let R = L.rects.map((r0) => {
    const r = { ...r0 };
    if (r.kind === "ward_module") {
      const g = r.ward;
      Object.assign(r, { program: queue[g].shift(), zone: g, kind: "community_module" });
      r.name = `${r.program}_${r.name.split("_M")[1]}`;
    } else if (C.ROW_HEAD[r.kind]) [r.program, r.zone] = C.ROW_HEAD[r.kind];
    else if (C.CONVERT[r.name]) [r.program, r.zone] = C.CONVERT[r.name];
    return r;
  });
  const halls = R.filter((r) => r.program === "hall");
  if (halls.length === 2 && halls[0].y === halls[1].y) {
    const [a, c] = [...halls].sort((p, q) => p.x - q.x);
    Object.assign(a, { w: rd(a.w + c.w), name: "hall" });
    R = R.filter((r) => r !== c);
  }
  const gard = R.filter((r) => r.program === "memorial garden");
  if (gard.length === 2) {
    const x0 = Math.min(...gard.map((r) => r.x)), x1 = Math.max(...gard.map((r) => r.x + r.w));
    Object.assign(gard[0], { x: x0, w: rd(x1 - x0), name: "memorial_garden" });
    R = R.filter((r) => r !== gard[1]);
  }
  return { ...L, rects: R, fences: { outer: L.fences.outer } };
}
