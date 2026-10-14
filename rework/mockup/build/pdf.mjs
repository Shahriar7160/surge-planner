// Print mockup.html to ../SURGE_rework_mockup.pdf with the preinstalled Chromium.
import { createRequire } from "module";
import { pathToFileURL } from "url";
import path from "path";

const require = createRequire(import.meta.url);
let pw;
try { pw = require("playwright"); } catch { pw = require(process.env.PW_PATH || "/opt/node-tools/node_modules/playwright"); }

const here = path.dirname(new URL(import.meta.url).pathname);
const browser = await pw.chromium.launch();
const page = await browser.newPage();
await page.goto(pathToFileURL(path.join(here, "mockup.html")).href, { waitUntil: "load" });
await page.pdf({ path: path.join(here, "..", "SURGE_rework_mockup.pdf"), width: "420mm", height: "297mm", printBackground: true });
if (process.argv.includes("--png")) {
  await page.setViewportSize({ width: 1588, height: 1123 });
  const n = await page.locator("section.page").count();
  for (let i = 0; i < n; i++) {
    await page.locator("section.page").nth(i).screenshot({ path: path.join(here, "png", `p${String(i + 1).padStart(2, "0")}.png`) });
  }
}
await browser.close();
