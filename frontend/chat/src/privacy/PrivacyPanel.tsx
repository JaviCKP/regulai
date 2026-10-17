import { MoreHorizontalIcon, ShieldCheckIcon, EyeIcon, EyeOffIcon, LockKeyholeIcon, ChevronDownIcon, CopyIcon } from "lucide-react"
import { useEffect, useRef, useState, type ReactNode } from "react"
import { Button } from "@/components/ui/button"
import { DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem } from "@/components/ui/dropdown-menu"
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui/sheet"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog"
import { useChat, useSession } from "../app/session-context"
import { getJSON, postJSON } from "../transport/http"
import { Artifact, ArtifactContent, ArtifactHeader, ArtifactTitle } from "@/components/ai-elements/artifact"
import FadeContent from "@/components/react-bits/FadeContent"
import type { RequestResult } from "../types"

type Alias = { id: number; token: string; category: string; occurrences: number; uses: number; calls: number; locations: { request_id: string; detector: string; revision_id: number; count: number; first: string; last: string }[]; turns: { request_id: string; input: number; history: number; context: number; response: number; provider_calls: number; uncertain_calls: number }[]; original: string | null }
type Inspector = { enabled: boolean; revision_id: number | null; totals: { values: number; occurrences: number }; coverage: string; aliases: Alias[]; irreversible: { category: string; count: number }[]; next: number | null; counts_note: string }
export type PreviewPart = { text: string; selected?: boolean; label?: string }
type Preview = { protected: string; count: number; coverage: string; notice?: string; review_token?: string; policy_status?: string; source_segments?: PreviewPart[]; protected_segments?: PreviewPart[] }
const category: Record<string, string> = { EMAIL: "Correo", PHONE: "Teléfono", PERSON: "Nombre", ID: "Documento", ACCOUNT: "Cuenta", CARD: "Tarjeta", FIELD: "Texto seleccionado", SECRET: "Secreto" }
const base = (id: number) => `/chat/privacy/conversations/${id}/`
const errorText = "No se pudo cargar. Vuelve a intentarlo."

export function PrivacyDetails({ children, label = "Más información" }: { children: ReactNode; label?: string }) {
  return <details className="group text-xs text-muted-foreground"><summary className="flex min-h-11 w-fit cursor-pointer list-none items-center gap-1.5 rounded-md focus-visible:outline-2 focus-visible:outline-ring">{label}<ChevronDownIcon className="size-3.5 transition-transform group-open:rotate-180" /></summary><div className="space-y-3 pb-3 leading-relaxed">{children}</div></details>
}

export function PrivacyMenu() {
  const session = useSession()
  const id = useChat(state => state.conversationId)
  const trigger = useRef<HTMLButtonElement>(null)
  const [open, setOpen] = useState(false)
  const [data, setData] = useState<Inspector | null>(null)
  const [error, setError] = useState("")
  const [revealing, setRevealing] = useState<number | null>(null)
  useEffect(() => {
    if (!open || !id) { setData(null); return }
    const controller = new AbortController()
    setError("")
    getJSON<Inspector>(base(id) + "inspector/", controller.signal).then(({ data }) => setData(data)).catch(() => {
      if (!controller.signal.aborted) setError(errorText)
    })
    return () => controller.abort()
  }, [open, id])
  const reveal = async (row: Alias) => {
    if (!id || revealing !== null) return
    if (row.original !== null) {
      setData(value => value && ({ ...value, aliases: value.aliases.map(item => item.id === row.id ? { ...item, original: null } : item) }))
      return
    }
    setRevealing(row.id)
    try {
      const result = await postJSON<{ aliases: Alias[] }>(base(id) + "reveal/", { ids: [row.id] })
      const original = result.aliases[0]?.original ?? "Original ya no disponible"
      setData(value => value && ({ ...value, aliases: value.aliases.map(item => item.id === row.id ? { ...item, original } : item) }))
    } catch { setError(errorText) } finally { setRevealing(null) }
  }
  const more = async () => {
    if (!id || !data?.next) return
    try { const result = await getJSON<Inspector>(base(id) + `inspector/?after=${data.next}`)
      setData({ ...result.data, aliases: [...data.aliases, ...result.data.aliases] })
    } catch { setError(errorText) }
  }
  const showMessage = async (row: Alias, requestId: string) => {
    try {
      const { data } = await getJSON<RequestResult>(`/chat/privacy/requests/${encodeURIComponent(requestId)}/`)
      if (data.error_type === "privacy_access_revoked") throw new Error("revoked")
      const article = document.querySelector<HTMLElement>(`[data-turn][data-request-id="${CSS.escape(requestId)}"]`)
      if (!article) throw new Error("unavailable")
      let target: HTMLElement = article
      for (const role of ["user", "assistant"] as const) {
        const message = role === "user" ? data.user_message : data.assistant_message
        const bytes = new TextEncoder().encode(message?.content ?? "")
        const part = message?.projection?.segments.find(part => part.kind === "original" && new TextDecoder().decode(bytes.slice(part.start, part.end)) === row.token)
        if (part) {
          target = article.querySelector<HTMLElement>(`${role === "user" ? "[data-privacy-user]" : ".rg-md"} [data-privacy-start="${part.start}"][data-privacy-end="${part.end}"]`) ?? article
          break
        }
      }
      setOpen(false)
      window.setTimeout(() => {
        target.scrollIntoView({ block: "center", behavior: "instant" })
        target.tabIndex = -1
        target.focus({ preventScroll: true })
        target.classList.add("bg-brand-soft", "rounded-sm")
        window.setTimeout(() => { target.classList.remove("bg-brand-soft", "rounded-sm"); target.removeAttribute("tabindex") }, 2400)
      }, 250)
    } catch { setError("Este mensaje ya no está disponible.") }
  }
  return <>
    <DropdownMenu><DropdownMenuTrigger render={<Button ref={trigger} variant="ghost" size="icon" className="size-11" aria-label="Más opciones de conversación" />}><MoreHorizontalIcon /></DropdownMenuTrigger>
      <DropdownMenuContent align="end"><DropdownMenuItem disabled={!id} onClick={() => setOpen(true)} className="min-h-11" aria-label="Privacidad de esta conversación"><ShieldCheckIcon />Privacidad</DropdownMenuItem>
        {session.boot.setup.can_manage && <DropdownMenuItem render={<a href="/settings/privacy/" />} className="min-h-11"><LockKeyholeIcon />Datos protegidos</DropdownMenuItem>}
      </DropdownMenuContent>
    </DropdownMenu>
    <Sheet open={open} onOpenChange={setOpen}><SheetContent finalFocus={trigger} className="w-full! max-w-md! overflow-y-auto pb-6 [&_[data-slot=sheet-close]]:size-11">
      <SheetHeader className="px-6 pb-5 pr-14 pt-7"><SheetTitle>Privacidad</SheetTitle><SheetDescription className="sr-only">Datos protegidos de esta conversación.</SheetDescription></SheetHeader>
      <div className="flex flex-col px-6">
        {error && <p role="alert" className="text-danger">{error}</p>}
        {!data && !error && <p role="status" className="py-8 text-sm text-muted-foreground">Cargando…</p>}
        {data && <>
          <div className="mb-3 flex items-center gap-2 text-xs text-muted-foreground"><span className={`size-1.5 rounded-full ${data.enabled ? "bg-brand-strong" : "bg-muted-foreground"}`} />{data.enabled ? "Protección activa" : "Protección desactivada"}</div>
          {!!data.totals.values && <p className="mb-5 text-xs text-subtle-foreground">{data.totals.values} valores · {data.totals.occurrences} apariciones</p>}
          {!data.aliases.length && <div className="py-16 text-center text-sm text-muted-foreground"><ShieldCheckIcon className="mx-auto mb-3 size-6 opacity-40" />Aún no hay datos protegidos.</div>}
          <ul className="divide-y divide-border">{data.aliases.map((row, index) => <li key={row.id} className="min-w-0 py-4">
            <div className="flex items-center gap-3"><div className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-surface-2 text-muted-foreground"><LockKeyholeIcon className="size-4" /></div><div className="min-w-0 flex-1"><p className="text-sm font-medium">{category[row.category] ?? row.category} <span className="ml-1 text-xs font-normal text-subtle-foreground">{index + 1}</span></p><p className="mt-0.5 text-xs text-subtle-foreground">{row.occurrences} apariciones · {row.uses} usos</p></div>
              <Button variant="ghost" className="min-h-11 px-3 text-xs text-muted-foreground" aria-label={row.original === null ? "Revelar original" : "Ocultar original"} aria-busy={revealing === row.id} aria-disabled={revealing !== null || !data.enabled} onClick={() => { if (data.enabled) void reveal(row) }}>{row.original === null ? <EyeIcon /> : <EyeOffIcon />}{row.original === null ? "Ver" : "Ocultar"}</Button></div>
            {row.original !== null && <FadeContent><p className="mt-3 whitespace-pre-wrap break-words rounded-lg bg-surface-2 px-3 py-2.5 text-sm" style={{ overflowWrap: "anywhere" }} data-privacy-original="">{row.original}</p></FadeContent>}
            <PrivacyDetails label="Detalles"><div className="flex items-center gap-2"><code className="min-w-0 flex-1 break-all">{row.token}</code><Button variant="ghost" size="icon" className="size-11 shrink-0" aria-label="Copiar identificador" onClick={() => void navigator.clipboard.writeText(row.token).then(() => session.toast("Identificador copiado.")).catch(() => setError("No se pudo copiar."))}><CopyIcon /></Button></div>
              {row.locations?.map((location, position) => <div key={`${location.request_id}-${position}`} className="flex flex-wrap items-center justify-between gap-2"><span>{location.count} apariciones · {location.detector} · rev. {location.revision_id}<br /><time dateTime={location.first}>{new Date(location.first).toLocaleString("es-ES")}</time>{location.last !== location.first && <> — <time dateTime={location.last}>{new Date(location.last).toLocaleString("es-ES")}</time></>}</span><Button variant="ghost" className="min-h-11 text-xs" onClick={() => void showMessage(row, location.request_id)}>Ver mensaje</Button></div>)}
              {row.turns?.map(turn => <div key={turn.request_id} className="border-t border-border pt-3"><div className="flex items-center justify-between gap-2"><span>{turn.provider_calls} llamadas al proveedor{turn.uncertain_calls > 0 && ` · ${turn.uncertain_calls} sin confirmar`}</span><Button variant="ghost" className="min-h-11 text-xs" onClick={() => void showMessage(row, turn.request_id)}>Ver mensaje</Button></div><dl className="grid grid-cols-2 gap-x-6 gap-y-1">{([["Entrada", turn.input], ["Historial reenviado", turn.history], ["Otros usos de salida", turn.context], ["Respuesta guardada", turn.response]] as const).map(([label, value]) => <div key={label} className="flex justify-between gap-2"><dt>{label}</dt><dd>{value}</dd></div>)}</dl></div>)}
            </PrivacyDetails>
          </li>)}</ul>
          {data.next && <Button variant="outline" className="min-h-11" onClick={more}>Cargar más</Button>}
          {!!data.irreversible.length && <div className="mt-5 border-t border-border pt-4"><PrivacyDetails label="Datos no recuperables"><ul>{data.irreversible.map(row => <li key={row.category}>{category[row.category] ?? row.category}: {row.count}</li>)}</ul></PrivacyDetails></div>}
          <div className="mt-6 border-t border-border pt-2"><PrivacyDetails label="Cobertura y conservación"><p>{data.revision_id ? `Política actual: revisión ${data.revision_id}. ` : ""}{data.coverage}</p><p>{data.counts_note} La entrada y el historial cuentan cada llamada; la respuesta, solo el mensaje guardado.</p><p>Recuperar un dato no verifica las afirmaciones de la IA. Al eliminar el chat se eliminan sus correspondencias. Las copias de seguridad siguen la retención de la instalación.</p></PrivacyDetails></div>
        </>}
      </div>
    </SheetContent></Sheet>
  </>
}

export function PrivacyPreview({ text }: { text: string }) {
  const id = useChat(state => state.conversationId)
  const trigger = useRef<HTMLButtonElement>(null)
  const [open, setOpen] = useState(false)
  const [data, setData] = useState<Preview | null>(null)
  const [error, setError] = useState("")
  useEffect(() => {
    setData(null); setError("")
    if (!open) return
    const controller = new AbortController()
    postJSON<Preview>(id ? base(id) + "preview/" : "/chat/privacy/preview/", { text }, controller.signal)
      .then(setData).catch(() => { if (!controller.signal.aborted) setError(errorText) })
    return () => controller.abort()
  }, [open, id, text])
  return <>
    <Button ref={trigger} type="button" variant="ghost" size="icon" className="size-11 text-muted-foreground" disabled={!text.trim()} aria-label="Ver lo que recibirá la IA" onClick={() => setOpen(true)}><ShieldCheckIcon /></Button>
    <Dialog open={open} onOpenChange={setOpen}><DialogContent finalFocus={trigger} className="gap-5 sm:max-w-2xl! max-h-[85dvh] overflow-y-auto [&_[data-slot=dialog-close]]:size-11">
      <DialogHeader className="pr-10"><DialogTitle>Vista para la IA</DialogTitle><DialogDescription className="text-xs">Solo este mensaje</DialogDescription></DialogHeader>
      {error && <p role="alert" className="text-danger">{error}</p>}
      {!data && !error && <p role="status" className="py-8 text-sm text-muted-foreground">Preparando vista…</p>}
      {data && <><div className="grid gap-3 md:grid-cols-2">
        <PreviewBox title="Tu texto" text={text} parts={data.source_segments} /><PreviewBox title="Texto protegido" text={data.protected} parts={data.protected_segments} /></div>
        {data.policy_status === "block" && <p role="status" className="text-sm text-danger">La política bloquea este envío.</p>}
        {data.policy_status === "consent_required" && <p role="status" className="text-sm">Este envío requiere consentimiento.</p>}
        <div className="flex flex-wrap items-start justify-between gap-x-4 border-t border-border pt-1"><span className="flex min-h-11 items-center gap-2 text-xs text-muted-foreground"><ShieldCheckIcon className="size-3.5" />{data.count === 1 ? "1 coincidencia" : `${data.count} coincidencias`}</span><PrivacyDetails label="Detalles"><p>{data.notice}</p><p>{data.coverage}</p><p>Las etiquetas abrevian los identificadores de esta vista previa.</p><code className="block max-h-40 overflow-auto whitespace-pre-wrap break-all">{data.protected}</code></PrivacyDetails></div></>}
    </DialogContent></Dialog>
  </>
}

export function PreviewBox({ title, text, parts }: { title: string; text: string; parts?: PreviewPart[] }) {
  return <FadeContent className="min-w-0"><Artifact className="h-full rounded-xl border-0 bg-surface-2 shadow-none"><ArtifactHeader className="border-0 px-4 pb-2 pt-4"><ArtifactTitle className="text-xs font-medium text-muted-foreground">{title}</ArtifactTitle></ArtifactHeader><ArtifactContent className="max-h-64 overflow-y-auto px-4 pb-4 pt-1"><p className="whitespace-pre-wrap break-words text-sm leading-7" style={{ overflowWrap: "anywhere" }}>{parts ? parts.map((part, index) => part.selected ? <mark key={index} title={part.label ? part.text : undefined} className={part.label ? "mx-0.5 inline rounded-md bg-brand-soft px-1.5 py-0.5 text-xs font-medium text-brand-strong" : "rounded-sm bg-brand-soft text-inherit"}>{part.label ?? part.text}</mark> : part.text) : text}</p></ArtifactContent></Artifact></FadeContent>
}

export function PrivacySelection() {
  const session = useSession()
  const id = useChat(state => state.conversationId)
  const busy = useChat(state => Boolean(state.busy.owner) || state.sending)
  const trigger = useRef<HTMLButtonElement>(null)
  const [selected, setSelected] = useState("")
  const [text, setText] = useState("")
  const [open, setOpen] = useState(false)
  const [data, setData] = useState<Preview | null>(null)
  const [error, setError] = useState("")
  useEffect(() => {
    const update = () => {
      if (open) return
      const selection = window.getSelection()
      const node = selection?.anchorNode?.parentElement
      const input = document.activeElement
      const value = input instanceof HTMLTextAreaElement && input.id === "regulai-prompt"
        ? input.value.slice(input.selectionStart, input.selectionEnd)
        : node?.closest("[data-turn]") ? selection?.toString() ?? "" : ""
      setSelected(value.trim() && value.length <= 512 ? value : "")
    }
    document.addEventListener("selectionchange", update)
    return () => document.removeEventListener("selectionchange", update)
  }, [open])
  useEffect(() => {
    if (!open || !id) return
    setData(null); setError("")
    const controller = new AbortController()
    postJSON<Preview>(base(id) + "selection/", { text }, controller.signal).then(setData)
      .catch(() => { if (!controller.signal.aborted) setError(errorText) })
    return () => controller.abort()
  }, [open, id, text])
  const save = async () => {
    if (!id || !data?.review_token) return
    try { await postJSON(base(id) + "selection/", { text, review_token: data.review_token }); setOpen(false); session.toast("Protección guardada.") }
    catch { setError("La revisión cambió. Cierra y vuelve a comprobar la selección.") }
  }
  if (!session.boot.privacy?.enabled || !id) return null
  return <>
    {(selected || open) && <Button ref={trigger} variant="outline" className="fixed bottom-36 left-1/2 z-30 min-h-11 max-w-[90vw] -translate-x-1/2 rounded-full bg-background px-5 shadow-sm" aria-label="Proteger siempre este texto en este chat" disabled={busy} onPointerDown={event => event.preventDefault()} onClick={() => { setText(selected); setOpen(true) }}><LockKeyholeIcon />Proteger texto</Button>}
    <Dialog open={open} onOpenChange={setOpen}><DialogContent finalFocus={trigger} className="gap-5 sm:max-w-md! max-h-[85dvh] overflow-y-auto"><DialogHeader className="pr-10"><DialogTitle>Proteger texto</DialogTitle><DialogDescription className="text-xs">Solo en este chat</DialogDescription></DialogHeader>
      <PreviewBox title="Selección" text={text} />{data && <PreviewBox title="La IA recibirá" text={data.protected} parts={data.protected_segments} />}{error && <p role="alert" className="text-danger">{error}</p>}
      <PrivacyDetails label="Cómo se aplica"><p>Coincidencia exacta en futuros envíos y en el historial reenviado. No retira datos ya enviados.</p></PrivacyDetails>
      <Button className="min-h-11" disabled={!data || !!error || busy} onClick={save}>Proteger en este chat</Button>
    </DialogContent></Dialog>
  </>
}
