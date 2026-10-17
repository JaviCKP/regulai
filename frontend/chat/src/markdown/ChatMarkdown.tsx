import { memo, useCallback, useLayoutEffect, useRef } from "react"

import { cn } from "@/lib/utils"
import { copyText } from "@/lib/clipboard"

import { clear, render } from "./renderer"

/* The single content policy for model and document text in the chat.
 * The renderer owns this element's children (a clear DOM boundary: React never
 * renders inside it); it only creates text nodes and allowlisted elements.
 * Streaming re-renders reuse finished blocks, so history and selections in
 * closed blocks are untouched while the last block grows. */

type Props = {
  source: string
  projection?: import("@/types").NaturalProjection
  streaming?: boolean
  /** Fade in blocks that appear while this message is live; history never animates. */
  animate?: boolean
  onCite?: (index: string) => void
  onCopied?: (ok: boolean) => void
  className?: string
}

export const ChatMarkdown = memo(function ChatMarkdown({ source, projection, streaming = false, animate = false, onCite, onCopied, className }: Props) {
  const ref = useRef<HTMLDivElement>(null)

  useLayoutEffect(() => {
    const root = ref.current
    if (!root) return
    if (projection) {
      clear(root)
      // Authorised originals are opaque data, including Markdown destinations,
      // HTML and nested tokens. No parser, link, image or preview sees them.
      for (const segment of projection.segments) {
        const span = document.createElement("span")
        span.textContent = segment.text
        span.dataset.privacyStart = String(segment.start)
        span.dataset.privacyEnd = String(segment.end)
        root.append(span)
      }
      return
    }
    if (!source) clear(root)
    else render(root, source, { streaming, animate })
  }, [source, projection, streaming, animate])

  const click = useCallback(async (event: React.MouseEvent<HTMLDivElement>) => {
    const target = event.target as HTMLElement
    const copy = target.closest<HTMLButtonElement>(".rg-code-copy")
    if (copy) {
      const ok = await copyText(copy.dataset.copy ?? "")
      onCopied?.(ok)
      if (!ok) return
      copy.textContent = "Copiado"
      copy.dataset.done = ""
      window.setTimeout(() => {
        copy.textContent = "Copiar"
        delete copy.dataset.done
      }, 1600)
      return
    }
    const cite = target.closest<HTMLElement>(".rg-cite")
    if (cite?.dataset.cite) onCite?.(cite.dataset.cite)
  }, [onCite, onCopied])

  return (
    <div
      ref={ref}
      className={cn("rg-md", projection && "whitespace-pre-wrap break-words", className)}
      data-streaming={streaming ? "" : undefined}
      aria-busy={streaming || undefined}
      onClick={click}
    />
  )
})
