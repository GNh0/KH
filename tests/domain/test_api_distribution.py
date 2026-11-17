"""Verify the extracted API skill runs without the KH package."""
import json
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]


class ApiDistributionTests(unittest.TestCase):
    def test_unlisted_source_is_excluded_without_creating_probes_in_the_project(self):
        with tempfile.TemporaryDirectory() as folder:
            external = Path(folder).resolve()
            checkout = external / 'source'
            skill = checkout / 'standalone/api-auth'
            original = ROOT / 'standalone/api-auth'
            manifest = json.loads((original / 'bundle.json').read_text(encoding='utf-8'))
            for name in ['bundle.json', *manifest['payload']]:
                target = skill / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(original / name, target)
            (checkout / 'scripts').mkdir()
            shutil.copyfile(ROOT / 'scripts/build_api_skill.py', checkout / 'scripts/build_api_skill.py')
            (skill / 'src/api_auth/unlisted-private-probe.py').write_text('private fixture', encoding='utf-8')
            archive = external / 'api-auth.zip'
            subprocess.run([sys.executable, '-B', str(checkout / 'scripts/build_api_skill.py'), '--out', str(archive)],
                           cwd=external, capture_output=True, check=True, timeout=15)
            with zipfile.ZipFile(archive) as bundle:
                self.assertFalse(any('unlisted-private-probe' in name for name in bundle.namelist()))

    def test_installation_archive_runs_without_kh_or_source_checkout(self):
        self.assertFalse((ROOT / 'skills/api-auth').exists())
        self.assertFalse((ROOT / 'src/api_auth').exists())
        self.assertFalse((ROOT / 'scripts/kh_api.py').exists())
        with tempfile.TemporaryDirectory() as folder:
            external = Path(folder).resolve()
            archive = external / 'api-auth.zip'
            built = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/build_api_skill.py'),
                                    '--out', str(archive)], cwd=external, capture_output=True,
                                   text=True, encoding='utf-8', check=True, timeout=15)
            self.assertEqual(str(archive), json.loads(built.stdout)['path'])
            with zipfile.ZipFile(archive) as bundle:
                self.assertIsNone(bundle.testzip())
                self.assertTrue(all(name.startswith('api-auth/') for name in bundle.namelist()))
                self.assertFalse(any('/tests/' in name or '__pycache__' in name or name.endswith('.sqlite3')
                                     for name in bundle.namelist()))
                bundle.extractall(external / 'installed')
            script = external / 'installed/api-auth/scripts/api_auth.py'
            result = subprocess.run([sys.executable, '-B', str(script), '--help'], cwd=external,
                                    capture_output=True, text=True, encoding='utf-8', timeout=15)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn('registration-plan', result.stdout)
            self.assertIn('stream', result.stdout)
