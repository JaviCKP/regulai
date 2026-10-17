import { getJSON } from "../transport/http"
import type { RequestResult } from "../types"
import { CopyButton } from "../turn/parts"

/** Reauthorize at copy time, including a tab left open after revocation. */
export function PrivacyCopies({ requestId, role = "assistant" }: { requestId: string; role?: "user" | "assistant" }) {
  const value = async (protectedVersion: boolean) => {
    const { data } = await getJSON<RequestResult>(`/chat/privacy/requests/${encodeURIComponent(requestId)}/`)
    const message = role === "user" ? data.user_message : data.assistant_message
    if (!message || data.error_type === "privacy_access_revoked") throw new Error("revoked")
    return protectedVersion ? message.protected_copy ?? "" : message.projection?.text ?? message.content ?? ""
  }
  return <div className="flex items-center gap-1">
    <CopyButton label="Copiar texto natural" text={() => value(false)} />
    <CopyButton label="Copiar versión protegida · Datos detectados sustituidos" text={() => value(true)} />
  </div>
}
