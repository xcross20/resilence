import { chromium } from "playwright-core";

const browser = await chromium.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});
const page = await browser.newPage();
const notes = [];
function step(name) {
  notes.push(name);
  console.log("STEP", name);
}

await page.goto("http://127.0.0.1:3000/operate", { waitUntil: "networkidle" });
step("operate");
const banner = await page.locator(".demo-strip").innerText();
const normalized = banner.toLowerCase();
if (!normalized.includes("synthetic demo") || !normalized.includes("not production authority")) {
  throw new Error(`banner missing: ${banner}`);
}
await page.getByRole("link", { name: "Investigate" }).click();
await page.waitForURL("**/investigate");
step("investigate");
if ((await page.content()).includes("reference_category")) throw new Error("reference label leaked");
const caseLink = page.locator("table a").first();
await caseLink.click();
await page.waitForURL((url) => url.searchParams.has("case"));
step("case");
await page.getByRole("link", { name: "Strategies" }).click();
await page.waitForURL("**/strategies");
step("strategies");
if (!(await page.locator("body").innerText()).includes("completed_eligible")) throw new Error("no eligible row");
await page.getByRole("link", { name: "Releases" }).click();
await page.waitForURL("**/releases");
step("releases");
const form = page.locator("form").first();
await form.locator("button").click();
await form.locator("pre").waitFor();
const denied = await form.locator("pre").innerText();
if (!denied.includes("missing_approval")) throw new Error(denied);
if (denied.includes('"production_authority": true')) throw new Error("production authority granted");
step("missing-confirmation");
await form.locator('input[name="confirmation"]').fill("activate_synthetic_revision");
await form.locator("button").click();
await form.locator("pre").getByText("activation_committed").waitFor();
const activated = await form.locator("pre").innerText();
if (activated.includes('"production_authority": true')) throw new Error("production authority granted");
if (!activated.includes('"eligibility_authoritative": true')) throw new Error(activated);
step("activation-committed");
await page.reload({ waitUntil: "networkidle" });
const after = await page.locator("body").innerText();
if (!after.toLowerCase().includes("synthetic demo")) throw new Error("banner lost after reload");
if (!after.includes("activation_committed")) throw new Error("event missing after reload");
step("history");
console.log(activated.slice(0, 400));
console.log(notes.join(" > "));
await browser.close();
