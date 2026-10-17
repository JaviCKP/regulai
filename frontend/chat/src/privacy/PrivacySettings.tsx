import { ArrowLeftIcon, CheckIcon, PlusIcon, ShieldCheckIcon, Trash2Icon } from "lucide-react"
import { useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { getJSON, postJSON, setCsrfToken } from "../transport/http"
import { PreviewBox, PrivacyDetails, type PreviewPart } from "./PrivacyPanel"

type Treatment = "off" | "reversible" | "irreversible"
type Literal = { text: string; category: string; treatment: "reversible" | "irreversible" }
type Yara = { rule_id: number; source_hash: string; strings: string[]; treatment: "reversible" | "irreversible" }
type Config = { version: 1; categories: Record<string, Treatment>; literals: Literal[]; yara: Yara[] }
type Rule = { rule_id: number; name: string; source_hash: string; strings: string[]; reason: string | null; action: string }
type Review = { current: string; protected: string; current_segments?: PreviewPart[]; protected_segments?: PreviewPart[]; revision_id: number; review_token: string; coverage: string; decision: { policy?: { status?: string } } }
const categories = [["EMAIL", "Correos electrónicos"], ["PHONE", "Teléfonos"], ["ID", "Documentos de identidad"], ["ACCOUNT", "Cuentas bancarias"], ["CARD", "Tarjetas"], ["PERSON", "Nombres en campos etiquetados"], ["FIELD", "Campos estructurados seleccionados"]]
const shortLabels: Record<string, string> = { PERSON: "Nombres etiquetados", FIELD: "Campos elegidos", ID: "Documentos" }
const endpoint = "/settings/privacy/configuration/"
const selectClass = "h-11 max-w-full rounded-lg border-0 bg-surface-2 pl-3 pr-7 text-xs text-muted-foreground focus-visible:outline-2 focus-visible:outline-ring"

export function PrivacySettings({ csrfToken }: { csrfToken: string }) {
  const [config, setConfig] = useState<Config | null>(null)
  const [rules, setRules] = useState<Rule[]>([])
  const [enabled, setEnabled] = useState(false)
  const [coverage, setCoverage] = useState("")
  const [sample, setSample] = useState("Ana Fixture escribe a ana@example.invalid. Ana Fixture necesita revisar el proyecto ficticio.")
  const [synthetic, setSynthetic] = useState(false)
  const [review, setReview] = useState<Review | null>(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState("")
  const [error, setError] = useState("")
  useEffect(() => {
    setCsrfToken(csrfToken)
    const controller = new AbortController()
    getJSON<{ configuration: Config; rules: Rule[]; enabled: boolean; coverage: string }>(endpoint, controller.signal)
      .then(({ data }) => { setConfig(data.configuration); setRules(data.rules); setEnabled(data.enabled); setCoverage(data.coverage) })
      .catch(() => { if (!controller.signal.aborted) setError("No se pudo cargar la configuración con tus permisos actuales.") })
    return () => controller.abort()
  }, [csrfToken])
  const change = (next: Config) => { setConfig(next); setReview(null); setMessage(""); setError("") }
  const test = async () => {
    setBusy(true); setError(""); setMessage(""); setReview(null)
    try { setReview(await postJSON<Review>(endpoint, { action: "simulate", configuration: config, sample, synthetic })) }
    catch { setError("No se pudo probar. Revisa el texto y las reglas seleccionadas.") }
    finally { setBusy(false) }
  }
  const activate = async () => {
    if (!review) return
    setBusy(true); setError("")
    try { await postJSON(endpoint, { action: "activate", revision_id: review.revision_id, review_token: review.review_token }); setEnabled(true); setReview(null); setMessage("Configuración activada.") }
    catch { setError("La revisión caducó o cambió la política. Prueba de nuevo antes de activar."); setReview(null) }
    finally { setBusy(false) }
  }
  return <main className="h-full overflow-y-auto bg-background text-foreground">
    <div className="mx-auto max-w-3xl px-5 py-6 sm:px-10 sm:py-10">
      <a href="/settings/company/" className="inline-flex min-h-11 items-center gap-2 rounded-md text-sm text-muted-foreground focus-visible:outline-2 focus-visible:outline-ring"><ArrowLeftIcon className="size-4" />Configuración de empresa</a>
      <div className="mb-10 mt-7 flex flex-wrap items-center justify-between gap-4"><h1 className="text-2xl font-semibold tracking-tight">Datos protegidos</h1>
        <span className="flex items-center gap-2 text-xs text-muted-foreground"><span className={`size-1.5 rounded-full ${enabled ? "bg-brand-strong" : "bg-muted-foreground"}`} />{enabled ? "Activa" : "Desactivada"}</span></div>
      {error && <p role="alert" className="mb-5 rounded-xl bg-danger-soft p-4 text-sm text-danger">{error}</p>}
      {message && <p role="status" className="mb-5 flex gap-2 rounded-xl bg-brand-soft p-4 text-sm"><CheckIcon className="size-5" />{message}</p>}
      {!config && !error && <p role="status">Cargando configuración…</p>}
      {config && <div className="flex flex-col gap-8">
        <section><h2 className="mb-3 text-sm font-medium">Categorías</h2>
          <div className="divide-y divide-border">{categories.map(([key, label]) => <label key={key} className="flex flex-wrap items-center justify-between gap-3 py-3"><span className="text-sm">{shortLabels[key!] ?? label}</span><select aria-label={label} value={config.categories[key!] ?? "off"} className={selectClass} onChange={event => change({ ...config, categories: { ...config.categories, [key!]: event.target.value as Treatment } })}>
            <option value="off">No añadir</option><option value="reversible">Recuperable</option><option value="irreversible">Irreversible</option>
          </select></label>)}</div>
          <PrivacyDetails label="Sobre la detección"><p>Recuperable: la persona autorizada ve el original en su chat. Irreversible: se oculta sin guardar correspondencia. No añadir: conserva la protección D2 existente.</p><p>Las contraseñas y claves nunca son recuperables. Los nombres en prosa libre requieren un texto exacto.</p><p>{coverage}</p></PrivacyDetails>
        </section>
        <section className="border-t border-border pt-7"><h2 className="mb-4 text-sm font-medium">Textos exactos</h2>
          <div className="flex flex-col gap-3">{config.literals.map((literal, index) => <div key={index} className="flex flex-wrap gap-2">
            <Input className="h-11 min-w-0 flex-1 basis-48" aria-label={`Texto exacto ${index + 1}`} value={literal.text} maxLength={512} onChange={event => change({ ...config, literals: config.literals.map((item, position) => position === index ? { ...item, text: event.target.value } : item) })} />
            <select className={selectClass} aria-label={`Tratamiento del texto ${index + 1}`} value={literal.treatment} onChange={event => change({ ...config, literals: config.literals.map((item, position) => position === index ? { ...item, treatment: event.target.value as Literal["treatment"] } : item) })}><option value="reversible">Recuperable</option><option value="irreversible">Irreversible</option></select>
            <Button variant="ghost" size="icon" className="size-11" aria-label={`Eliminar texto ${index + 1}`} onClick={() => change({ ...config, literals: config.literals.filter((_, position) => position !== index) })}><Trash2Icon /></Button>
          </div>)}</div>
          <Button className="mt-2 min-h-11 px-0 text-xs text-muted-foreground" variant="ghost" disabled={config.literals.length >= 128} onClick={() => change({ ...config, literals: [...config.literals, { text: "", category: "FIELD", treatment: "reversible" }] })}><PlusIcon />Añadir texto</Button>
        </section>
        <section className="border-t border-border pt-2"><PrivacyDetails label="Reglas avanzadas · YARA"><p>Solo cadenas con posiciones verificables. Se conservan sus acciones de bloqueo o consentimiento.</p>
          {!rules.length && <p className="text-sm text-subtle-foreground">No hay reglas de empresa para seleccionar.</p>}
          {rules.map(rule => <fieldset key={rule.rule_id} className="mb-3 rounded-lg bg-surface-2 p-4"><legend className="text-sm font-medium">{rule.name} · {rule.action === "block" ? "Bloqueo" : "Consentimiento"}</legend>
            {rule.reason ? <p className="text-xs text-subtle-foreground">{rule.reason}</p> : rule.strings.map(string => <label key={string} className="flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" className="size-5 accent-current" checked={config.yara.some(item => item.rule_id === rule.rule_id && item.strings.includes(string))} onChange={event => {
              const entry = config.yara.find(item => item.rule_id === rule.rule_id) ?? { rule_id: rule.rule_id, source_hash: rule.source_hash, strings: [], treatment: "reversible" as const }
              const strings = event.target.checked ? [...entry.strings, string] : entry.strings.filter(item => item !== string)
              change({ ...config, yara: [...config.yara.filter(item => item.rule_id !== rule.rule_id), ...(strings.length ? [{ ...entry, strings }] : [])] })
            }} />{string}</label>)}
            {config.yara.some(item => item.rule_id === rule.rule_id) && <select className={selectClass} aria-label={`Tratamiento de ${rule.name}`} value={config.yara.find(item => item.rule_id === rule.rule_id)?.treatment} onChange={event => change({ ...config, yara: config.yara.map(item => item.rule_id === rule.rule_id ? { ...item, treatment: event.target.value as Yara["treatment"] } : item) })}><option value="reversible">Recuperable en el chat</option><option value="irreversible">Ocultar sin correspondencia</option></select>}
          </fieldset>)}
        </PrivacyDetails></section>
        <section className="border-t border-border pt-7"><h2 className="mb-4 text-sm font-medium">Prueba antes de activar</h2><label className="sr-only" htmlFor="privacy-sample">Texto ficticio para comprobar coincidencias</label><Textarea id="privacy-sample" className="min-h-28 resize-y rounded-xl bg-surface-2 text-sm" value={sample} maxLength={16000} onChange={event => { setSample(event.target.value); setReview(null) }} />
          <div className="mt-3 flex flex-wrap items-center justify-between gap-3"><label className="flex min-h-11 items-center gap-2 text-xs text-muted-foreground"><input type="checkbox" className="size-4 accent-current" checked={synthetic} onChange={event => { setSynthetic(event.target.checked); setReview(null) }} />Confirmo que este texto es ficticio.</label>
          <Button className="min-h-11" variant="outline" disabled={!synthetic || !sample.trim() || busy} onClick={test}>{busy ? "Comprobando…" : "Probar borrador"}</Button></div>
          {review && <div className="mt-6 flex flex-col gap-4"><h3 className="sr-only">Diferencias revisadas</h3><div className="grid gap-3 md:grid-cols-2"><PreviewBox title="Ahora" text={review.current} parts={review.current_segments} /><PreviewBox title="Con el cambio" text={review.protected} parts={review.protected_segments} /></div>
            {review.decision.policy?.status === "block" && <p className="text-sm text-danger">La política bloquea este ejemplo.</p>}
            {review.decision.policy?.status === "consent_required" && <p className="text-sm text-muted-foreground">Este ejemplo requiere consentimiento.</p>}
            <div className="flex flex-wrap items-start justify-between gap-3"><PrivacyDetails label="Detalles de la prueba"><p>{review.coverage}</p><p>La prueba usa solo este ejemplo. Los bloqueos se conservan.</p><code className="block max-h-40 overflow-auto whitespace-pre-wrap break-all">{review.protected}</code></PrivacyDetails><Button className="min-h-11" disabled={busy} onClick={activate}><ShieldCheckIcon />Activar cambios</Button></div></div>}
        </section>
        <div className="pb-8" />
      </div>}
    </div>
  </main>
}
