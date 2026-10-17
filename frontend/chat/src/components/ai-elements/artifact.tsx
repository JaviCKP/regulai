// Adapted from Vercel AI Elements Artifact (Apache-2.0).
// Local changes: only the used primitives; semantic title and regulAI tokens.
// Source and license: frontend/chat/THIRD_PARTY.md.
import type { HTMLAttributes } from "react"
import { cn } from "@/lib/utils"

export const Artifact = ({ className, ...props }: HTMLAttributes<HTMLDivElement>) => (
  <div data-slot="artifact" className={cn("flex min-w-0 flex-col overflow-hidden rounded-xl border border-border bg-background", className)} {...props} />
)

export const ArtifactHeader = ({ className, ...props }: HTMLAttributes<HTMLDivElement>) => (
  <div className={cn("flex items-center justify-between gap-3 border-b border-border bg-surface-2 px-4 py-3", className)} {...props} />
)

export const ArtifactTitle = ({ className, ...props }: HTMLAttributes<HTMLHeadingElement>) => (
  <h3 className={cn("text-sm font-medium text-foreground", className)} {...props} />
)

export const ArtifactContent = ({ className, ...props }: HTMLAttributes<HTMLDivElement>) => (
  <div className={cn("min-w-0 flex-1 overflow-auto p-4", className)} {...props} />
)

export const ArtifactActions = ({ className, ...props }: HTMLAttributes<HTMLDivElement>) => (
  <div className={cn("flex items-center gap-1", className)} {...props} />
)
