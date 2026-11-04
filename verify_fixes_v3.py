"""Check that all v3 patch source files were extracted into this repo."""
from pathlib import Path
import hashlib
import json
import sys

root = Path(__file__).resolve().parent
manifest = json.loads((root / 'FIXES_V3_MANIFEST.json').read_text(encoding='utf-8'))
bad = []
for relative, expected in manifest['sha256'].items():
    target = root / relative
    # Accept equivalent CRLF/LF checkouts on Windows/Git.
    actual = hashlib.sha256(target.read_bytes().replace(b'\r\n', b'\n')).hexdigest() if target.is_file() else None
    if actual != expected:
        bad.append(relative)
if bad:
    print('Missing or different v3 files:')
    print('\n'.join(bad))
    sys.exit(1)
print('All v3 fix files match. Restart Flask to load them.')
