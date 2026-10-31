const { chromium } = await import(process.env.PLAYWRIGHT_MODULE ?? "playwright")
import assert from "node:assert/strict"
import fs from "node:fs/promises"

const args = process.argv.slice(2)
const argument = (name) => (args.includes(name) ? args[args.indexOf(name) + 1] : undefined)
const origin = argument("--origin") ?? process.env.QUARTZ_GRAPH_URL
assert.ok(origin, "--origin URL or QUARTZ_GRAPH_URL is required")
const sites = [{ id: "site", url: origin }]
const selected = argument("--site")
const report = { pass: false, checked_at: new Date().toISOString(), checks: [], failures: [] }
const browsers = new Map()
const scenarios = [
  { id: "desktop", width: 1440 },
  { id: "lost-graphics-context", width: 1440, contextLoss: true },
  { id: "no-gpu-mobile", width: 390, noGpu: true },
  { id: "corrupt-storage", width: 1440, corruptStorage: true },
  { id: "blocked-storage-mobile", width: 390, blockedStorage: true },
  { id: "slow-index-mobile", width: 390, slowIndex: true },
  { id: "failed-index-retry", width: 1440, failedIndex: true },
]

async function triggerGraph(page) {
  for (const selector of ["[data-open-graph]", ".global-graph-icon"]) {
    const matches = page.locator(selector)
    for (const target of await matches.all()) {
      if (await target.isVisible()) {
        await target.click()
        return
      }
    }
  }
  throw new Error("No visible graph control")
}

async function readyGraph(page) {
  const dialog = page.locator(".global-graph-outer.active")
  await dialog.waitFor({ state: "visible", timeout: 5000 })
  await dialog.locator("canvas, svg.graph-svg").waitFor({ state: "visible", timeout: 20000 })
  assert.equal(await dialog.locator("canvas, svg.graph-svg").count(), 1)
  return dialog
}

try {
  for (const site of sites.filter((site) => !selected || site.id === selected)) {
    for (const scenario of scenarios) {
      const key = scenario.noGpu ? "no-gpu" : "normal"
      if (!browsers.has(key))
        browsers.set(
          key,
          await chromium.launch({
            executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE,
            headless: true,
            args: scenario.noGpu ? ["--disable-webgl", "--disable-webgl2", "--disable-webgpu"] : [],
          }),
        )
      const context = await browsers
        .get(key)
        .newContext({ viewport: { width: scenario.width, height: 950 } })
      const page = await context.newPage()
      const errors = []
      let rejectIndex = Boolean(scenario.failedIndex)
      let interceptedIndexes = 0
      page.on("pageerror", (error) => errors.push(error.message))
      try {
        if (scenario.contextLoss)
          await page.addInitScript(() => {
            if (typeof GPUAdapter === "undefined") return
            const requestDevice = GPUAdapter.prototype.requestDevice
            GPUAdapter.prototype.requestDevice = async function (...arguments_) {
              const device = await requestDevice.apply(this, arguments_)
              window.__quartzGraphGpuDevices ??= []
              window.__quartzGraphGpuDevices.push(device)
              return device
            }
          })
        if (scenario.corruptStorage)
          await page.addInitScript(() => localStorage.setItem("graph-visited", "{broken"))
        if (scenario.blockedStorage)
          await page.addInitScript(() => {
            const read = Storage.prototype.getItem
            const write = Storage.prototype.setItem
            Storage.prototype.getItem = function (key) {
              if (key === "graph-visited") throw new DOMException("Blocked", "SecurityError")
              return read.call(this, key)
            }
            Storage.prototype.setItem = function (key, value) {
              if (key === "graph-visited") throw new DOMException("Blocked", "SecurityError")
              return write.call(this, key, value)
            }
          })
        if (scenario.slowIndex)
          await page.route(/\/(navigation|content|graph)Index\.json(?:\?|$)/, async (route) => {
            interceptedIndexes++
            await new Promise((resolve) => setTimeout(resolve, 1500))
            await route.continue().catch(() => {})
          })
        if (scenario.failedIndex)
          await page.route(/\/(navigation|content|graph)Index\.json(?:\?|$)/, async (route) => {
            interceptedIndexes++
            if (rejectIndex) await route.fulfill({ status: 503, body: "Temporary index failure" })
            else await route.continue()
          })
        const response = await page.goto(site.url, { waitUntil: "domcontentloaded" })
        assert.equal(response.status(), 200)
        await triggerGraph(page)
        if (scenario.failedIndex) {
          const retry = page
            .locator(".global-graph-outer.active")
            .getByRole("button", { name: "Retry graph", exact: true })
          await retry.waitFor({ state: "visible", timeout: 20000 })
          rejectIndex = false
          await retry.click()
        }
        if (scenario.slowIndex) {
          await page
            .locator(".global-graph-outer.active")
            .waitFor({ state: "visible", timeout: 5000 })
          await page.keyboard.press("Escape")
          await page.waitForTimeout(1800)
          assert.equal(
            await page.locator(".global-graph-outer.active").count(),
            0,
            "Closed graph reopened after async render",
          )
          await triggerGraph(page)
        }
        const dialog = await readyGraph(page)
        if (scenario.contextLoss && (await dialog.locator("canvas").count())) {
          await dialog.locator("canvas").evaluate((canvas) => {
            const context = canvas.getContext("webgl2") ?? canvas.getContext("webgl")
            const extension = context?.getExtension("WEBGL_lose_context")
            if (extension) extension.loseContext()
            else if (window.__quartzGraphGpuDevices?.length) {
              for (const device of window.__quartzGraphGpuDevices) device.destroy()
            } else throw new Error("Cannot exercise a real graphics-context loss")
          })
          await dialog.locator("svg.graph-svg").waitFor({ state: "visible" })
          assert.ok((await dialog.locator("svg.graph-svg circle").count()) > 0)
        }
        if (scenario.noGpu) {
          assert.ok(
            (await dialog.locator("svg.graph-svg circle").count()) > 0,
            "SVG graph has no nodes",
          )
          assert.ok(
            (await dialog.locator("svg.graph-svg a[href]").count()) > 0,
            "SVG graph has no navigable nodes",
          )
          const nodeSize = await dialog.locator("svg.graph-svg circle").first().boundingBox()
          assert.ok(nodeSize.width >= 3.9, "Graph nodes disappear when fitted to the viewport")
          await page.screenshot({ path: `/tmp/quartz-graph-${site.id}-${scenario.id}.png` })
          const circle = await dialog.locator("svg.graph-svg circle").first().boundingBox()
          await page.mouse.move(circle.x + circle.width / 2, circle.y + circle.height / 2)
          await page.mouse.down()
          await page.mouse.move(circle.x + circle.width / 2 + 25, circle.y + circle.height / 2 + 25)
          await page.keyboard.press("Escape")
          await page.mouse.move(20, 20)
          await page.mouse.up()
          await triggerGraph(page)
          await readyGraph(page)
          const bounds = await dialog.locator("svg.graph-svg").boundingBox()
          await page.mouse.move(bounds.x + 4, bounds.y + 4)
          await page.mouse.down()
          await page.mouse.move(bounds.x + 20, bounds.y + 20)
          await page.keyboard.press("Escape")
          await page.mouse.move(25, 25)
          await page.mouse.up()
          await triggerGraph(page)
          await readyGraph(page)
        }
        await page.keyboard.press("Escape")
        await dialog.waitFor({ state: "hidden" })
        await triggerGraph(page)
        await readyGraph(page)
        const close = page.getByRole("button", { name: "Close graph", exact: true })
        if (await close.count()) await close.click()
        else await page.keyboard.press("Escape")
        await dialog.waitFor({ state: "hidden" })
        assert.deepEqual(
          scenario.failedIndex
            ? errors.filter((error) => !/HTTP 503|Failed to fetch|Unexpected token/.test(error))
            : errors,
          [],
        )
        if (scenario.slowIndex || scenario.failedIndex)
          assert.ok(interceptedIndexes > 0, "Index fault was not exercised")
        report.checks.push({ site: site.id, scenario: scenario.id, pass: true })
        console.log(`PASS ${site.id} ${scenario.id}`)
      } catch (error) {
        report.failures.push({
          site: site.id,
          scenario: scenario.id,
          error: String(error),
          browser_errors: errors,
        })
        await page
          .screenshot({ path: `/tmp/quartz-graph-${site.id}-${scenario.id}-failure.png` })
          .catch(() => {})
        console.error(`FAIL ${site.id} ${scenario.id}: ${error.message}`)
      } finally {
        await context.close()
      }
    }
  }
  assert.ok(report.checks.length + report.failures.length > 0, "No sites selected")
  report.pass = report.failures.length === 0
} finally {
  for (const browser of browsers.values()) await browser.close()
  const destination = argument("--report") ?? "/tmp/quartz-graph-checks.json"
  await fs.writeFile(destination, JSON.stringify(report, null, 2) + "\n")
}
if (!report.pass) process.exitCode = 1
