"""Restore the existing UI dependencies locally; no npm/global installation."""
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

root = Path(__file__).resolve().parents[1] / 'regulai/static/vendor'
root.mkdir(exist_ok=True)
sources = {
    'jquery.min.js': 'https://cdn.jsdelivr.net/npm/jquery@3.7.1/dist/jquery.min.js',
    'bootstrap.bundle.min.js': 'https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js',
    'iconify-icon.min.js': 'https://cdn.jsdelivr.net/npm/iconify-icon@1.0.8/dist/iconify-icon.min.js',
    'simplebar.css': 'https://cdn.jsdelivr.net/npm/simplebar@6.2.5/dist/simplebar.css',
}
manifest_file = root / 'manifest.json'
existing = json.loads(manifest_file.read_text()) if manifest_file.exists() else {}
manifest = {}
for name, url in sources.items():
    with urlopen(url, timeout=30) as response:
        content = response.read(1024 * 1024)
    checksum = hashlib.sha256(content).hexdigest()
    if name in existing and checksum != existing[name]['sha256']:
        raise ValueError(f'Checksum mismatch for {name}; retained existing assets.')
    (root / name).write_bytes(content)
    manifest[name] = {'source': url, 'sha256': checksum}
manifest_file.write_text(json.dumps(manifest, indent=2) + '\n')
print(f'Verified {len(manifest)} local UI assets.')
