import { render } from "@testing-library/react"
import type { ComponentType } from "react"
import { describe, expect, it } from "vitest"

import { ChatMarkdown } from "./ChatMarkdown"
import { StreamdownCandidate } from "./streamdown-candidate"

/* Equivalence gate (task 80): the same content-policy checks for the current
 * renderer and the Streamdown candidate. Results are recorded in the task. */

type Engine = ComponentType<{ source: string; streaming?: boolean }>
const engines: [string, Engine][] = [["legacy", ChatMarkdown], ["streamdown", StreamdownCandidate]]

const root = (container: HTMLElement) => container.querySelector(".rg-md") as HTMLElement

describe.each(engines)("%s renderer", (_name, Engine) => {
  const view = (source: string, streaming = false) => root(render(<Engine source={source} streaming={streaming} />).container)

  it("shows raw HTML as text and loads no images", () => {
    const node = view("<img src=x onerror=alert(1)> **bien** <script>alert(2)</script>\n\n![logo](https://tracker.invalid/p.png)")
    expect(node.querySelectorAll("img, script, iframe")).toHaveLength(0)
    expect(node.textContent).toContain("<img src=x onerror=alert(1)>")
    expect(node.textContent).toContain("<script>alert(2)</script>")
  })

  it("links only http(s) and mailto", () => {
    const node = view("[web](https://example.org/x) [mail](mailto:a@b.es) [js](javascript:alert(1)) [rel](/admin/)")
    expect([...node.querySelectorAll("a")].map((link) => link.getAttribute("href"))).toEqual(["https://example.org/x", "mailto:a@b.es"])
    expect(node.textContent).not.toContain("javascript:")
  })

  it("labels masking markers outside code and citations", () => {
    const node = view("Escribe a [[REGULAI_EMAIL]] o `[[REGULAI_PHONE]]` [2].")
    expect(node.querySelector(".rg-redacted")?.textContent).toBe("correo protegido")
    expect(node.querySelector("code")?.textContent).toBe("[[REGULAI_PHONE]]")
    expect(node.querySelector(".rg-cite")?.textContent).toBe("2")
  })

  it("demotes headings and labels tables and tasks", () => {
    const node = view("# T\n\n| A | B |\n|:--|--:|\n| 1 | 2 |\n\n- [x] Hecho")
    expect(node.querySelector("h1")).toBeNull()
    expect(node.querySelector("h2")?.textContent).toBe("T")
    expect(node.querySelector(".rg-table")?.getAttribute("aria-label")).toBe("Tabla")
    expect(node.querySelector(".rg-task")?.getAttribute("aria-label")).toBe("Hecho")
  })

  it("keeps incomplete fragments readable while streaming", () => {
    expect(view("Texto **negri", true).querySelector("strong")?.textContent).toBe("negri")
    expect(view("Ver [el enlace](https://exa", true).querySelector("a")).toBeNull()
    expect(view("Tabla:\n| Concepto | Límite |", true).textContent?.trim()).toBe("Tabla:")
    expect(view("```js\nconst a = 1", true).querySelector("code")?.textContent).toContain("const a = 1")
  })

  it("keeps the identity of finished blocks while the last grows", () => {
    const { container, rerender } = render(<Engine source={"Primero.\n\nSeg"} streaming />)
    const first = root(container).querySelector("p")
    rerender(<Engine source={"Primero.\n\nSegundo.\n\n- uno"} streaming />)
    expect(root(container).querySelector("p")).toBe(first)
  })

  it("leaves nothing after a retraction", () => {
    const { container, rerender } = render(<Engine source="Retirar" streaming />)
    rerender(<Engine source="" />)
    expect(root(container).textContent).toBe("")
  })
})
