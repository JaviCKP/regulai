"""Run rendered chat JavaScript with an offline DOM and synthetic server replies."""
import json
import re
import shutil
import subprocess

from front.test_chat_flow import ChatFixture
from front import test_pipeline, test_pipeline_privacy
from front.models import EngineModel


class ChatUiTests(ChatFixture):
    def browser(self, checks, path='/chat/'):
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        source = next(script for script in re.findall(r'<script\b[^>]*>(.*?)</script>',
            response.content.decode(), re.S) if 'async function sendMessage' in script)
        harness = r"""
const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
const source = JSON.parse(fs.readFileSync(0, 'utf8'));
class Element {
  constructor(tag = 'div') {this.tag = tag; this.children = []; this.textContent = ''; this.classList = {toggle() {}};}
  appendChild(child) {this.children.push(child); return child;}
  replaceChildren() {this.children = []; this.textContent = '';}
  querySelector(selector) {return selector === '.message-role' ? this : null;}
  remove() {}
  addEventListener(event, callback) {this[event] = callback;}
  get text() {return this.textContent + this.children.map(child => child.text).join('\n');}
}
const container = new Element();
const context = {document: {addEventListener() {}, createElement: tag => new Element(tag),
  getElementById: id => id === 'chatContainer' ? container : null}, Element, container, assert};
vm.createContext(context);
vm.runInContext(source, context);
vm.runInContext('createAssistantBubble = () => new Element(); createSystemBubble = value => {const e = new Element(); e.textContent = value; return e;};', context);
"""
        result = subprocess.run([shutil.which('node'), '-e', harness + '\nvm.runInContext(' + json.dumps(checks) + ', context);'],
                                input=json.dumps(source), text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_html_quotes_cannot_escape_download_attributes(self):
        self.browser("assert.equal(escapeHtml(`<&>\"'`), '&lt;&amp;&gt;&quot;&#39;');")

    def test_escalated_destination_survives_send_export_and_history_restore(self):
        test_pipeline.PipelineTests.configure(self)
        first = self.send('/api/chat/send/', 'Previous synthetic turn').json()
        self.assertEqual(first['status'], 'completed')
        other = test_pipeline_privacy.PipelinePrivacyTests.fallback(self, cross_engine=True, allow=True)
        EngineModel.objects.filter(engine=other.engine).update(model_id=self.model.model_id)
        self.http.side_effect = test_pipeline.jev_http(failures={'failure_contradiction': 1})
        history_path = '/chat/' + str(first['conversation_id']) + '/'
        for path in (history_path + 'send/', '/api/chat/send/', history_path):
            with self.subTest(path=path):
                self.provider.reset_mock()
                result = self.send(path, 'Next synthetic turn', conversation_id=first['conversation_id']).json()
                self.assertEqual(result['status'], 'failed')
                self.assertEqual(self.provider.call_count, 2)
                self.assertEqual(result['receipt']['route']['company_engine_id'], other.pk)
                self.assertEqual(result['receipt']['history']['sent_turns'], 1)
                generations = [call for call in result['receipt']['calls'] if call['purpose'] == 'generation']
                self.assertEqual([call['provider'] for call in generations],
                                 [f'engine:{self.credential.pk}', f'engine:{other.pk}'])
                receipt_url = '/chat/requests/' + result['request_id'] + '/receipt/'
                exported = self.client.get(receipt_url)
                self.assertEqual(exported.status_code, 200)
                self.assertIn('attachment;', exported['Content-Disposition'])
                saved = exported.json()
                self.assertContains(self.client.get(history_path), 'data-receipt-url="' + receipt_url + '"')
                self.browser("""
const result = """ + json.dumps(result) + "; const saved = " + json.dumps(saved) + "; const receiptUrl = " + json.dumps(receipt_url) + ";" + """
currentConversationId = result.conversation_id;
const command = {requestId: result.request_id, userBubble: new Element()};
renderResult(result, command);
const expectedDestination = """ + json.dumps(f'engine:{other.pk}') + "; const originalDestination = " + json.dumps(f'engine:{self.credential.pk}') + ";" + r"""
function checkDestination(receipt) {
  assert.ok(receipt.children.some(line => line.text === 'Destination: ' + expectedDestination));
  assert.ok(receipt.children.some(line => line.text === 'Effective route: ' + expectedDestination + ' / synthetic-v1'));
  const generationLines = receipt.children.filter(line => /^Call \d+: generation/.test(line.text));
  assert.equal(generationLines.length, 2);
  assert.ok(generationLines[0].text.includes(originalDestination + ' / synthetic-v1'));
  assert.ok(generationLines[1].text.includes(expectedDestination + ' / synthetic-v1'));
  assert.match(receipt.text, /History turns sent \/ omitted: 1 \/ 0/);
  assert.doesNotMatch(receipt.text, /Second engine|synthetic-key|synthetic-other|https?:\/\//);
}
checkDestination(command.receipt.children[1]);
assert.equal(command.receipt.children.find(child => child.tag === 'a').href, receiptUrl);
const exportedReceipt = new Element(); renderReceipt(exportedReceipt, saved.receipt, saved.status);
checkDestination(exportedReceipt);
(async () => {
  const details = new Element('details'), restored = new Element();
  details.open = true; details.dataset = {receiptUrl}; details.querySelector = () => restored;
  document.querySelectorAll = () => [details];
  let requested;
  fetch = async url => {requested = url; return {ok: true, json: async () => saved};};
  loadSavedDetails('.request-receipt', 'receiptUrl', (body, data) => renderReceipt(body, data.receipt, data.status));
  await details.toggle();
  assert.equal(requested, receiptUrl); assert.equal(details.dataset.loaded, 'true');
  checkDestination(restored);
})();
""", path=history_path)

    def test_pending_consent_shows_omissions_and_preserves_request_and_file(self):
        self.browser(r"""
const file = {name: 'synthetic.docx'}, bubble = new Element();
const command = {requestId: 'same-request', file, prompt: 'same-input', userBubble: bubble, token: 'old-token'};
renderResult({status: 'pending_consent', success: false, consent_token: 'renewed-token',
  consent_reason: 'consent_expired', receipt: {coverage: {status: 'complete_text_only',
    disclosures: [{code: 'images_unread', count: 2, locators: ['paragraph:1']}]},
    notices: ['classification_ambiguous'], history: {sent_turns: 3, omitted_turns: 4, sent_bytes: 100, omitted_bytes: 200},
    limits: {jev_state_bytes: 131072, max_output_tokens: 4000}, route: {model_effective: 'effective-model'}}}, command);
assert.equal(command.requestId, 'same-request'); assert.equal(command.file, file);
assert.equal(command.token, 'renewed-token');
assert.match(bubble.text, /Imágenes no analizadas ni enviadas.*2/); assert.match(bubble.text, /paragraph:1/);
assert.match(bubble.text, /expired/i); assert.match(bubble.text, /classification_ambiguous/);
assert.match(bubble.text, /History turns sent \/ omitted: 3 \/ 4/);
assert.match(bubble.text, /131072/); assert.match(bubble.text, /effective-model/);
assert.match(command.controls.text, /Imágenes no analizadas ni enviadas/);
let confirmed; submitCommand = value => {confirmed = value;};
command.controls.children.find(e => e.tag === 'button').click();
assert.equal(confirmed, command); assert.equal(confirmed.token, 'renewed-token');
""")

    def test_advisory_answer_is_labelled_and_retains_no_verified_evidence(self):
        self.browser(r"""
const command = {requestId: 'advisory', userBubble: new Element()};
renderResult({status: 'completed', success: true, receipt: {verification: {status: 'failed'}},
  assistant_message: {content: 'A synthetic claim'},
  evidence: {items: [{claim_index: 1, locator: 'line:1', excerpt: 'UNVERIFIED_EXCERPT'}]}}, command);
assert.match(command.assistantBubble.text, /No verificado/);
assert.doesNotMatch(command.assistantBubble.text, /UNVERIFIED_EXCERPT/);
const evidence = new Element();
renderEvidence(evidence, {items: [{claim_index: 1, locator: 'line:1', excerpt: 'verified source'}]});
assert.match(evidence.text, /\[1\] line:1/);
""")

    def test_informational_disclosures_are_not_reported_as_omitted_content(self):
        self.browser(r"""
const output = new Element();
renderDisclosures(output, {disclosures: [{code: 'tracked_changes_present', count: 1, locators: ['paragraph:1']},
  {code: 'encoding_assumed', count: 1, locators: ['document']}, {code: 'blank_page', count: 1, locators: ['page:2']}]});
assert.match(output.text, /cambios aceptados/); assert.match(output.text, /Windows-1252/);
assert.match(output.text, /Página en blanco/); assert.doesNotMatch(output.text, /no analizada|no enviada/i);
const receipt = new Element(); renderReceipt(receipt,
  {limits: {response_bytes: 12345, history_max_bytes: 32768, history_max_turns: 20}}, 'completed');
assert.match(receipt.text, /Response limit \(bytes\): 12345/);
assert.match(receipt.text, /History limit \(bytes\): 32768/);
assert.match(receipt.text, /History limit \(turns\): 20/);
const withoutLimits = new Element(); renderReceipt(withoutLimits, {}, 'completed');
assert.doesNotMatch(withoutLimits.text, /History limit/);
""")
