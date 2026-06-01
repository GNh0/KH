import unittest

from src.orchestration.domain_profiles import (
    DomainProfileBuilder,
    render_work_design_markdown,
    work_design_from_profile,
)


class DomainProfileBuilderTests(unittest.TestCase):
    def test_builder_creates_generic_domain_profile_for_any_topic(self):
        profile = DomainProfileBuilder.build(
            objective="Design a training curriculum",
            domain_hint="education",
            subdomains=["learning goals", "assessment"],
            artifact_types=["curriculum-structure", "assessment-plan"],
        )

        self.assertEqual(profile.domain_name, "education")
        self.assertIn("learning goals", profile.subdomains)
        self.assertIn("curriculum-structure", profile.required_design_artifact_types)
        self.assertIn("work design saved", profile.evidence_required)
        self.assertIn("final-decision-manager", [role.name for role in profile.roles])

    def test_work_design_from_profile_carries_required_artifacts_and_gates(self):
        profile = DomainProfileBuilder.build(
            objective="Assess a logistics process",
            artifact_types=["process-map", "risk-checklist"],
        )

        design = work_design_from_profile(
            profile,
            scope="warehouse operation",
            deliverables=["process improvement memo"],
        )

        self.assertEqual(design.objective, "Assess a logistics process")
        self.assertIn("process-map", design.design_artifacts)
        self.assertIn("process improvement memo", design.deliverables)
        self.assertIn("risk policy checked", design.evidence_required)

    def test_render_work_design_markdown_is_domain_neutral(self):
        profile = DomainProfileBuilder.build("Compare operating models")
        design = work_design_from_profile(profile)

        markdown = render_work_design_markdown(design)

        self.assertIn("# Work Design", markdown)
        self.assertIn("Compare operating models", markdown)
        self.assertIn("## Required Design Artifacts", markdown)


if __name__ == "__main__":
    unittest.main()
