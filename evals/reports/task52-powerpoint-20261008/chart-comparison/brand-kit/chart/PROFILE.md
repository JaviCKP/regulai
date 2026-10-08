# Brand Profile: chart

- kind: pptx

## Roles

Each role lists its concrete style and its usage (scope · placement · required).
`structural` roles belong to the ordered skeleton and must appear in their slot;
`freeform` roles are used on demand inside the freeform body region.

- `cover.title`: placeholder (robust) - usage: n/a
- `heading.1`: placeholder (best_effort) - usage: n/a
- `paragraph`: placeholder (best_effort) - usage: n/a

## Brand palette roles

Semantic color tokens captured from the template. Reference THESE names
(or a theme slot like `accent1`) as run color tokens; never a raw hex.

- `primary` -> `accent1` (#4F81BD)
- `text` -> `dk1` (#000000)

## Authoring hints

- Pick blocks by MEANING using the role table above; the engine resolves
  every role to the template's own artifacts. Never name a style, font,
  or hex anywhere in the input: the profile is the only source.
- Respect the ordered skeleton (Structure section, when present): cover
  content first, derived indexes where the template keeps them, then the
  freeform body in the template's own order.
- After `comprehend`, reusable fragments (components/sections) may be
  available in `profile.json` under `comprehension.fragments`: prefer
  them over re-deriving recurring layouts.
