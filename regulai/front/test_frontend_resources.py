"""Offline resource and browser behavior regressions."""
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
import subprocess

from django.test import SimpleTestCase
from django.template.loader import render_to_string
from django.urls import reverse
from front.test_chat_flow import ChatFixture

ROOT = Path(__file__).resolve().parents[2]
NAVIGATION = {
    'https://platform.openai.com/api-keys',
    'https://console.anthropic.com/settings/keys',
    'https://platform.deepseek.com/api_keys',
    'https://yara.readthedocs.io/en/stable/writingrules.html',
}


class ResourceTests(SimpleTestCase):
    def test_templates_and_styles_load_only_local_resources(self):
        violations = []

        class Tags(HTMLParser):
            def handle_starttag(self, tag, attrs):
                for key, value in attrs:
                    if key in {'href', 'src', 'srcset', 'action', 'poster', 'data'} and value and re.match(r'^(?:https?:)?//', value):
                        if not (tag == 'a' and key == 'href' and value in NAVIGATION):
                            violations.append(value)

        for path in (ROOT / 'regulai/front/templates').rglob('*.html'):
            Tags().feed(path.read_text(encoding='utf-8'))
        for path in (ROOT / 'regulai/static/css').rglob('*.css'):
            text = re.sub(r'/\*.*?\*/', '', path.read_text(encoding='utf-8'), flags=re.S)
            violations.extend(re.findall(r'(?:url\(\s*[\"\']?|@import\s+[\"\'])(?:https?:)?//[^)\"\'\s]+', text))
        self.assertEqual(violations, [])

    def test_pinned_assets_verify_without_network(self):
        result = subprocess.run([__import__('sys').executable, str(ROOT / 'scripts/vendor_assets.py'), '--check'],
                                text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Verified', result.stdout)

    def test_icons_are_registered_locally_and_network_is_disabled(self):
        node = shutil.which('node')
        self.assertIsNotNone(node)
        harness = r"""
const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
let fetcher = 'enabled'; const collections = [];
const icon = {_api: {setFetch: value => {fetcher = value}}, addCollection: value => collections.push(value)};
const context = {customElements: {get: () => icon}};
vm.createContext(context);
for (const file of process.argv.slice(1)) vm.runInContext(fs.readFileSync(file, 'utf8'), context);
assert.equal(fetcher, undefined);
assert.equal(collections.length, 2);
assert.ok(collections.find(c => c.prefix === 'solar').icons['chat-round-dots-bold']);
assert.ok(collections.find(c => c.prefix === 'simple-icons').icons.openai);
"""
        result = subprocess.run([node, '-e', harness, str(ROOT / 'regulai/static/vendor/solar-icons.js'),
                                 str(ROOT / 'regulai/static/vendor/brand-icons.js')],
                                text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)


class BrowserPolicyTests(ChatFixture):
    def test_company_admin_keeps_engine_controls_without_operator_model_controls(self):
        self.user.is_superuser = True
        self.user.is_staff = True
        html = render_to_string('engines/list.html', {'user': self.user,
            'company_engines': [self.credential], 'is_platform_operator': False})
        self.assertIn(reverse('front:engine_toggle', args=[self.credential.pk]), html)
        self.assertNotIn('Add Model', html)
        self.assertNotIn(reverse('front:model_toggle', args=[self.model.pk]), html)
        self.assertNotIn('Admin Panel', html)

    def test_operator_model_actions_are_post_forms_with_csrf(self):
        html = render_to_string('engines/list.html', {'user': self.user,
            'company_engines': [self.credential], 'is_platform_operator': True,
            'csrf_token': 'synthetic-csrf'})
        for action in ('engine_toggle', 'model_toggle', 'model_delete'):
            pk = self.credential.pk if action == 'engine_toggle' else self.model.pk
            url = reverse('front:' + action, args=[pk])
            self.assertIn('method="post" action="' + url + '"', html)
            self.assertNotIn('href="' + url + '"', html)
        self.assertIn('name="csrfmiddlewaretoken" value="synthetic-csrf"', html)

    def test_csp_declares_only_self_and_existing_inline_ui(self):
        response = self.client.get('/chat/')
        self.assertEqual(response.status_code, 200)
        policy = response.headers.get('Content-Security-Policy-Report-Only', '')
        self.assertIn("default-src 'self'", policy)
        self.assertIn("connect-src 'self'", policy)
        self.assertIn("script-src 'self' 'unsafe-inline'", policy)
        self.assertNotIn('Content-Security-Policy', response.headers)
