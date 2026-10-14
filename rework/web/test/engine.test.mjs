// Compare the JS engine with the Python results: node web/test/engine.test.mjs
import { readFileSync } from "fs";
import { makeBrief, makeLayout, checkLayout, KIT } from "../js/engine.js";
const root = new URL("../../data/", import.meta.url);
const briefs = JSON.parse(readFileSync(new URL("s3/briefs.json", root))).sites;
const layouts = JSON.parse(readFileSync(new URL("s4/layouts.json", root))).layouts;
const checks = JSON.parse(readFileSync(new URL("s4/checks.json", root)));
let fail = 0;
const eq = (a, b, what) => { if (JSON.stringify(a) !== JSON.stringify(b)) { fail++; console.log("MISMATCH", what, a, b); } };
for (const pb of briefs) {
  const b = makeBrief(pb.peak_confirmed_beds);
  eq(b.wards.map((w) => w.modules), pb.wards.map((w) => w.modules), pb.site_id + " modules");
  eq(b.staff_total, pb.staff_total, pb.site_id + " staff");
  for (const s of pb.spaces) {
    const j = b.spaces.find((x) => x.space === s.space);
    if (Math.abs(j.area_m2 - s.area_m2) > (s.space === "burial_area" ? 1 : 0.11)) eq(j.area_m2, s.area_m2, pb.site_id + " " + s.space);
  }
  // layout from the Python brief (exact areas) must equal the Python layout
  const L = makeLayout(pb, KIT), PL = layouts.find((l) => l.site_id === pb.site_id);
  eq(L.rects.length, PL.rects.length, pb.site_id + " n rects");
  for (const r of PL.rects) {
    const j = L.rects.find((x) => x.name === r.name);
    if (!j) { fail++; console.log("missing", r.name); continue; }
    eq([j.x, j.y, j.w, j.h], [r.x, r.y, r.w, r.h], pb.site_id + " " + r.name);
  }
  eq(L.fences.outer, PL.fences.outer, pb.site_id + " fence");
  const c = checkLayout(L, pb), pc = checks[pb.site_id];
  eq([c.ok, c.max_staff_walk_m, c.patient_path_m, c.fenced_size_m], [pc.ok, pc.max_staff_walk_m, pc.patient_path_m, pc.fenced_size_m], pb.site_id + " checks");
  // layout from the JS brief
  const L2 = makeLayout(b); const c2 = checkLayout(L2, b);
  console.log(pb.site_id, "JS brief → layout ok:", c2.ok, "fence", c2.fenced_size_m.join("×"), "beds", c2.beds_in_layout);
}
// rows of 3 still pass (the bug the checker once caught)
for (const n of [2, 3, 4, 8]) { const b = makeBrief(120); const L = makeLayout(b, { ...KIT, MAX_MODULES_PER_ROW: n }); const c = checkLayout(L, b, { ...KIT, MAX_MODULES_PER_ROW: n }); console.log("per_row", n, "overlaps", c.overlaps.length, "walk", c.max_staff_walk_m, "ok", c.ok); }
console.log(fail ? `${fail} mismatches` : "all equal to the Python pipeline");
process.exit(fail ? 1 : 0);
