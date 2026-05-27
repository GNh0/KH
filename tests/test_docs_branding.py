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


if __name__ == "__main__":
    unittest.main()
