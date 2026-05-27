import unittest

from src.skills.catalog import list_registered_skills, load_builtin_skills


class SkillCatalogTests(unittest.TestCase):
    def test_builtin_skill_catalog_loads_core_capabilities(self):
        names = {skill["name"] for skill in load_builtin_skills()}

        self.assertIn("read_file", names)
        self.assertIn("write_file", names)
        self.assertIn("check_license", names)
        self.assertIn("analyze_design_pattern", names)
        self.assertIn("minify_code", names)
        self.assertIn("truncate_logs", names)
        self.assertIn("list_uaf_skills", names)
        self.assertIn("read_uaf_skill", names)
        self.assertNotIn("list_reference_blueprints", names)
        self.assertNotIn("read_reference_blueprint", names)

    def test_registered_skill_catalog_is_sorted(self):
        load_builtin_skills()
        names = [skill["name"] for skill in list_registered_skills()]

        self.assertEqual(names, sorted(names))


if __name__ == "__main__":
    unittest.main()
