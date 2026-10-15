"""Offline browser behavior for document cards and content-free inference traces."""
import json
from pathlib import Path
import shutil
import subprocess
from types import SimpleNamespace
import uuid

from django.test import SimpleTestCase
from django.template.loader import render_to_string
from django.urls import reverse


class AgentFrontendTests(SimpleTestCase):
    def test_restored_agent_omits_only_the_receipt_already_shown_in_its_panel(self):
        current, previous = uuid.uuid4(), uuid.uuid4()
        messages = [SimpleNamespace(role='user', content='Synthetic request',
                    request_record=SimpleNamespace(request_id=request_id, status='completed'))
                    for request_id in (previous, current)]
        rendered = render_to_string('chat/chat.html', {'messages': messages, 'agent_mode': True,
            'agent_available': True, 'agent_initial': {'id': 'run', 'request_id': str(current)}})
        previous_url = reverse('front:chat_request_receipt', args=[previous])
        current_url = reverse('front:chat_request_receipt', args=[current])
        self.assertIn(f'data-receipt-url="{previous_url}"', rendered)
        self.assertNotIn(f'data-receipt-url="{current_url}"', rendered)

    def browser(self, checks):
        source = (Path(__file__).resolve().parents[1] / 'static/js/agent-chat.js').read_text(encoding='utf-8')
        harness = r"""
const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
const source = JSON.parse(fs.readFileSync(0, 'utf8'));
class Element {
  constructor(tag = 'div') {
    this.tag = tag; this.children = []; this.textContent = ''; this.dataset = {}; this.attributes = {};
    this.style = {}; this.listeners = {}; this.hidden = false; this.disabled = false;
    this.classList = {toggle() {}, add() {}, remove() {}};
  }
  appendChild(child) { this.children.push(child); return child; }
  replaceChildren() { this.children = []; this.textContent = ''; }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  addEventListener(event, callback) { this.listeners[event] = callback; }
  after(child) { this.afterElement = child; }
  focus() { this.focused = true; }
  get text() { return this.textContent + this.children.map(child => child.text).join('\n'); }
  all(tag) { return this.children.flatMap(child => [...(child.tag === tag ? [child] : []), ...child.all(tag)]); }
}
const elements = Object.fromEntries(['agentProgress', 'agentFailure', 'agentEvents', 'agentState', 'agentActivity',
  'agentCancel', 'agentLimitations', 'agentSummary', 'agentTrace', 'agentArtifacts', 'agentExport',
  'agentRefresh', 'attachmentHint', 'fileInput', 'prompt', 'chatContainer', 'agent-initial',
  'conversationSidebar', 'conversationSidebarToggle', 'conversationMode'].map(id => [id, new Element()]));
elements['agent-initial'].textContent = 'null';
const readyHandlers = [], streams = [], responseQueue = [], requests = [];
let nextSnapshot = null;
class EventSource {
  constructor(url) { this.url = url; this.listeners = {}; streams.push(this); }
  addEventListener(name, callback) { this.listeners[name] = callback; }
  close() { this.closed = true; }
}
const fixture = {
  run: {id: 'run-a', status: 'completed', status_url: '/status/a', events_url: '/events/a', cancel_url: '/cancel/a'},
  result: {receipt: {policy: {status: 'allowed', reason_codes: ['local_policy_allowed']},
    jev: {status: 'not_consulted'}, calls: [], total: {cost: null}}},
  events: [], artifacts: [], current_revision: null, export_enabled: false,
};
const context = {document: {
  createElement: tag => new Element(tag), getElementById: id => elements[id] || null,
  querySelector: () => ({value: 'synthetic-csrf'}),
  addEventListener: (event, callback) => { if (event === 'DOMContentLoaded') readyHandlers.push(callback); },
}, window: {addEventListener() {}, matchMedia: () => ({matches: false})}, EventSource,
  Element, elements, streams, fixture, assert, requests,
  fetch: async (url, options) => { requests.push({url, options}); return responseQueue.length ? responseQueue.shift()(url) : {ok: true, json: async () => nextSnapshot || fixture}; },
  setSnapshot: value => {nextSnapshot = value;}, enqueueResponse: callback => responseQueue.push(callback),
  ready: () => readyHandlers.forEach(callback => callback()),
};
vm.createContext(context); vm.runInContext(source, context);
"""
        program = harness + '\nvm.runInContext(' + json.dumps('(async () => {' + checks + '})()') + ', context).catch(error => {console.error(error); process.exitCode = 1;});'
        result = subprocess.run([shutil.which('node'), '-e', program], input=json.dumps(source),
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_jev_states_do_not_turn_local_policy_into_jev_approval(self):
        self.browser(r"""
for (const [status, expected] of [['not_consulted', 'No consultado'], ['disabled', 'Deshabilitado'],
  ['failed', 'Falló'], ['no_response', 'Sin respuesta'], ['consulted', 'Consultado']]) {
  const output = new Element();
  window.regulayAgent.renderReceipt(output, {policy: {reason_codes: ['local_policy_allowed']},
    jev: {status, decision: {category: 'ordinary', task: 'report', difficulty: 'high'}, reasons: [],
      recommendations: [], applied: {sensitivity: 'ordinary', task: 'report', difficulty: 'high'},
      effect: 'continue', signals: {difficulty: {noul: 0.7}}, policy: {source: 'regulay_policy', revision: 3}}, calls: []});
  assert.match(output.text, new RegExp(expected));
  assert.match(output.text, /Jev no ha proporcionado motivos textuales/);
  assert.match(output.text, /Decisión aplicada por Regulay/);
  assert.match(output.text, /Una autorización local no es una aprobación de Jev/);
  assert.doesNotMatch(output.text, /Jev aprobado|Jev: Permitido|\[object Object\]/);
}
""")

    def test_full_call_sequence_preserves_requested_effective_fallback_and_unknown_cost(self):
        self.browser(r"""
const output = new Element();
window.regulayAgent.renderReceipt(output, {calls: [
  {sequence: 1, purpose: 'classification', provider_name: 'Jev gateway', model_requested: 'jev-requested',
   model_effective: 'jev-effective', route: {mode: 'policy', destination: 'gateway'}, fallback: {status: 'not_used'}, cost: null},
  {sequence: 2, purpose: 'generation', provider: 'synthetic', model_requested: 'requested-a', model_effective: 'effective-b',
   route: {mode: 'agent_profile', destination: 'engine:9'}, fallback: {status: 'used', reason: 'test fallback'},
   duration_ms: 42, cost: '0.0012', cost_kind: 'tariff_estimate', currency: 'USD'}]});
for (const value of ['jev-requested', 'jev-effective', 'requested-a', 'effective-b', 'engine:9', '42 ms', '0.0012 USD', 'Estimación con las tarifas configuradas']) assert.ok(output.text.includes(value), value);
assert.match(output.text, /Coste\nNo disponible/);
assert.match(output.text, /Sin fallback de Regulay/);
const sequence = output.all('details').find(item => item.text.includes('Secuencia de llamadas'));
assert.notEqual(sequence.open, true);
assert.equal(sequence.all('ol')[0].children.length, 2);
""")

    def test_primary_source_read_does_not_claim_an_inference_or_missing_model(self):
        self.browser(r"""
const output = new Element();
window.regulayAgent.renderReceipt(output, {calls: [{sequence: 1, purpose: 'research',
  provider_name: 'public_https', route: {mode: 'primary_source_read'},
  model_requested: null, model_effective: null, cost: '0', currency: 'USD', cost_kind: 'no_api_charge'}]});
assert.match(output.text, /Secuencia de llamadas · 1 llamada/);
assert.match(output.text, /Consulta de fuentes · Lectura sin modelo/);
assert.match(output.text, /Ruta\nConsulta de fuente primaria/);
assert.match(output.text, /Modelo solicitado\nLectura sin modelo/);
assert.match(output.text, /Modelo efectivo\nLectura sin modelo/);
assert.match(output.text, /Origen del coste\nSin cargo de API/);
assert.doesNotMatch(output.text, /Secuencia de inferencia|Modelo efectivo no disponible/);
""")

    def test_document_card_has_companion_downloads_and_separate_honest_checks(self):
        self.browser(r"""
const artifact = {id: 'aaaaaaaa-1111-2222-3333-bbbbbbbbbbbb', logical_id: 'logical-a', revision: 2, format: 'docx', status: 'verified',
  preview: {title: '<img src=x onerror=alert(1)> Informe largo', page_count: 5, pages: []},
  download_url: '/chat/agent/artifacts/aaaaaaaa-1111-2222-3333-bbbbbbbbbbbb/download/',
  downloads: [{format: 'DOCX', url: '/chat/agent/artifacts/aaaaaaaa-1111-2222-3333-bbbbbbbbbbbb/download/?format=docx'},
    {format: 'pdf', url: '/chat/agent/artifacts/aaaaaaaa-1111-2222-3333-bbbbbbbbbbbb/download/?format=pdf'},
    {format: 'pdf', url: 'https://outside.invalid/document'}, {format: 'pdf', url: 'javascript:alert(1)'}],
  verification_checks: {integrity: {status: 'passed', detail: 'Archivo abre'}, instructions: {status: 'failed', detail: 'No cumple el idioma'}}};
setSnapshot({...fixture, artifacts: [artifact], current_revision: artifact});
await window.regulayAgent.watch(fixture.run);
const card = elements.agentArtifacts;
assert.match(card.text, /5 páginas · Revisión 2/);
assert.equal(card.all('h3')[0].textContent, artifact.preview.title);
assert.equal(card.all('img').length, 0);
assert.equal(card.all('a').filter(link => link.attributes.download === '').length, 2);
assert.equal(card.all('a').filter(link => link.textContent === 'Descargar DOCX').length, 1);
assert.equal(card.all('a').filter(link => link.textContent === 'Descargar PDF').length, 1);
assert.match(card.text, /Integridad del archivo\nSuperada/);
assert.match(card.text, /Formato e instrucciones\nFallida/);
assert.equal((card.text.match(/No realizada/g) || []).length, 3);
assert.doesNotMatch(card.text, /Verificado y revisado|Fórmulas y totales verificados/);
assert.match(elements.agentSummary.text, /Coste\nNo disponible/);
""")

    def test_visual_review_requires_all_pages_and_only_confirms_visual_checks(self):
        self.browser(r"""
const base = '/chat/agent/artifacts/aaaaaaaa-1111-2222-3333-bbbbbbbbbbbb/';
const artifact = {id: 'aaaaaaaa-1111-2222-3333-bbbbbbbbbbbb', revision: 1, format: 'pdf', status: 'candidate',
  preview: {title: 'Informe', pages: [base + 'pages/1/', base + 'pages/2/']}, review_url: base + 'review/',
  sha256: 'safe-digest', page_sha256: ['a', 'b'], review_checks: ['legibility']};
setSnapshot({...fixture, run: {...fixture.run, status: 'active'}, artifacts: [artifact]});
await window.regulayAgent.watch(fixture.run);
const card = elements.agentArtifacts, control = card.all('button')[0], images = card.all('img');
assert.equal(control.disabled, true); images[0].onload(); assert.equal(control.disabled, true);
images[1].onload(); assert.equal(control.disabled, false);
assert.match(card.text, /únicamente la revisión visual/);
assert.equal(card.all('a').filter(link => link.attributes.download === '').length, 0);
await control.listeners.click();
const review = requests.find(request => request.url === base + 'review/');
assert.ok(review); assert.deepEqual(JSON.parse(review.options.body), {sha256: 'safe-digest', page_sha256: ['a', 'b'], checks: ['legibility']});
""")

    def test_terminal_error_is_visible_once_and_cleared_for_next_run(self):
        self.browser(r"""
const error = 'La investigación está deshabilitada. No se han consultado fuentes.';
setSnapshot({...fixture, run: {...fixture.run, status: 'failed'}, result: {...fixture.result, error},
  events: [{id: 1, data: {text: 'No se pudo completar el informe'}}]});
await window.regulayAgent.watch(fixture.run);
assert.equal(elements.agentFailure.textContent, error);
assert.equal(elements.agentFailure.hidden, false);
setSnapshot({...fixture, run: {...fixture.run, status: 'failed'}, result: {...fixture.result, error},
  events: [{id: 2, data: {text: error}}]});
await window.regulayAgent.watch(fixture.run);
assert.equal(elements.agentProgress.textContent, error);
assert.equal(elements.agentFailure.hidden, true);
setSnapshot({...fixture, run: {...fixture.run, id: 'run-b', status: 'active'}});
await window.regulayAgent.watch({...fixture.run, id: 'run-b'});
assert.equal(elements.agentFailure.hidden, true);
assert.equal(elements.agentFailure.textContent, '');
""")

    def test_summary_identifies_estimated_subtotal_without_claiming_complete_cost(self):
        self.browser(r"""
setSnapshot({...fixture, result: {receipt: {calls: [{model_effective: 'model-a', cost_kind: 'tariff_estimate'}],
  total: {cost: null, known_cost: '0.004', currency: 'USD'}}}});
await window.regulayAgent.watch(fixture.run);
assert.match(elements.agentSummary.text, /0\.004 USD conocido · incluye estimación · total no disponible/);
""")

    def test_stale_snapshot_cannot_replace_a_newer_run(self):
        self.browser(r"""
let resolveOld;
enqueueResponse(() => new Promise(resolve => {resolveOld = resolve;}));
const old = window.regulayAgent.watch(fixture.run);
await Promise.resolve();
setSnapshot({...fixture, run: {...fixture.run, id: 'run-b', status: 'cancelled'}, events: [{id: 2, data: {text: 'Nueva ejecución cancelada'}}]});
await window.regulayAgent.watch({...fixture.run, id: 'run-b'});
resolveOld({ok: true, json: async () => ({...fixture, events: [{id: 1, data: {text: 'Respuesta anterior'}}]})});
await old;
assert.equal(elements.agentState.textContent, 'Cancelado');
assert.equal(elements.agentProgress.textContent, 'Nueva ejecución cancelada');
assert.doesNotMatch(elements.agentEvents.text, /Respuesta anterior/);
""")

    def test_failed_old_request_does_not_clear_newer_run(self):
        self.browser(r"""
let rejectOld;
enqueueResponse(() => new Promise((resolve, reject) => {rejectOld = reject;}));
const old = window.regulayAgent.watch(fixture.run);
await Promise.resolve();
setSnapshot({...fixture, run: {...fixture.run, id: 'run-b', status: 'completed'}});
await window.regulayAgent.watch({...fixture.run, id: 'run-b'});
rejectOld(new Error('Old network failure'));
await old;
assert.equal(elements.agentState.textContent, 'Finalizado');
assert.ok(elements.agentSummary.children.length);
""")

    def test_real_events_are_deduplicated_and_unavailable_state_removes_private_projection(self):
        self.browser(r"""
setSnapshot({...fixture, run: {...fixture.run, status: 'active'}, events: [{id: 1, data: {text: 'Componiendo el informe'}}]});
await window.regulayAgent.watch(fixture.run);
const source = streams[0];
source.listeners.progress({data: JSON.stringify({id: 1, data: {text: 'Componiendo el informe'}})});
source.listeners.progress({data: JSON.stringify({id: 2, kind: 'progress', data: {text: 'Renderizando cinco páginas'}})});
assert.equal(elements.agentEvents.children.length, 2);
assert.equal(elements.agentProgress.textContent, 'Renderizando cinco páginas');
assert.doesNotMatch(elements.agentProgress.text, /Excel|fórmulas/);
source.listeners.revoked();
assert.equal(source.closed, true); assert.equal(elements.agentCancel.hidden, true);
assert.equal(elements.agentArtifacts.children.length, 0); assert.equal(elements.agentSummary.children.length, 0);
assert.equal(elements.agentState.textContent, 'Estado no disponible');
""")

    def test_conversation_sidebar_has_keyboard_button_and_matching_accessibility_state(self):
        self.browser(r"""
ready(); const control = elements.conversationSidebarToggle;
assert.equal(control.attributes['aria-expanded'], 'true');
control.listeners.click(); assert.equal(elements.conversationSidebar.hidden, true);
assert.equal(control.attributes['aria-expanded'], 'false');
assert.equal(control.textContent, 'Mostrar conversaciones');
control.listeners.click(); assert.equal(elements.conversationSidebar.hidden, false);
""")
