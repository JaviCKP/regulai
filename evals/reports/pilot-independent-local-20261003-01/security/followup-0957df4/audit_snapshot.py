"""Read-only source/dependency audit for the frozen review evidence."""
import hashlib
from importlib import metadata
import json
from pathlib import Path
from packaging.requirements import Requirement

HERE = Path(__file__).resolve().parent
manifest = json.loads((HERE / 'snapshot-manifest.json').read_text(encoding='utf-8'))
mismatches = []
for name, expected in manifest['files'].items():
    path = HERE / 'snapshot' / name
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        mismatches.append(name)
packages = []
for line in (HERE / 'snapshot' / 'requirements.txt').read_text(encoding='utf-8').splitlines():
    if not line.strip() or line.lstrip().startswith('#'):
        continue
    requirement = Requirement(line)
    installed = metadata.version(requirement.name)
    packages.append({'name': requirement.name, 'installed': installed, 'requirement': str(requirement),
                     'version_matches': installed in requirement.specifier if not requirement.url else installed == '3.8.0'})
model = metadata.distribution('xx-ent-wiki-sm')
result = {'candidate': manifest['commit'], 'base': manifest['base'], 'file_count': len(manifest['files']),
          'mismatches': mismatches, 'dependencies': packages,
          'model_direct_url': json.loads(model.read_text('direct_url.json')),
          'model_declared_license': model.metadata.get('License'),
          'spacy_declared_license': metadata.metadata('spacy').get('License'),
          'evidence_hashes': {item.name: hashlib.sha256(item.read_bytes()).hexdigest()
                              for item in HERE.iterdir() if item.is_file() and item.name != 'integrity.json'}}
(HERE / 'integrity.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps({'file_count': len(manifest['files']), 'source_mismatches': mismatches,
                  'dependency_count': len(packages), 'dependency_mismatches': [item for item in packages if not item['version_matches']],
                  'model_direct_url': result['model_direct_url'],
                  'licenses': [result['model_declared_license'], result['spacy_declared_license']]}))
raise SystemExit(bool(mismatches or any(not item['version_matches'] for item in packages)))
