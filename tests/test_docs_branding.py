import unittest
from pathlib import Path


class DocsBrandingTests(unittest.TestCase):
    def test_skillbook_docs_use_personal_project_folder(self):
        docs_root = Path("docs")

        self.assertTrue((docs_root / "skillbook").is_dir())
        old_folder = "super" + "powers"
        self.assertFalse((docs_root / old_folder).exists())
        self.assertTrue((docs_root / "skillbook" / "plans").is_dir())
        self.assertTrue((docs_root / "skillbook" / "specs").is_dir())

    def test_public_project_surface_uses_personal_uaf_branding(self):
        checked_roots = [
            Path("README.md"),
            Path("README.ko.md"),
            Path("SKILL.md"),
            Path("plugin.json"),
            Path("docs"),
            Path("skills"),
            Path("src"),
            Path("tests"),
        ]
        blocked_tokens = ("g" + "stack", "garry" + "tan")
        findings = []

        for root in checked_roots:
            paths = [root] if root.is_file() else [path for path in root.rglob("*") if path.is_file()]
            for path in paths:
                path_text = path.as_posix().lower()
                if any(token in path_text for token in blocked_tokens):
                    findings.append(f"path:{path.as_posix()}")
                    continue

                try:
                    content = path.read_text(encoding="utf-8").lower()
                except UnicodeDecodeError:
                    continue

                if any(token in content for token in blocked_tokens):
                    findings.append(f"content:{path.as_posix()}")

        self.assertEqual([], findings)

    def test_public_project_surface_has_no_mojibake_markers(self):
        checked_roots = [
            Path("README.md"),
            Path("README.ko.md"),
            Path("SKILL.md"),
            Path("plugin.json"),
            Path(".codex-plugin/plugin.json"),
            Path(".agents/plugins"),
            Path("docs"),
            Path("skills"),
            Path("src"),
            Path("tests"),
        ]
        marker_codes = (
            0x00C3,
            0x00C2,
            0xFFFD,
            0xF9E3,
            0xBD89,
            0xBEA4,
            0x314C,
            0xAC57,
            0xAFAA,
            0x8E42,
            0x7230,
            0x6028,
        )
        mojibake_markers = tuple(chr(code) for code in marker_codes)
        findings = []

        for root in checked_roots:
            paths = [root] if root.is_file() else [path for path in root.rglob("*") if path.is_file()]
            for path in paths:
                try:
                    content = path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    continue

                for marker in mojibake_markers:
                    if marker in content:
                        findings.append(f"{path.as_posix()}:{marker}")

        self.assertEqual([], findings)


if __name__ == "__main__":
    unittest.main()
