// Synthetic privacy acceptance against the committed Django-served build.
// No real provider: ops/chat_ui/lab.py uses a captured httpx.MockTransport.
import { chromium, expect } from "@playwright/test"
import { mkdirSync, readFileSync, writeFileSync } from "node:fs"
import { join, resolve } from "node:path"
import { tmpdir } from "node:os"
import assert from "node:assert/strict"

const out = resolve(process.argv[2] || "../../output/playwright/privacy")
const base = "http://127.0.0.1:8893"
const labDir = join(tmpdir(), "regulai-privacy-lab", "lab")
const lab = JSON.parse(readFileSync(join(labDir, "lab.json"), "utf8"))
assert.equal(lab.fixture, true)
const report = { fixture: true, base, shots: [], errors: [], foreign: [], copy: [], video: null }
mkdirSync(out, { recursive: true })
const browser = await chromium.launch()
async function shot(page, width, name) {
  await page.screenshot({ path: join(out, `${width}-${name}.png`), animations: "disabled", fullPage: false })
  report.shots.push({ width, name, overflow: await page.evaluate(() => document.documentElement.scrollWidth > innerWidth) })
}
try {
  for (const width of [1440, 768, 360]) {
    const context = await browser.newContext({ storageState: join(labDir, "browser-state.json"),
      viewport: { width, height: width === 360 ? 780 : 960 }, locale: "es-ES",
      permissions: ["clipboard-read", "clipboard-write"],
      ...(width === 1440 ? { recordVideo: { dir: join(out, "recording"), size: { width, height: 960 } } } : {}) })
    const page = await context.newPage()
    page.on("pageerror", error => report.errors.push(error.message))
    page.on("request", request => { if (!request.url().startsWith(base) && !/^(blob|data|about):/.test(request.url())) report.foreign.push(request.url()) })
    await page.goto(base + "/settings/privacy/")
    await expect(page.getByRole("heading", { name: "Datos protegidos", exact: true })).toBeVisible()
    await expect(page.getByLabel("Correos electrónicos")).toHaveValue("reversible")
    await shot(page, width, "configuracion")
    await page.getByLabel("Confirmo que este texto es ficticio.").check()
    await page.getByRole("button", { name: "Probar borrador" }).click()
    await expect(page.getByRole("heading", { name: "Con el cambio" })).toBeVisible()
    await page.getByRole("button", { name: "Activar cambios" }).scrollIntoViewIfNeeded()
    await shot(page, width, "diferencias")
    // Explicitly do not activate: this is only a synthetic draft.
    const initial = await page.goto(`${base}/chat/${lab.privacy_chat}/`)
    const html = await initial.text()
    assert(!html.includes("ana@example.invalid"), "Original leaked into initial HTML")
    await expect(page.locator("article[data-turn]").first()).toContainText("Ana Fixture usa ana@example.invalid")
    await page.getByRole("button", { name: "Más opciones de conversación" }).click()
    await page.getByRole("menuitem", { name: "Privacidad de esta conversación", exact: true }).click()
    const inspector = page.getByRole("dialog")
    await expect(inspector.getByRole("button", { name: "Revelar original" }).first()).toBeVisible()
    assert.equal(await inspector.locator("[data-privacy-original]").count(), 0)
    await shot(page, width, "inspector")
    await inspector.getByRole("button", { name: "Revelar original" }).first().click()
    await expect(inspector.locator("[data-privacy-original]")).toBeVisible()
    await shot(page, width, "original-revelado")
    await page.keyboard.press("Escape")
    await expect(page.getByRole("button", { name: "Más opciones de conversación" })).toBeFocused()
    const prompt = page.getByRole("textbox", { name: "Mensaje", exact: true })
    await prompt.fill(`Ana Fixture escribe a ana@example.invalid. Evidencia sintética ${width}.`)
    await page.getByRole("button", { name: "Ver lo que recibirá la IA", exact: true }).click()
    await expect(page.getByRole("heading", { name: "Texto protegido", exact: true })).toBeVisible()
    await shot(page, width, "previsualizacion")
    await page.keyboard.press("Escape")
    await expect(page.getByRole("button", { name: "Ver lo que recibirá la IA", exact: true })).toBeFocused()
    await prompt.press("Enter")
    const turn = page.locator("article[data-turn]").last()
    const live = turn.locator(".rg-md[data-streaming]")
    await expect(live).toContainText("ana@example.invalid", { timeout: 30000 })
    await shot(page, width, "stream-natural")
    await expect(turn.locator(".rg-md[data-streaming]")).toHaveCount(0, { timeout: 45000 })
    const answer = await turn.locator(".rg-md").innerText()
    assert(!answer.includes("[[R_"))
    await turn.getByRole("button", { name: "Copiar texto natural", exact: true }).last().click()
    await expect.poll(async () => (await page.evaluate(() => navigator.clipboard.readText())).replace(/\r\n/g, "\n")).toBe(answer)
    await turn.getByRole("button", { name: /Copiar versión protegida/ }).last().click()
    await expect.poll(() => page.evaluate(() => navigator.clipboard.readText())).toContain('[[R_EMAIL_')
    const copied = await page.evaluate(() => navigator.clipboard.readText())
    assert(copied.includes("[[R_PERSON_") && copied.includes("[[R_EMAIL_"))
    assert(!copied.includes("Ana Fixture") && !copied.includes("ana@example.invalid"))
    report.copy.push({ width, protected: copied, naturalMatches: true })
    await shot(page, width, "copia-protegida")
    await page.reload()
    await expect(page.locator("article[data-turn]").last().locator(".rg-md")).toHaveText(answer)
    await page.evaluate(() => document.documentElement.setAttribute("data-bs-theme", "dark"))
    await shot(page, width, "oscuro")
    const video = page.video()
    await context.close()
    if (video) report.video = await video.path()
  }
  assert.deepEqual(report.errors, [])
  assert.deepEqual(report.foreign, [])
  assert(report.shots.every(shot => !shot.overflow))
} finally {
  writeFileSync(join(out, "report.json"), JSON.stringify(report, null, 2))
  await browser.close()
}
console.log(JSON.stringify(report))
