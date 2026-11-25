import getpass
import json
import re
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]


def manifest(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding='utf-8-sig'))


class ManifestVersionTests(unittest.TestCase):
    def test_every_host_manifest_publishes_the_same_release(self):
        claude = manifest('.claude-plugin/plugin.json')
        listed = {item['name']: item for item in manifest('.claude-plugin/marketplace.json')['plugins']}
        versions = {
            '.claude-plugin/plugin.json': claude['version'],
            '.claude-plugin/marketplace.json': listed[claude['name']]['version'],
            '.codex-plugin/plugin.json': manifest('.codex-plugin/plugin.json')['version'],
            '.antigravity-plugin/plugin.json': manifest('.antigravity-plugin/plugin.json')['version'],
        }
        self.assertEqual(1, len(set(versions.values())), versions)

    def test_host_marketplaces_install_the_shared_release_branch(self):
        claude = manifest('.claude-plugin/marketplace.json')['plugins']
        codex = manifest('.agents/plugins/marketplace.json')['plugins']
        self.assertEqual({'release'}, {item['source']['ref'] for item in [*claude, *codex]})
        self.assertEqual({'kh-uaf'}, {item['name'] for item in codex})
        self.assertEqual('kh-uaf', manifest('.codex-plugin/plugin.json')['name'])

    def test_tracked_documentation_has_no_personal_windows_profile(self):
        # Claude installs the whole repository, so history notes ship with the plugin.
        found = subprocess.run(['git', 'grep', '-l', '-I', '-i', r'users[\\/]\+' + re.escape(getpass.getuser()), '--', 'docs', 'skills', 'agents', '*.md'],
                               cwd=ROOT, capture_output=True, text=True)
        if found.returncode not in {0, 1}:
            self.skipTest('git grep unavailable: ' + found.stderr.strip())
        self.assertEqual('', found.stdout.strip())


if __name__ == '__main__':
    unittest.main()
