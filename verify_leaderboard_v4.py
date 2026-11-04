"""Verify installation of leaderboard/moderation v4 without opening the database."""
from pathlib import Path
import hashlib,json,sys
root=Path(__file__).resolve().parent
manifest=json.loads((root/'LEADERBOARD_V4_MANIFEST.json').read_text(encoding='utf-8'))
bad=[]
for name,expected in manifest['sha256'].items():
    p=root/name
    actual=hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest() if p.is_file() else None
    if actual!=expected:bad.append(name)
if bad:
    print('Missing or different leaderboard v4 files:')
    print('\n'.join(bad))
    sys.exit(1)
print('All leaderboard v4 files match. Restart Flask to load them.')
