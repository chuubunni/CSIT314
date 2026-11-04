"""Check that every merge file was installed, without opening the database."""
from pathlib import Path
import hashlib
import json
import sys
root=Path(__file__).resolve().parent
manifest=json.loads((root/'MERGE_MANIFEST.json').read_text(encoding='utf-8'))
bad=[]
for name,expected in manifest['sha256'].items():
    p=root/name
    actual=hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest() if p.is_file() else None
    if actual!=expected:bad.append(name)
if bad:
    print('Missing or different merge files:')
    print('\n'.join(bad))
    sys.exit(1)
print('All merged files match. Restart Flask to load them.')
