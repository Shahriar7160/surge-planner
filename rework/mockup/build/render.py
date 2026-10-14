"""Render the presentation mockup (A3 landscape HTML -> PDF via Chromium).

Reads out.json from compute.py. Every item the author still has to do is
registered with todo() and compiled onto the last page.
"""
import json
import math
from html import escape

D = json.load(open("out.json"))
X0, Y0, X1, Y1 = D["bbox"]
KX, KY = D["kx"], D["ky"]
ASPECT = ((Y1 - Y0) * KY) / ((X1 - X0) * KX)

# ---------- palette (validated reference instance; yellow reserved for TODO marks)
INK, INK2, INK3, RULE, PAPER = "#141413", "#55534e", "#8a887f", "#d9d6cc", "#f7f6f2"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
CAT = [BLUE, ORANGE, AQUA]
RED_RAMP = ["#fbe3e0", "#f6b9b2", "#ee8b81", "#e34948", "#b8302f", "#7d1d1c"]
TODO_Y = "#ffd84d"

TODOS = []


def todo(text, pri="M", short=None):
    """Register a task for the author. Returns the inline marker."""
    n = len(TODOS) + 1
    TODOS.append({"id": f"T{n:02d}", "text": short or text, "pri": pri, "page": CUR[0]})
    return f'<span class="todo"><b>YOU&nbsp;·&nbsp;T{n:02d}</b> {text}</span>'


def ph(label, h=None, cls=""):
    st = f' style="height:{h}"' if h else ""
    return f'<div class="ph {cls}"{st}><span>{label}</span></div>'


CUR = [0]


# ---------- map helpers
def proj(w):
    h = w * ASPECT

    def f(x, y):
        return ((x - X0) / (X1 - X0) * w, (Y1 - y) / (Y1 - Y0) * h)
    return f, h


def poly_d(pts, f, close=False):
    if len(pts) < 2:
        return ""
    s = "M" + "L".join(f"{a:.1f},{b:.1f}" for a, b in (f(*p) for p in pts))
    return s + ("Z" if close else "")


MAJOR = {"trunk", "primary", "secondary", "tertiary"}
MINOR = {"unclassified", "road", "residential", "service", "track"}


def base_map(w, roads="all", water=True, forest=True, extra="", dark=False):
    f, h = proj(w)
    out = [f'<svg class="map" viewBox="0 0 {w} {h:.0f}" width="100%" xmlns="http://www.w3.org/2000/svg">',
           f'<defs><clipPath id="c{w}"><rect width="{w}" height="{h:.0f}"/></clipPath></defs>',
           f'<g clip-path="url(#c{w})">']
    if forest:
        d = "".join(poly_d(p, f, True) for p in D["forest"])
        out.append(f'<path d="{d}" fill="{"#1f2a1f" if dark else "#e6eadf"}" stroke="none"/>')
    if water:
        d = "".join(poly_d(p, f) for t, p in D["water"] if t == "river")
        out.append(f'<path d="{d}" fill="none" stroke="{"#2b4a66" if dark else "#a9c6e4"}" stroke-width="0.9"/>')
    if roads:
        if roads == "all":
            d = "".join(poly_d(p, f) for t, p in D["roads"] if t in MINOR)
            out.append(f'<path d="{d}" fill="none" stroke="{"#3a3a37" if dark else "#cfccc2"}" stroke-width="0.45"/>')
        d = "".join(poly_d(p, f) for t, p in D["roads"] if t in MAJOR)
        out.append(f'<path d="{d}" fill="none" stroke="{"#77756e" if dark else "#8f8c84"}" stroke-width="1.1"/>')
    out.append(extra if isinstance(extra, str) else extra(f))
    out.append("</g></svg>")
    return "".join(out)


def dots(f, pts, r, fill, stroke=None, op=1):
    s = f' stroke="{stroke}" stroke-width="0.8"' if stroke else ""
    return "".join(f'<circle cx="{f(x, y)[0]:.1f}" cy="{f(x, y)[1]:.1f}" r="{r}" fill="{fill}"{s} opacity="{op}"/>'
                   for x, y in pts)


def label(f, x, y, text, dx=6, dy=-6, size=11, color=INK, weight=600, halo=PAPER):
    px, py = f(x, y)
    return (f'<text x="{px + dx:.1f}" y="{py + dy:.1f}" font-size="{size}" font-weight="{weight}" '
            f'fill="{color}" stroke="{halo}" stroke-width="3" paint-order="stroke" '
            f'font-family="Inter">{escape(text)}</text>')


PL = D["places"]
PA = D["patches"]
CITIES = [p for p in PL if p["t"] == "city"]


def scalebar(w, km=20):
    px = km / ((X1 - X0) * KX) * w
    return (f'<div class="scale"><span style="width:{px:.0f}px"></span>{km} km</div>')


# ---------- page shell
PAGES = []


def page(num, kicker, title, body, cls=""):
    CUR[0] = num
    PAGES.append((num, kicker, title, body() if callable(body) else body, cls))


def shell(num, kicker, title, body, cls):
    return f"""
<section class="page {cls}">
  <header><span class="k">{kicker}</span><span class="pn">S.U.R.G.E. — rework mockup · {num:02d}</span></header>
  <h1>{title}</h1>
  {body}
</section>"""


# ================= PAGE 1 — cover
def p_cover():
    def extra(f):
        s = dots(f, [(p["x"], p["y"]) for p in PL if p["t"] in ("hamlet", "isolated_dwellin")], 1.1, INK3, op=.55)
        s += dots(f, [(p["x"], p["y"]) for p in PL if p["t"] in ("village", "town", "suburb", "neighbourhood")], 2, INK2)
        for st in D["sites"]:
            p = PA[st["patch"]]
            s += dots(f, [(p["x"], p["y"])], 6 + 3 * st["modules"], "none", RED_RAMP[3])
            s += dots(f, [(p["x"], p["y"])], 3.2, RED_RAMP[3])
        for c in CITIES:
            s += label(f, c["x"], c["y"], c["n"], size=13)
        s += label(f, -10.25, 8.12, "Liberia / Sierra Leone · outside the 2014 Guinea extract", dx=0, dy=0, size=11, color=INK3, weight=400)
        return s
    m = base_map(1060, extra=extra)
    return f"""
<div class="cover">
  <div class="cv-l">
    <div class="eyebrow">Computational design · Disaster response · Open data</div>
    <div class="big">S.U.R.G.E.</div>
    <div class="sub">Spatial Unit Response Generator for Epidemics</div>
    <p class="lede">A disaster produces a flood of data; S.U.R.G.E. turns that data into treatment sites,
    ward sizes and ready-to-assemble wards, automatically.</p>
    <p class="note">Rebuilt in 2026 from the author's 2015 studio project, the Parametric Response System (P.R.S.).</p>
    <dl class="meta">
      <dt>Study area</dt><dd>Guéckédou · Macenta · Kissidougou, Forest Guinea, where the 2014 West Africa outbreak began</dd>
      <dt>Inputs</dt><dd>OpenStreetMap 2014: {D['n_places']:,} settlements, {len(D['roads']):,} road segments, waterways, land use, forest</dd>
      <dt>Outputs</dt><dd>Outbreak forecast → catchments → treatment sites → ward plans → after-use</dd>
    </dl>
    <div class="byline">Shahriar Bigdeli · Python + Grasshopper · origin: Design 5A ARCT5500, UWA Summer Studio 2015</div>
  </div>
  <div class="cv-r">{m}
    <div class="cap">Prototype output on real 2014 OSM data: red rings are the {D['k_sites']} computed treatment sites, sized by number of 12-bed modules.</div>
  </div>
</div>"""


# ================= PAGE 2 — origin
def p_origin():
    return f"""
<div class="g3">
  <figure><img src="img/g7_prs-04.jpg" style="height:520px;object-fit:cover;object-position:top"/>
    <figcaption>2015 · The P.R.S. diagram: data + module spec → analysis → location + pattern, then deploy, then convert.</figcaption></figure>
  <figure><img src="img/folio9-9.jpg"/>
    <figcaption>2015 · The 10-step Grasshopper “data processing mechanism” (MeerkatGIS + Voronoi + grid).</figcaption>
    <img src="img/g7_etu-11.jpg" style="margin-top:14px"/>
    <figcaption>2015 · Ebola treatment unit layout and zoning.</figcaption></figure>
  <div class="col">
    <h3>What held up</h3>
    <ul>
      <li>Framing the response as a <b>pipeline</b>: data goes in, a spatial plan comes out.</li>
      <li>Three phases: <b>immediate</b> (analyse), <b>short term</b> (deploy), <b>long term</b> (convert to community space).</li>
      <li>Grounded in real field references: MSF three-ward ETUs, the Monrovia Medical Unit, CDC Firestone.</li>
    </ul>
    <h3>What was thin</h3>
    <ul>
      <li>Epidemiology was two constants (R₀ = 2, 0.3%). Nothing changed over time.</li>
      <li>Isolation zones were <b>straight-line Voronoi</b> cells. They ignored roads.</li>
      <li>Deployment was a <b>regular grid</b> with manual relocation. Nothing was optimised.</li>
      <li>Ward plans weren't driven by predicted case load.</li>
    </ul>
    <h3>The rework</h3>
    <p>Keep the idea and the narrative. Replace each step with a model that can be tested.</p>
    {todo("Re-export the 2015 boards at full resolution (the .ai files in /New folder) for this spread.", "M",
          "Hi-res exports of 2015 boards")}
  </div>
</div>"""


# ================= PAGE 3 — system
def p_system():
    stages = [
        ("01", "Data", "OSM 2014 layers + case reports + population", "geodata"),
        ("02", "Outbreak", "Spatial SEIR over settlements linked by road travel", "weekly risk"),
        ("03", "Access", "Road-network travel time; catchments", "time surface"),
        ("04", "Siting", "Coverage optimisation with capacity", "sites + modules"),
        ("05", "Units", "Parametric ward generator from MSF rules", "plans"),
        ("06", "After-use", "Rules to convert units as demand falls", "community space"),
    ]
    phases = [("Immediate response", 0, 4, BLUE), ("Short term", 4, 5, ORANGE), ("Long term", 5, 6, AQUA)]
    W, bx, gap = 1530, 216, 34
    svg = [f'<svg viewBox="0 0 {W} 310" width="100%">',
           '<defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">'
           f'<path d="M0,0L10,5L0,10z" fill="{INK}"/></marker></defs>']
    for i, (n, t, d, o) in enumerate(stages):
        x = 20 + i * (bx + gap)
        svg.append(f'<rect x="{x}" y="70" width="{bx}" height="170" rx="4" fill="#fff" stroke="{INK}" stroke-width="1.2"/>')
        svg.append(f'<text x="{x + 16}" y="104" font-family="DejaVu Sans Mono" font-size="15" fill="{INK3}">{n}</text>')
        svg.append(f'<text x="{x + 16}" y="138" font-family="Inter" font-size="26" font-weight="700" fill="{INK}">{t}</text>')
        words, line, ly = d.split(), "", 168
        for wd in words:
            if len(line + wd) > 24:
                svg.append(f'<text x="{x + 16}" y="{ly}" font-family="Inter" font-size="14" fill="{INK2}">{line}</text>')
                line, ly = "", ly + 19
            line += wd + " "
        svg.append(f'<text x="{x + 16}" y="{ly}" font-family="Inter" font-size="14" fill="{INK2}">{line}</text>')
        svg.append(f'<text x="{x + 16}" y="228" font-family="DejaVu Sans Mono" font-size="13" fill="{INK}">→ {o}</text>')
        if i < len(stages) - 1:
            svg.append(f'<line x1="{x + bx + 2}" y1="155" x2="{x + bx + gap - 4}" y2="155" stroke="{INK}" stroke-width="1.5" marker-end="url(#ar)"/>')
    for name, a, b, c in phases:
        x0, x1 = 20 + a * (bx + gap), 20 + b * (bx + gap) - gap
        svg.append(f'<rect x="{x0}" y="262" width="{x1 - x0}" height="8" fill="{c}"/>')
        svg.append(f'<text x="{x0}" y="294" font-family="Inter" font-size="15" font-weight="600" fill="{INK}">{name}</text>')
    # feedback loop
    svg.append(f'<path d="M{20 + 4 * (bx + gap) + bx / 2},70 C{20 + 4 * (bx + gap) + bx / 2},20 {20 + 1 * (bx + gap) + bx / 2},20 {20 + 1 * (bx + gap) + bx / 2},66" '
               f'fill="none" stroke="{INK2}" stroke-dasharray="5 5" stroke-width="1.3" marker-end="url(#ar)"/>')
    svg.append(f'<text x="{20 + 2.5 * (bx + gap)}" y="30" text-anchor="middle" font-family="Inter" font-size="14" fill="{INK2}">'
               'feedback: isolation capacity lowers transmission in reached settlements</text>')
    svg.append("</svg>")
    return f"""
<p class="intro">Each 2015 step becomes a model with explicit inputs, assumptions and outputs.
The phases are the same as the 2015 P.R.S. diagram.</p>
{''.join(svg)}
<div class="g3 tight">
  <div class="col"><h3>2015 → 2026 mapping</h3>
  <table class="t">
    <tr><th>2015 step</th><th>Rework</th></tr>
    <tr><td>Contagious factor = 2</td><td>Spatial SEIR model, run weekly</td></tr>
    <tr><td>3 · Voronoi isolation zones</td><td>Road travel-time catchments</td></tr>
    <tr><td>4–5 · Grid of 500 km² cells</td><td>Coverage optimisation</td></tr>
    <tr><td>7–9 · Density + manual relocation</td><td>Demand-weighted siting with constraints</td></tr>
    <tr><td>10 · Modules per area</td><td>Beds from forecast → 12-bed modules</td></tr>
  </table></div>
  <div class="col"><h3>Stack</h3>
  <p class="mono">Python · numpy · road graph + Dijkstra · SEIR (metapopulation) · greedy max-coverage → MILP · Rhino/Grasshopper for the unit · web map for the interface</p>
  <p class="locked"><b>Locked:</b> Python for data → location → ward sizing; Grasshopper (linked with Hops) for the automatic ward design.</p>
  </div>
  <div class="col"><h3>Reproducibility</h3>
  <p>One command rebuilds every figure from the raw shapefiles in <span class="mono">References/Data</span>.
  Each page notes which parameters drive it.</p>
  {todo("Put the pipeline in a public repo with a README, pinned environment and licence (OSM data is ODbL).", "M",
        "Public repo + README + ODbL attribution")}
  </div>
</div>"""


# ================= PAGE 4 — data
def p_data():
    w = 440

    def m(kind):
        if kind == "places":
            return base_map(w, roads=None, water=False, forest=False,
                            extra=lambda f: dots(f, [(p["x"], p["y"]) for p in PL], 1.2, INK))
        if kind == "roads":
            return base_map(w, roads="all", water=False, forest=False)
        if kind == "water":
            def ex(f):
                d = "".join(poly_d(p, f) for t, p in D["water"])
                return f'<path d="{d}" fill="none" stroke="{BLUE}" stroke-width="0.7"/>'
            return base_map(w, roads=None, water=False, forest=False, extra=ex)
        if kind == "forest":
            def ex(f):
                d = "".join(poly_d(p, f, True) for p in D["forest"])
                return f'<path d="{d}" fill="{AQUA}" opacity=".55"/>'
            return base_map(w, roads=None, water=False, forest=False, extra=ex)
        if kind == "resid":
            def ex(f):
                d = "".join(poly_d(p, f, True) for p in D["resid"])
                return f'<path d="{d}" fill="{ORANGE}" stroke="{ORANGE}" stroke-width="0.8"/>'
            return base_map(w, roads=None, water=False, forest=False, extra=ex)
        if kind == "cell":
            return base_map(w, roads=None, water=False, forest=False,
                            extra=lambda f: dots(f, [tuple(c) for c in D["cell"]], 4, INK))
    tiles = [("places", "Settlements", f"{D['n_places']:,} points · city→hamlet"),
             ("roads", "Roads", f"{len(D['roads']):,} segments · 12 classes"),
             ("water", "Waterways", "rivers, streams · crossings matter"),
             ("forest", "Forest / natural", "exclusion layer for siting"),
             ("resid", "Residential land use", "isolation buffer source"),
             ("cell", "Cell towers", f"{len(D['cell'])} sites · reporting reach")]
    cells = "".join(f'<div class="tile">{m(k)}<div class="tl"><b>{t}</b><span>{s}</span></div></div>' for k, t, s in tiles)
    return f"""
<p class="intro">The six OSM layers below (Sept–Dec 2014) came with the 2015 project, clipped to the same window as the
2015 MeerkatGIS crop. Step 1 added population, terrain, land cover, boundaries and case data (right; full atlas in
<span class="mono">rework/data/atlas_step1.png</span>).</p>
<div class="datagrid">
  <div class="tiles">{cells}</div>
  <div class="col">
    <h3>Gaps to close</h3>
    <p class="locked"><b>Step 1 done:</b> HRSL population (90 m), Copernicus DEM + slope, ESA WorldCover land cover,
    geoBoundaries admin units, Guinea MoH sitreps by prefecture (Aug–Oct 2014) and WHO weekly cases.
    See <span class="mono">rework/data/SOURCES.md</span>.</p>
    <p class="locked"><b>Added:</b> 172 MoH health facilities in the window and CHIRPS 2014 monthly rainfall (2,294 mm/yr, peak July).</p>
    <p class="locked"><b>Facility data repaired:</b> 207 facilities in the window. 172 are from the MoH list, 13 matched by village name, the Guéckédou hospital is placed at its town centre and 21 are scenario placements. See <span class="mono">data/facility_repair.png</span>.</p>

    <p class="note">Cell coverage only has {len(D['cell'])} tower points inside the window. Treat it as a proxy for where reporting is possible, not as true coverage.</p>
  </div>
</div>"""


# ================= PAGE 5 — outbreak
def ramp(v, vmax):
    if v <= 0.05:
        return None
    t = min(1, math.log10(1 + v) / math.log10(1 + vmax))
    return RED_RAMP[min(len(RED_RAMP) - 1, int(t * len(RED_RAMP)))]


def p_outbreak():
    prev = D["prev"]
    weeks = [10, 20, 30, 40]
    vmax = max(max(r) for r in prev)
    w = 330

    def mk(wk):
        def ex(f):
            s = ""
            row = prev[wk - 1]
            order = sorted(range(len(PA)), key=lambda k: row[k])
            for k in order:
                c = ramp(row[k], vmax)
                if c:
                    rr = 2 + 7 * math.sqrt(PA[k]["P"] / 60000)
                    s += dots(f, [(PA[k]["x"], PA[k]["y"])], f"{rr:.1f}", c, PAPER)
            return s
        return base_map(w, roads="major", water=False, forest=False, extra=ex)
    sm = "".join(f'<div class="tile">{mk(wk)}<div class="tl"><b>Week {wk}</b><span>{sum(prev[wk - 1]):,.0f} infectious</span></div></div>' for wk in weeks)
    # chart: beds, log y, two series
    b, br = D["beds"], D["beds_r"]
    CW, CH, pl, pb = 620, 300, 56, 34
    n = len(b)
    xs = lambda i: pl + i / (n - 1) * (CW - pl - 10)
    ys = lambda v: CH - pb - (math.log10(max(v, 1)) / 5) * (CH - pb - 10)
    g = [f'<svg viewBox="0 0 {CW} {CH}" width="100%">']
    for e in range(0, 6):
        y = ys(10 ** e)
        g.append(f'<line x1="{pl}" x2="{CW - 10}" y1="{y:.1f}" y2="{y:.1f}" stroke="{RULE}" stroke-width="1"/>')
        g.append(f'<text x="{pl - 8}" y="{y + 4:.1f}" text-anchor="end" font-size="11" fill="{INK2}" font-family="Inter">{10 ** e:,}</text>')
    for wk in range(0, n, 10):
        g.append(f'<text x="{xs(wk):.1f}" y="{CH - 12}" text-anchor="middle" font-size="11" fill="{INK2}" font-family="Inter">wk {wk}</text>')
    g.append(f'<line x1="{xs(9):.1f}" x2="{xs(9):.1f}" y1="10" y2="{CH - pb}" stroke="{INK3}" stroke-dasharray="3 4"/>')
    g.append(f'<text x="{xs(9) + 5:.1f}" y="22" font-size="11" fill="{INK2}" font-family="Inter">response starts (wk 10)</text>')
    for ser, c, lab in ((b, RED_RAMP[3], "no response"), (br, BLUE, f"with {D['k_sites']} sites")):
        d = "M" + "L".join(f"{xs(i):.1f},{ys(v):.1f}" for i, v in enumerate(ser))
        g.append(f'<path d="{d}" fill="none" stroke="{c}" stroke-width="2"/>')
        i = len(ser) - 1 if lab == "no response" else max(range(len(ser)), key=lambda k: ser[k])
        g.append(f'<text x="{xs(i) - 4:.1f}" y="{ys(ser[i]) - 8:.1f}" text-anchor="end" font-size="12" font-weight="600" fill="{INK}" font-family="Inter">{lab} · peak {max(ser):,.0f}</text>')
    g.append("</svg>")
    return f"""
<div class="g2">
  <div>
    <p class="intro">Metapopulation SEIR over {len(PA)} settlement clusters. Clusters are coupled by a gravity model on
    <b>road travel time</b>, so the virus moves the way people do. Seeded at {escape(D['seed'])}, near Meliandou, where the index case was.</p>
    <div class="tiles four">{sm}</div>
    <div class="legend"><span>infectious per cluster (log)</span>{''.join(f'<i style="background:{c}"></i>' for c in RED_RAMP)}<span>circle size = population proxy</span></div>
    <div class="formula mono">dS = −β·S·(M·I/N) · dE = β·S·(M·I/N) − σE · dI = σE − γI<br>
    R₀ = 1.7 (lit. 1.5–2.0) · 1/σ = 9.4 d · 1/γ = 7.4 d · M = 0.92·I + 0.08·gravity(P, e<sup>−t/2h</sup>)</div>
  </div>
  <div>
    <h3>Bed demand, region total</h3>
    {''.join(g)}
    <p class="note">Assumes 60% of infectious people seek a bed. Isolation within reach of a site cuts transmission by 60%.
    <b>Uncalibrated</b>: this shows the mechanism, not a forecast. The real outbreak was far smaller and much more stochastic.</p>
<p class="locked"><b>Done (step 2):</b> calibrated to the MoH prefecture sitreps: R₀ 1.56, fit error 0.096 (log RMSE). See <span class="mono">data/s2/fig_1_calibration.png</span>.</p>
    {todo("Make the model stochastic (e.g. τ-leaping, 200 runs) and show uncertainty bands instead of one line.", "M",
          "Stochastic runs + uncertainty bands")}
    {todo("Add funeral transmission and health-care-worker infection as separate compartments. Both drove the 2014 outbreak.", "L",
          "Funeral + HCW compartments")}
  </div>
</div>"""


# ================= PAGE 6 — access
def p_access():
    w = 700

    def mk(key, show_moved):
        def ex(f):
            s = ""
            for p in PL:
                k = p[key]
                if k < 0:
                    continue
                s += dots(f, [(p["x"], p["y"])], 1.8, CAT[k], op=.85)
            if show_moved:
                mv = [(p["x"], p["y"]) for p in PL if p["nw"] >= 0 and p["nw"] != p["eu"]]
                s += dots(f, mv, 3.4, "none", INK)
            # Euclidean voronoi boundaries via raster sampling (2015 method)
            if key == "eu":
                cs = [(c["x"], c["y"]) for c in CITIES]
                step = 0.005
                near = lambda x, y: min(range(3), key=lambda i: (cs[i][0] - x) ** 2 * KX * KX + (cs[i][1] - y) ** 2 * KY * KY)
                pts = []
                nx, ny = int((X1 - X0) / step), int((Y1 - Y0) / step)
                grid = [[near(X0 + i * step, Y0 + j * step) for i in range(nx)] for j in range(ny)]
                for j in range(ny - 1):
                    for i in range(nx - 1):
                        if grid[j][i] != grid[j][i + 1] or grid[j][i] != grid[j + 1][i]:
                            pts.append((X0 + i * step, Y0 + j * step))
                s += dots(f, pts, 1.1, INK)
            for i, c in enumerate(CITIES):
                s += dots(f, [(c["x"], c["y"])], 7, CAT[i], PAPER)
                s += label(f, c["x"], c["y"], c["n"], dx=10, dy=4, size=14)
            return s
        return base_map(w, roads="major", water=True, forest=False, extra=ex)
    pct = 100 * D["moved"] / D["n_places"]
    return f"""
<div class="g2">
  <figure>{mk("eu", False)}<figcaption><b>2015 · straight-line Voronoi.</b> Each settlement goes to the nearest city as the crow flies.</figcaption></figure>
  <figure>{mk("nw", True)}<figcaption><b>Rework · road travel time.</b> Each settlement goes to the city it can reach fastest by road.
  Black rings mark settlements that switch catchment.</figcaption></figure>
</div>
<div class="g3 tight">
  <div class="stat"><div class="n">{D['moved']}</div><div class="l">of {D['n_places']:,} settlements ({pct:.0f}%) change catchment once roads are considered</div></div>
  <div class="col"><h3>How it works</h3><p>{len(D['roads']):,} OSM segments become a graph of 188k nodes. Speeds are set per road class
  (trunk 50 km/h → footpath 4 km/h). Multi-source Dijkstra from each city gives travel time and catchment for every settlement in one pass.
  Settlements off the network walk to the nearest node at 4 km/h.</p></div>
  <div class="col">
  {todo("Check the road-speed table with someone who knows Forest Guinea. Add a rainy-season scenario where tracks and paths drop to about 50% speed.", "M",
        "Validate road speeds + rainy-season scenario")}
  {todo("Treat rivers without a bridge as barriers: intersect the waterways layer with roads and add ferry penalties.", "L",
        "River crossings / ferry penalties")}
  </div>
</div>
<div class="legend">{''.join(f'<i style="background:{CAT[i]}"></i><span>{escape(c["n"])}</span>' for i, c in enumerate(CITIES))}</div>"""


# ================= PAGE 7 — siting
def p_siting():
    w = 700

    def grid_map(f):
        s = dots(f, [(p["x"], p["y"]) for p in PA], 2.2, INK3)
        for x, y in D["grid_pts"]:
            px, py = f(x, y)
            s += f'<rect x="{px - 4:.1f}" y="{py - 4:.1f}" width="8" height="8" fill="{INK}"/>'
        return s

    def opt_map(f):
        s = ""
        for st in D["sites"]:
            sp = PA[st["patch"]]
            for k in st["reach"]:
                a, b = f(PA[k]["x"], PA[k]["y"])
                c, d = f(sp["x"], sp["y"])
                s += f'<line x1="{a:.1f}" y1="{b:.1f}" x2="{c:.1f}" y2="{d:.1f}" stroke="{BLUE}" stroke-width=".8" opacity=".55"/>'
        s += dots(f, [(p["x"], p["y"]) for p in PA], 2.2, INK3)
        for st in D["sites"]:
            sp = PA[st["patch"]]
            s += dots(f, [(sp["x"], sp["y"])], 5 + 2.5 * st["modules"], BLUE, PAPER)
            s += label(f, sp["x"], sp["y"], f'{sp["n"]} · {st["modules"]}×', dx=12, dy=4, size=12)
        return s
    return f"""
<div class="g2">
  <figure>{base_map(w, roads="major", water=False, forest=True, extra=grid_map)}
  <figcaption><b>2015 · one unit per 500 km² cell.</b> {D['n_grid']} units on a regular grid, no matter where people live.</figcaption></figure>
  <figure>{base_map(w, roads="major", water=False, forest=True, extra=opt_map)}
  <figcaption><b>Rework · demand-weighted coverage.</b> Greedy maximum coverage: each site serves clusters within {D['cover_h']} h by road.
  Labels give the number of 12-bed modules, sized from that catchment's forecast peak.</figcaption></figure>
</div>
<div class="g4">
  <div class="stat"><div class="n">{D['k_sites']}</div><div class="l">sites cover {100 * D['opt_cov']:.0f}% of peak demand within {D['cover_h']} h</div></div>
  <div class="stat"><div class="n mut">{D['n_grid']}</div><div class="l">grid units to reach {100 * D['grid_cov']:.0f}%, the 2015 method</div></div>
  <div class="stat"><div class="n">{D['t_opt_mean']:.1f} h</div><div class="l">mean demand-weighted travel time ({D['t_grid_mean']:.1f} h for the grid, but with 7× the units)</div></div>
  <div class="col">
<p class="locked"><b>Done:</b> capacitated maximal-covering MILP (HiGHS). 4 sites cover 97% of peak bed demand within 1.5 h; the 2015 grid needed 33 units.</p>
<p class="locked"><b>Done:</b> 8 MUST filters (68,885 → 936 candidates) and 9 weighted SHOULD scores, all in <span class="mono">s2_params.py</span>.</p>
<p class="locked"><b>Done:</b> sweep over 2–10 sites × 0.75–3 h, plus a facility-repair sensitivity. See <span class="mono">data/s2/fig_4_tradeoffs_feedback.png</span>.</p>
  </div>
</div>"""


# ================= PAGE 8 — unit generator
def etu_plan(mods, w=440):
    """Parametric ETU: green (staff) zone → doffing → red zone wards sized by modules."""
    bay = 46            # one 12-bed confirmed module
    wards_w = max(1, mods) * bay
    W = 40 + 120 + 30 + 80 + 80 + wards_w + 70 + 40
    H = 320
    sc = w / W
    s = [f'<svg viewBox="0 0 {W} {H}" width="100%" font-family="Inter">',
         '<defs><marker id="fa" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto">'
         f'<path d="M0,0L10,5L0,10z" fill="{INK}"/></marker></defs>',
         f'<rect x="10" y="20" width="{W - 20}" height="{H - 50}" fill="none" stroke="{INK3}" stroke-dasharray="6 4"/>',
         f'<text x="14" y="14" font-size="10" fill="{INK2}">double fence, 1 m apart</text>']
    x = 40
    # green zone
    s.append(f'<rect x="{x}" y="40" width="120" height="220" fill="#dff1e8" stroke="{INK}" stroke-width="1"/>')
    for i, t in enumerate(["staff entry", "lab", "pharmacy", "stores", "donning"]):
        s.append(f'<text x="{x + 8}" y="{64 + i * 40}" font-size="11" fill="{INK}">{t}</text>')
    s.append(f'<text x="{x + 8}" y="254" font-size="10" font-weight="700" fill="{AQUA}">LOW RISK</text>')
    x += 150
    # triage
    s.append(f'<rect x="{x}" y="180" width="80" height="80" fill="#fff" stroke="{INK}"/>')
    s.append(f'<text x="{x + 8}" y="200" font-size="11">triage</text>')
    s.append(f'<line x1="{x + 40}" y1="{H - 2}" x2="{x + 40}" y2="262" stroke="{INK}" stroke-width="1.4" marker-end="url(#fa)"/>')
    s.append(f'<text x="{x - 34}" y="{H - 6}" font-size="10" fill="{INK2}">patient entry</text>')
    # suspect / probable
    s.append(f'<rect x="{x}" y="40" width="80" height="60" fill="{RED_RAMP[0]}" stroke="{INK}"/>')
    s.append(f'<text x="{x + 6}" y="58" font-size="11">suspect</text>')
    s.append(f'<rect x="{x}" y="105" width="80" height="60" fill="{RED_RAMP[1]}" stroke="{INK}"/>')
    s.append(f'<text x="{x + 6}" y="123" font-size="11">probable</text>')
    x += 80
    s.append(f'<rect x="{x}" y="40" width="80" height="220" fill="#fff" stroke="{INK}"/>')
    s.append(f'<text x="{x + 6}" y="58" font-size="11">corridor</text>')
    s.append(f'<text x="{x + 6}" y="72" font-size="9" fill="{INK2}">one-way</text>')
    x += 80
    for i in range(max(1, mods)):
        s.append(f'<rect x="{x + i * bay}" y="40" width="{bay - 4}" height="220" fill="{RED_RAMP[2]}" stroke="{INK}"/>')
        for b in range(6):
            s.append(f'<rect x="{x + i * bay + 5}" y="{50 + b * 34}" width="13" height="24" fill="#fff" opacity=".8"/>')
            s.append(f'<rect x="{x + i * bay + 24}" y="{50 + b * 34}" width="13" height="24" fill="#fff" opacity=".8"/>')
    s.append(f'<text x="{x}" y="276" font-size="11" font-weight="600">confirmed</text>')
    s.append(f'<text x="{x}" y="290" font-size="11" fill="{INK2}">{mods}×12 beds</text>')
    x += wards_w
    s.append(f'<rect x="{x + 6}" y="40" width="60" height="100" fill="#fff" stroke="{INK}"/>')
    s.append(f'<text x="{x + 10}" y="58" font-size="10">doffing</text><text x="{x + 10}" y="72" font-size="10">+ shower</text>')
    s.append(f'<rect x="{x + 6}" y="150" width="60" height="50" fill="{INK3}" stroke="{INK}"/>')
    s.append(f'<text x="{x + 10}" y="170" font-size="10" fill="#fff">morgue</text>')
    s.append(f'<rect x="{x + 6}" y="208" width="60" height="52" fill="#fff" stroke="{INK}"/>')
    s.append(f'<text x="{x + 10}" y="226" font-size="10">discharge</text><text x="{x + 10}" y="240" font-size="10">shower</text>')
    s.append(f'<text x="{x + 6}" y="{H - 6}" font-size="10" font-weight="700" fill="{RED_RAMP[4]}">HIGH RISK</text>')
    # staff loop
    s.append(f'<path d="M100,40 C100,8 {x + 36},8 {x + 36},38" fill="none" stroke="{AQUA}" stroke-width="1.6" marker-end="url(#fa)"/>')
    s.append("</svg>")
    return "".join(s)


def p_units():
    mods = sorted({st["modules"] for st in D["sites"]})
    pick = [mods[0], mods[len(mods) // 2], mods[-1]] if len(mods) >= 3 else (mods + [mods[-1] * 2, mods[-1] * 3])[:3]
    pick = sorted(set(pick)) if len(set(pick)) == 3 else [1, 2, max(mods[-1], 4)]
    names = {st["modules"]: PA[st["patch"]]["n"] for st in D["sites"]}
    cards = "".join(f'<figure class="plan">{etu_plan(m)}<figcaption><b>{m} module{"s" if m > 1 else ""} · {m * 12} beds</b>'
                    f'{" · e.g. " + escape(names[m]) if m in names else ""}</figcaption></figure>' for m in pick)
    return f"""
<p class="intro">The generator turns a site's bed demand into a plan. The ward sequence and circulation rules come straight from the
MSF three-ward model in <span class="mono">References/An Ebola treatment centre2.docx</span>. Only the confirmed ward grows; the rest stays fixed.</p>
<div class="g3">{cards}</div>
<div class="g3 tight">
  <div class="col"><h3>Encoded rules</h3><ul>
    <li>Sequence: triage → suspect → probable → confirmed → morgue / discharge</li>
    <li>All paths fenced and one-way; staff loop enters green, exits through doffing</li>
    <li>Foot basin + shower at every red→green crossing</li>
    <li>Double fence at 1 m; separate patient and staff gates</li>
    <li>Module = 12 beds (2015 brief); lab within the 500 km² coverage of the mobile lab</li></ul></div>
  <div class="col"><h3>Parameters</h3><table class="t">
    <tr><td>beds_needed</td><td>from stage 04, per site</td></tr>
    <tr><td>module_beds</td><td>12</td></tr>
    <tr><td>staff_ratio</td><td>{todo("check the draft ratios in pipeline/s3_params.py against MSF/WHO guidance", "M", "Verify step 3 ratios (staff, water, areas)")}</td></tr>
    <tr><td>plot_bounds</td><td>from siting constraints</td></tr></table></div>
  <div class="col">
    {todo("Open grasshopper/surge_draw_layouts.py and the Hops server in Rhino 8, check the geometry, then swap the plain extrusions for the modelled origami tent.", "H",
          "Test the generator in Rhino 8 + model the tent")}
    {todo("Bring in the 2015 origami tent and negative-pressure module as the 3D kit of parts. Re-model it cleanly in Rhino.", "M",
          "Re-model origami tent + HVAC module in Rhino")}
    {todo("Render one hero axonometric of the largest site (deployed camp, as on the 2015 'Deployed unit' board).", "M",
          "Hero axonometric of largest site")}
  </div>
</div>"""


# ================= PAGE 9 — after-use
def p_after():
    W = 1500
    stages = [("Weeks 0–4", "Deploy", "Modules + mobile lab", RED_RAMP[3]),
              ("Weeks 4–30", "Operate", "Wards grow and shrink with the forecast", RED_RAMP[2]),
              ("Weeks 30–42", "Decommission", "Decontaminate · 42 days, no new cases", INK3),
              ("Year 1+", "Convert", "Learning centre · workshop · garden", AQUA)]
    svg = [f'<svg viewBox="0 0 {W} 150" width="100%" font-family="Inter">']
    bw = (W - 40) / 4
    for i, (t, h, d, c) in enumerate(stages):
        x = 20 + i * bw
        svg.append(f'<rect x="{x}" y="20" width="{bw - 8}" height="10" fill="{c}"/>')
        svg.append(f'<text x="{x}" y="58" font-size="13" fill="{INK2}" font-family="DejaVu Sans Mono">{t}</text>')
        svg.append(f'<text x="{x}" y="88" font-size="24" font-weight="700" fill="{INK}">{h}</text>')
        svg.append(f'<text x="{x}" y="114" font-size="14" fill="{INK2}">{escape(d)}</text>')
    svg.append("</svg>")
    return f"""
<p class="intro">The long-term phase from 2015 stays in. Once a site's forecast demand stays at zero, its modules are reassigned.
The fixed parts (slab, water treatment, power) become the base for a community centre run for the families affected.</p>
{''.join(svg)}
<div class="g3">
  <figure><img src="img/g7_sk-18.jpg"/><figcaption>2015 · Learning centre sketch</figcaption></figure>
  <figure><img src="img/g7_sk-19.jpg"/><figcaption>2015 · Workshop sketch</figcaption></figure>
  <div class="col"><h3>Conversion rule (draft)</h3>
    <p class="mono">if demand(site, t) == 0 for 42 days:<br>&nbsp;&nbsp;wards → classrooms / workshops<br>
    &nbsp;&nbsp;green zone → admin + counselling<br>&nbsp;&nbsp;water unit → kept; garden on decontaminated slab</p>
    {todo("Write the conversion as rules, using the 2015 workshop table (learning centre 1:20, counselling 3×/wk, gardening, cooking, carpentry) as the brief for each programme.", "M",
          "Formalise conversion rules from 2015 programme table")}
    {todo("Check the 42-day end-of-outbreak rule and the decontamination steps against WHO guidance, and cite them.", "L",
          "Cite WHO end-of-outbreak + decon guidance")}
    {todo("Redraw the two sketches in the same line style as the new plans, or keep them as-is and label them as 2015 work.", "L",
          "Decide: redraw or keep 2015 sketches")}
  </div>
</div>"""


# ================= PAGE 10 — interface
def p_interface():
    def ex(f):
        s = ""
        row = D["prev"][19]
        vmax = max(max(r) for r in D["prev"])
        for k in range(len(PA)):
            c = ramp(row[k], vmax)
            if c:
                s += dots(f, [(PA[k]["x"], PA[k]["y"])], 4, c, PAPER)
        for st in D["sites"]:
            sp = PA[st["patch"]]
            s += dots(f, [(sp["x"], sp["y"])], 5 + 2.5 * st["modules"], "none", BLUE)
        return s
    m = base_map(900, roads="all", water=True, forest=True, extra=ex)
    return f"""
<p class="intro">The working output is an interactive map, not a static board. A reviewer can scrub through time, change the
assumptions and watch the sites and wards update.</p>
<div class="app">
  <div class="bar"><b>S.U.R.G.E.</b><span>Forest Guinea · 2014</span><span class="pill">Scenario: with response</span><span class="pill ghost">No response</span><span class="pill ghost">Rainy season</span></div>
  <div class="appbody">
    <div class="side">
      <h4>Assumptions</h4>
      <div class="sl"><span>R₀</span><i style="--v:.55"></i><b>1.7</b></div>
      <div class="sl"><span>Coverage time</span><i style="--v:.4"></i><b>{D['cover_h']} h</b></div>
      <div class="sl"><span>Max sites</span><i style="--v:.35"></i><b>{D['k_sites']}</b></div>
      <div class="sl"><span>Beds / module</span><i style="--v:.3"></i><b>12</b></div>
      <div class="sl"><span>Isolation effect</span><i style="--v:.6"></i><b>60%</b></div>
      <h4>Selected site</h4>
      <p><b>{escape(PA[D['sites'][0]['patch']]['n'])}</b><br>{D['sites'][0]['modules']} modules · {D['sites'][0]['modules'] * 12} beds<br>serves {len(D['sites'][0]['reach'])} clusters</p>
      {ph("ward plan thumbnail", "120px")}
    </div>
    <div class="mapwrap">{m}
      <div class="time"><span>wk 0</span><div class="track"><i style="left:38%"></i></div><span>wk 52</span><b>week 20</b></div>
    </div>
  </div>
</div>
<div class="g3 tight">
  <div class="col">{todo("Build the web map (MapLibre or deck.gl). Precompute scenarios as JSON so it runs as a static page.", "H", "Build interactive web map")}</div>
  <div class="col">{todo("Record a 60–90 s screen capture of the slider and scenario switch for the portfolio and LinkedIn.", "M", "Screen-capture video of the tool")}</div>
  <div class="col">{todo("Decide whether the live tool is public. If so, add a clear 'research prototype, not for operational use' disclaimer.", "M", "Public tool? + disclaimer")}</div>
</div>"""


# ================= PAGE 11 — validation & reflection
def p_validation():
    rows = "".join(f'<tr><td>{escape(PA[st["patch"]]["n"])}</td><td>{st["modules"]}×12</td><td class="mut">—</td><td class="mut">—</td></tr>'
                   for st in D["sites"])
    return f"""
<div class="g2">
  <div>
    <h3>Model vs. what actually happened</h3>
    <table class="t wide"><tr><th>Computed site</th><th>Modules</th><th>Prefecture</th><th>CTE there in 2014 sitreps?</th></tr>{rows}</table>
    {todo("Compare computed sites with the prefectures where CTEs operated in the 2014 sitreps (Guéckédou, Macenta). Discuss any site with no counterpart.", "H",
          "Compare sites with 2014 CTE prefectures")}
    {ph("Chart: modelled vs observed weekly cases (after calibration)", "220px")}
  </div>
  <div class="col">
    <h3>Limitations, stated plainly</h3>
    <ul>
      <li>OSM in 2014 was incomplete in rural Guinea. Road gaps bias travel times upward.</li>
      <li>Population is a proxy until WorldPop is added.</li>
      <li>The SEIR model is deterministic and uncalibrated. It overstates spread by orders of magnitude.</li>
      <li>Greedy siting is not optimal. It is only a baseline for the MILP.</li>
      <li>Community trust, burial practices and security shaped the real response, and none of them are in the model.</li>
    </ul>
    <h3>Reflection: 2015 → 2026</h3>
    {todo("Write 150–200 words in your own voice: what you'd now do differently, what computational design means to you, and how it shows in this rework.", "H",
          "Write personal reflection (150–200 words)")}
    {todo("Get one outside reviewer (epidemiologist or humanitarian logistician) to read pages 05–07 and quote their feedback.", "M",
          "External expert review + quote")}
  </div>
</div>"""


# ================= PAGE 12 — checklist
def p_todo():
    pri_name = {"H": "Must do", "M": "Should do", "L": "Nice to have"}
    cols = []
    for p in ("H", "M", "L"):
        items = "".join(f'<li><span class="box"></span><b>{t["id"]}</b> {escape(t["text"])}<em>p.{t["page"]:02d}</em></li>'
                        for t in TODOS if t["pri"] == p)
        cols.append(f'<div class="col"><h3><span class="todo"><b>{pri_name[p]}</b></span></h3><ul class="check">{items}</ul></div>')
    return f"""
<p class="intro">Every yellow <span class="todo"><b>YOU</b></span> marker in this mockup, collected here. Everything else on these
pages, including the maps, catchments, outbreak curves and siting numbers, was <b>computed from the 2014 data already in this repo</b> and is a
working prototype you can build on.</p>
<div class="g3">{''.join(cols)}</div>
<div class="g3 tight">
  <div class="col"><h3>Suggested order</h3><p class="mono">1 data gaps → 2 calibrate → 3 MILP siting → 4 Grasshopper units → 5 web map → 6 boards + reflection</p></div>
  <div class="col"><h3>Legend</h3><p><span class="todo"><b>YOU · Txx</b> task</span> = needs you &nbsp; {ph("placeholder", "40px", "inline")}</p></div>
  <div class="col"><h3>Regenerate</h3><p class="mono">cd rework/mockup/build<br>python3 compute.py &amp;&amp; python3 render.py<br>node pdf.mjs &nbsp;# needs playwright</p></div>
</div>"""


page(1, "Cover", "", p_cover, "cov")
page(2, "Origin · 2015", "Where this started", p_origin)
page(3, "System", "From diagram to pipeline", p_system)
page(4, "Stage 01 · Data", "What the system reads", p_data)
page(5, "Stage 02 · Outbreak", "Where the virus goes, week by week", p_outbreak)
page(6, "Stage 03 · Access", "Distance is travel time, not straight lines", p_access)
page(7, "Stage 04 · Siting", "Fewer units, placed where they're needed", p_siting)
page(8, "Stage 05 · Units", "Plans generated from demand", p_units)
page(9, "Stage 06 · After-use", "The long-term response", p_after)
page(10, "Interface", "A tool, not a board", p_interface)
page(11, "Validation", "Testing the model against 2014", p_validation)
page(12, "Your to-do list", "What's left for you", p_todo)

CSS = open("style.css").read()
html = (f'<!doctype html><html><head><meta charset="utf-8"><title>SURGE rework mockup</title><style>{CSS}</style></head><body>'
        + "".join(shell(*p) for p in PAGES) + "</body></html>")
open("mockup.html", "w").write(html)
print("pages", len(PAGES), "todos", len(TODOS), "html bytes", len(html))
