import { getJSON } from "../transport/http"
import type { RequestResult } from "../types"
import { CopyButton } from "../turn/parts"
import { DownloadIcon, ShieldCheckIcon } from "lucide-react"
import { Button } from "@/components/ui/button"
import { DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem } from "@/components/ui/dropdown-menu"
import { useSession } from "../app/session-context"
import { ArtifactActions } from "@/components/ai-elements/artifact"

/** Reauthorize at copy time, including a tab left open after revocation. */
export function PrivacyCopies({ requestId, role = "assistant" }: { requestId: string; role?: "user" | "assistant" }) {
  const session = useSession()
  const value = async (protectedVersion: boolean) => {
    const { data } = await getJSON<RequestResult>(`/chat/privacy/requests/${encodeURIComponent(requestId)}/`)
    const message = role === "user" ? data.user_message : data.assistant_message
    if (!message || data.error_type === "privacy_access_revoked") throw new Error("revoked")
    return protectedVersion ? message.protected_copy ?? "" : message.projection?.text ?? message.content ?? ""
  }
  const download = async (protectedVersion: boolean) => {
    try {
      const text = await value(protectedVersion)
      const url = URL.createObjectURL(new Blob([text], { type: "text/plain;charset=utf-8" }))
      const link = document.createElement("a")
      link.href = url; link.download = `mensaje-${protectedVersion ? "protegido" : "natural"}.txt`
      link.click(); window.setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch { session.toast("La descarga ya no está autorizada. Actualiza la conversación.", true) }
  }
  return <ArtifactActions>
    <CopyButton label="Copiar texto natural" text={() => value(false)} />
    <CopyButton label="Copiar versión protegida · Datos detectados sustituidos" icon={ShieldCheckIcon} text={() => value(true)} />
    <DropdownMenu><DropdownMenuTrigger render={<Button variant="ghost" size="icon" className="size-11 text-muted-foreground" aria-label="Descargar mensaje" />}><DownloadIcon /></DropdownMenuTrigger><DropdownMenuContent align="end">
      <DropdownMenuItem className="min-h-11" onClick={() => void download(false)}>Descargar texto natural</DropdownMenuItem>
      <DropdownMenuItem className="min-h-11" onClick={() => void download(true)}>Descargar versión protegida</DropdownMenuItem>
    </DropdownMenuContent></DropdownMenu>
  </ArtifactActions>
}
