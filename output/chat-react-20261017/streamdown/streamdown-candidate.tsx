/* Evaluation only (task 80): Streamdown 2.7.0 configured with the chat's content
 * policy, run against the same contract suite as ChatMarkdown. Not imported by
 * the application unless it passes that suite. */
import { Children, isValidElement, type ReactNode } from "react"
import { defaultRemarkPlugins, Streamdown } from "streamdown"
import { visit, SKIP } from "unist-util-visit"
import rehypeSanitize, { defaultSchema } from "rehype-sanitize"

/** GitHub schema plus the two labelled inline elements of the policy. */
const schema = {
  ...defaultSchema,
  attributes: {
    ...defaultSchema.attributes,
    span: [...(defaultSchema.attributes?.span ?? []), ["className", "rg-redacted"], "title"],
    sup: [...(defaultSchema.attributes?.sup ?? []), ["className", "rg-cite"], "dataCite"],
  },
  clobberPrefix: "",
}

import { MARKER_LABEL } from "./renderer"

const SAFE_URL = /^(?:https?:\/\/|mailto:)[^\s<>"']+$/i
const INLINE = /\[\[REGULAI_(PERSON|LOCATION|ORGANIZATION|EMAIL|PHONE|ID|ACCOUNT|CARD|SECRET)\]\]|\[(\d{1,2})\](?!\()/g

type MdNode = { type: string; value?: string; children?: MdNode[]; alt?: string; data?: Record<string, unknown> }

/** Raw HTML stays visible text and images never load: both become text nodes. */
function literalHtmlAndImages() {
  return (tree: MdNode) => {
    visit(tree as never, (node: MdNode) => {
      if (node.type === "html") node.type = "text"
      if (node.type === "image") {
        node.type = "text"
        node.value = `!${node.alt ?? ""}`
      }
    })
  }
}

/** Masking markers and [n] citations as the same labelled elements as the legacy renderer. */
function regulaiInline() {
  return (tree: MdNode) => {
    visit(tree as never, "text", (node: MdNode, index: number | undefined, parent: MdNode | undefined) => {
      if (!parent || index === undefined || typeof node.value !== "string") return
      const value = node.value
      const parts: MdNode[] = []
      let last = 0
      for (const match of value.matchAll(INLINE)) {
        if (match.index! > last) parts.push({ type: "text", value: value.slice(last, match.index) })
        if (match[1]) {
          parts.push({ type: "regulaiMarker", data: { hName: "span", hProperties: { className: ["rg-redacted"], title: "Dato enmascarado antes de salir de la organización" },
            hChildren: [{ type: "text", value: `${MARKER_LABEL[match[1]]} protegido` }] } })
        } else {
          parts.push({ type: "regulaiCite", data: { hName: "sup", hProperties: { className: ["rg-cite"], dataCite: match[2] }, hChildren: [{ type: "text", value: match[2] }] } })
        }
        last = match.index! + match[0].length
      }
      if (!parts.length) return
      if (last < value.length) parts.push({ type: "text", value: value.slice(last) })
      parent.children!.splice(index, 1, ...parts)
      return [SKIP, index + parts.length]
    })
  }
}

const text = (children: ReactNode): string => Children.toArray(children).map((child) =>
  typeof child === "string" || typeof child === "number" ? String(child) : isValidElement(child) ? text((child.props as { children?: ReactNode }).children) : "").join("")

export function StreamdownCandidate({ source, streaming = false }: { source: string; streaming?: boolean }) {
  return (
    <div className="rg-md">
      <Streamdown
        mode={streaming ? "streaming" : "static"}
        parseIncompleteMarkdown={streaming}
        controls={false}
        remarkPlugins={[...Object.values(defaultRemarkPlugins), literalHtmlAndImages, regulaiInline]}
        rehypePlugins={[[rehypeSanitize, schema]]}
        isAnimating={streaming}
        components={{
          h1: ({ children }) => <h2>{children}</h2>,
          h2: ({ children }) => <h3>{children}</h3>,
          h3: ({ children }) => <h4>{children}</h4>,
          h4: ({ children }) => <h5>{children}</h5>,
          a: ({ href, children }) => (typeof href === "string" && SAFE_URL.test(href)
            ? <a href={href} target="_blank" rel="noopener noreferrer nofollow">{children}</a> : <>{children}</>),
          img: () => null,
          strong: ({ children }) => <strong>{children}</strong>,
          em: ({ children }) => <em>{children}</em>,
          table: ({ children }) => <div className="rg-table" role="region" aria-label="Tabla" tabIndex={0}><table>{children}</table></div>,
          input: ({ checked }) => <span className={`rg-task${checked ? " is-done" : ""}`} aria-label={checked ? "Hecho" : "Pendiente"}>{checked ? "✓" : ""}</span>,
          pre: ({ children }) => {
            const code = Children.toArray(children)[0]
            const props = isValidElement(code) ? (code.props as { className?: string; children?: ReactNode }) : {}
            const lang = /language-([\w#+.-]+)/.exec(props.className ?? "")?.[1] ?? ""
            const body = text(props.children).replace(/\n$/, "")
            return (
              <figure className="rg-code">
                <figcaption className="rg-code-bar"><span className="rg-code-lang">{lang || "texto"}</span>
                  <button type="button" className="rg-code-copy" aria-label="Copiar código" data-copy={body}>Copiar</button></figcaption>
                <pre><code data-lang={lang || undefined}>{body}</code></pre>
              </figure>
            )
          },
        }}
      >
        {source}
      </Streamdown>
    </div>
  )
}
