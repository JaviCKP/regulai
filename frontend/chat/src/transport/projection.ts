import type { NaturalProjection } from "../types"

/** Transport assembly only. Detection and resolution belong to the server. */
export function applyProjection(previous: NaturalProjection | undefined, next: NaturalProjection | undefined) {
  if (!next) return undefined
  if (!next.append || !previous) return next
  return { ...next, text: previous.text + next.text, segments: [...previous.segments, ...next.segments] }
}
