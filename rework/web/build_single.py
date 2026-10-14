"""Bundle the planner into one HTML file (CSS and JS inlined; data stays in data/).

    python build_single.py      → dist/index.html  (+ copy data/ next to it)

Used to publish the page where only a single page plus data files can be uploaded. GitHub Pages serves the normal
index.html directly and does not need this.
"""
import re
import shutil
from pathlib import Path

HERE = Path(__file__).parent
DIST = HERE / "dist"
html = (HERE / "index.html").read_text()
css = (HERE / "vendor/leaflet.css").read_text() + "\n" + (HERE / "css/app.css").read_text()
engine = (HERE / "js/engine.js").read_text().replace("export function", "function").replace("export const", "const")
app = re.sub(r'^import .*?;\n', "", (HERE / "js/app.js").read_text(), flags=re.S | re.M)
libs = "\n".join((HERE / f"vendor/{f}").read_text() for f in ("leaflet.js", "three.min.js", "OrbitControls.js"))

body = html.split("<body>", 1)[1].split("</body>", 1)[0]
head = html.split("<head>", 1)[1].split("</head>", 1)[0]
head = re.sub(r'<link rel="stylesheet" href="(vendor|css)/[^"]+">\n?', "", head)
head = re.sub(r'<meta (charset|name="viewport")[^>]*>\n?', "", head)
body = re.sub(r'<script[^>]*src="[^"]+"></script>\n?', "", body)
out = (head.strip() + f"\n<style>\n{css}\n</style>\n" + body.strip() +
       f"\n<script>\n{libs}\n</script>\n<script type=\"module\">\n{engine}\n{app}\n</script>\n")
DIST.mkdir(exist_ok=True)
(DIST / "index.html").write_text(out)
shutil.copytree(HERE / "data", DIST / "data", dirs_exist_ok=True)
print(f"wrote {DIST / 'index.html'} ({len(out) / 1e6:.1f} MB) and dist/data/")
