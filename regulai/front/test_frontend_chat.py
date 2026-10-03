"""Run rendered chat JavaScript with an offline DOM and synthetic server replies."""
import json
import re
import shutil
import subprocess

from front.test_chat_flow import ChatFixture


class ChatUiTests(ChatFixture):
    def browser(self, checks):
        response = self.client.get('/chat/')
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

    def test_pending_consent_shows_omissions_and_preserves_request_and_file(self):
        self.browser(r"""
const file = {name: 'synthetic.docx'}, bubble = new Element();
const command = {requestId: 'same-request', file, prompt: 'same-input', userBubble: bubble, token: 'old-token'};
renderResult({status: 'pending_consent', success: false, consent_token: 'renewed-token',
  consent_reason: 'consent_expired', receipt: {coverage: {status: 'complete_text_only',
    disclosures: [{code: 'images_omitted', count: 2, locators: ['paragraph:1']}]},
    notices: ['classification_ambiguous'], history: {sent_turns: 3, omitted_turns: 4, sent_bytes: 100, omitted_bytes: 200},
    limits: {jev_state_bytes: 131072, max_output_tokens: 4000}, route: {model_effective: 'effective-model'}}}, command);
assert.equal(command.requestId, 'same-request'); assert.equal(command.file, file);
assert.equal(command.token, 'renewed-token');
assert.match(bubble.text, /images_omitted.*2/); assert.match(bubble.text, /paragraph:1/);
assert.match(bubble.text, /expired/i); assert.match(bubble.text, /classification_ambiguous/);
assert.match(bubble.text, /History turns sent \/ omitted: 3 \/ 4/);
assert.match(bubble.text, /131072/); assert.match(bubble.text, /effective-model/);
assert.match(command.controls.text, /images_omitted/);
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
