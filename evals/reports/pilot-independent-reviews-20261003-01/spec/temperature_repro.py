"""Fixed-candidate integration probe, in-memory DB and blocked real sockets."""
import json
from pathlib import Path

from front import evaluation
from front.test_smoke import SmokeIsolationTests


class DocumentTemperatureRepro(SmokeIsolationTests):
    def test_document_request_matches_manifest_temperature(self):
        source = evaluation.PILOT_MANIFEST.parent
        self.case = next(json.loads(line) for line in (source / 'cases.jsonl').read_text(encoding='utf-8').splitlines()
                         if json.loads(line)['id'] == 'document-success')
        (self.root / 'cases.jsonl').write_text(json.dumps(self.case) + '\n', encoding='utf-8')
        self.manifest['dataset_sha256'] = evaluation.digest((self.root / 'cases.jsonl').read_bytes())
        self.save_approval()
        self.temperatures = []
        self.run_smoke()
        observed = {'case': self.case['id'], 'manifest_temperature': self.manifest['generation_options']['temperature'],
                    'http_temperatures': self.temperatures, 'network_socket_calls': self.socket.call_count}
        (Path(__file__).parent / 'temperature-observed.json').write_text(json.dumps(observed, indent=2), encoding='utf-8')
        print(json.dumps(observed))
        self.assertEqual(set(self.temperatures), {self.manifest['generation_options']['temperature']})

    def sdk_transport(self, request, **kwargs):
        self.temperatures.append(json.loads(request.content)['temperature'])
        return super().sdk_transport(request, **kwargs)
