# UI components

The privacy interface includes source components adapted for regulAI; it makes no
new AI SDK requests and adds no runtime packages.

- **Vercel AI Elements — Artifact**. Source:
  https://github.com/vercel/ai-elements/blob/1310612d305d6c2694a920ff87e38a74ec859e61/packages/elements/src/artifact.tsx
  (`src/components/ai-elements/artifact.tsx`). Apache-2.0; notices and license in
  `licenses/ai-elements.txt` and `licenses/Apache-2.0.txt`. Changes: retain used
  primitives, use existing design tokens, and make the title a semantic heading.
- **React Bits — FadeContent**. Source:
  https://github.com/DavidHDev/react-bits/blob/c83b5e7e026f003af33ff9ebc3d93afb5c86ad22/src/ts-tailwind/Animations/FadeContent/FadeContent.tsx
  (`src/components/react-bits/FadeContent.tsx`). License copied from that commit
  in `licenses/react-bits.txt`. The lightweight CSS version is pinned deliberately:
  current variants add GSAP/effects unnecessary for these short panel transitions.
  Changes: reduced-motion support, timer cleanup, observer fallback, strict types,
  180 ms default, no blur. Used on previews and explicitly revealed values, never
  to fabricate streaming output or mask authorization state.
