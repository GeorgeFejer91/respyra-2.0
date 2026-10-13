"""Check the curated download record against its public, qualified release."""

from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import urllib.request

root = Path(__file__).resolve().parents[2]
release = json.loads((root / 'companion/download/release.json').read_text(encoding='utf-8'))
receipt = (root / release['verificationReceipt']).read_text(encoding='utf-8')
gh = shutil.which('gh') or r'C:\Program Files\GitHub CLI\gh.exe'
repository = 'GeorgeFejer91/respyra-2.0'
published = json.loads(subprocess.check_output([gh, 'api', f'repos/{repository}/releases/tags/{release["tag"]}']))
assert not published['draft'], 'The curated installer release must be public'
assert published['prerelease'] == release['preview'], 'Preview status differs from the public release'
tag = release['tag']
remote_tags = dict(line.split()[::-1] for line in subprocess.check_output(
    ['git', '-C', str(root), 'ls-remote', 'origin', f'refs/tags/{tag}', f'refs/tags/{tag}^{{}}'], text=True).splitlines())
assert remote_tags.get(f'refs/tags/{tag}^{{}}', remote_tags.get(f'refs/tags/{tag}')) == release['sourceRevision'], 'Public tag differs from qualified source'
assert release['sourceRevision'] in receipt and release['miniSourceRevision'] in receipt
assert [installer['id'] for installer in release['installers']] == ['suite', 'respyra', 'polar', 'vernier']
assets = {asset['name']: asset for asset in published['assets']}
checked = []
for installer in release['installers']:
    assert installer['file'] in receipt and installer['sha256'] in receipt, 'Installer qualification receipt differs'
    asset = assets[installer['file']]
    assert asset['size'] == installer['size'], installer['file'] + ' size differs'
    assert asset['digest'] == 'sha256:' + installer['sha256'], installer['file'] + ' digest differs'
    url = f'https://github.com/{repository}/releases/download/{tag}/{installer["file"]}'
    assert asset['browser_download_url'] == url
    request = urllib.request.Request(url, headers={'Range':'bytes=0-1', 'User-Agent':'Respyra-website-release-check'})
    with urllib.request.urlopen(request, timeout=30) as response:
        assert response.status in (200, 206), response.status
        size = response.headers['Content-Range'].rsplit('/', 1)[-1] if response.status == 206 else response.headers['Content-Length']
        assert int(size) == installer['size'], installer['file'] + ' public response size differs'
        assert response.read(2) == b'MZ', installer['file'] + ' is not a Windows executable'
    checked.append(dict(id=installer['id'], file=installer['file'], size=installer['size'], sha256=installer['sha256']))
    print('VERIFIED public artifact metadata/access:', installer['file'], flush=True)
evidence = root / '.for-ai-local'
evidence.mkdir(exist_ok=True)
(evidence / 'download-release-check.json').write_text(json.dumps(dict(
    result='VERIFIED', checkedAt=datetime.now(timezone.utc).isoformat(), tag=tag,
    sourceRevision=release['sourceRevision'], verificationReceipt=release['verificationReceipt'], installers=checked,
    scope='Public tag, server digest/size, anonymous executable prefix/access; installed qualification reused from the exact artifact receipt.'
), indent=2), encoding='utf-8')
print('PASS: curated suite and three individual installers match qualified public artifacts', flush=True)
