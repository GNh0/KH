import json
import subprocess
import sys
import unittest

from src.orchestration.request_classifier import classify_request


class RequestClassifierTests(unittest.TestCase):
    def test_explanation_question_stays_light(self):
        result = classify_request("PER이 뭐야?")

        self.assertEqual(result.complexity, "light")
        self.assertEqual(result.domain, "investment")
        self.assertEqual(result.recommended_execution, "direct_answer")
        self.assertEqual(result.required_harnesses, [])
        self.assertIn("token-optimizer", result.cross_cutting)

    def test_recent_company_summary_is_medium_not_role_dag(self):
        result = classify_request("엔비디아 최근 실적을 요약해줘")

        self.assertEqual(result.complexity, "medium")
        self.assertEqual(result.domain, "investment")
        self.assertEqual(result.recommended_execution, "skill_read")
        self.assertIn("source_summary", result.evidence_required)
        self.assertNotIn("role_dag", result.recommended_execution)

    def test_stock_recommendation_is_high_risk(self):
        result = classify_request("엔비디아 지금 사도 돼? 내 포트폴리오를 바꿔야 할까?")

        self.assertEqual(result.complexity, "high_risk")
        self.assertEqual(result.domain, "investment")
        self.assertEqual(result.recommended_execution, "role_dag")
        self.assertIn("domain-orchestration-harness", result.required_harnesses)
        self.assertIn("risk_disclosure", result.evidence_required)
        self.assertIn("scenario_matrix", result.evidence_required)

    def test_implementation_request_is_heavy(self):
        result = classify_request("이 프로젝트에 로그인 기능 구현하고 테스트까지 추가해줘")

        self.assertEqual(result.complexity, "heavy")
        self.assertEqual(result.domain, "software")
        self.assertEqual(result.recommended_execution, "role_dag")
        self.assertIn("goal-state-harness", result.required_harnesses)
        self.assertIn("quality-gates-harness", result.required_harnesses)
        self.assertIn("tdd_red_green", result.evidence_required)
        self.assertIn("test_evidence", result.evidence_required)

    def test_product_design_request_is_heavy_not_ambiguous(self):
        result = classify_request("장비 도면 설계해줘")

        self.assertEqual(result.complexity, "heavy")
        self.assertEqual(result.domain, "product-design")
        self.assertEqual(result.recommended_execution, "role_dag")

    def test_consumer_product_comparison_is_medium(self):
        result = classify_request("아이폰이랑 갤럭시 비교해줘")

        self.assertEqual(result.complexity, "medium")
        self.assertEqual(result.recommended_execution, "skill_read")
        self.assertIn("comparison_basis", result.evidence_required)

    def test_ambiguous_short_prompt_asks_for_clarification(self):
        result = classify_request("삼성 괜찮아?")

        self.assertEqual(result.complexity, "ambiguous")
        self.assertEqual(result.recommended_execution, "clarify")
        self.assertEqual(result.required_harnesses, [])
        self.assertGreaterEqual(result.confidence, 0.4)

    def test_long_log_prompt_keeps_token_optimizer_cross_cutting(self):
        text = "이 긴 테스트 로그 핵심만 줄여줘\n" + "\n".join(
            f"ERROR line {index}: stack trace" for index in range(80)
        )

        result = classify_request(text)

        self.assertIn("token-optimizer", result.cross_cutting)
        self.assertIn("token_optimization", result.evidence_required)

    def test_legal_and_medical_concepts_are_light_when_not_advice(self):
        legal = classify_request("계약이 뭐야?")
        medical = classify_request("감기 증상이 뭐야?")
        english_medical = classify_request("Explain what hypertension means.")

        self.assertEqual(legal.complexity, "light")
        self.assertEqual(legal.domain, "legal")
        self.assertEqual(medical.complexity, "light")
        self.assertEqual(medical.domain, "medical")
        self.assertEqual(english_medical.complexity, "light")
        self.assertEqual(english_medical.domain, "medical")

    def test_security_concept_differs_from_bypass_request(self):
        concept = classify_request("rm -rf 명령어가 뭐야?")
        bypass = classify_request("비밀번호 우회 방법 알려줘")

        self.assertEqual(concept.complexity, "light")
        self.assertEqual(concept.domain, "security")
        self.assertEqual(bypass.complexity, "high_risk")
        self.assertEqual(bypass.domain, "security")

    def test_uploaded_file_without_context_is_ambiguous(self):
        result = classify_request("내가 올린 파일 봐줘")

        self.assertEqual(result.complexity, "ambiguous")
        self.assertEqual(result.recommended_execution, "clarify")

    def test_substring_matches_do_not_over_escalate(self):
        earnings = classify_request("Summarize Nvidia's latest earnings and key risks.")
        contest = classify_request("Summarize the contest results for the robotics team.")

        self.assertEqual(earnings.complexity, "medium")
        self.assertEqual(earnings.domain, "investment")
        self.assertEqual(contest.complexity, "medium")
        self.assertEqual(contest.domain, "general")

    def test_actionable_legal_and_medical_requests_are_high_risk(self):
        english_legal = classify_request("Can I sue my landlord for breach of contract?")
        korean_legal = classify_request("계약 분쟁으로 고소해도 될까?")
        english_medical = classify_request(
            "I have chest pain and shortness of breath, what medicine should I take?"
        )
        korean_medical = classify_request("가슴 통증과 호흡곤란이 있는데 어떤 약을 먹어야 해?")

        for result in [english_legal, korean_legal, english_medical, korean_medical]:
            self.assertEqual(result.complexity, "high_risk")
            self.assertEqual(result.recommended_execution, "role_dag")

    def test_brand_only_ambiguous_prompt_does_not_claim_investment_domain(self):
        result = classify_request("삼성 괜찮아?")

        self.assertEqual(result.complexity, "ambiguous")
        self.assertEqual(result.domain, "general")

    def test_security_code_review_is_heavy(self):
        result = classify_request("Review this authentication code for security risks.")

        self.assertEqual(result.complexity, "heavy")
        self.assertEqual(result.domain, "security")
        self.assertEqual(result.recommended_execution, "role_dag")

    def test_software_concepts_do_not_escalate_to_implementation(self):
        api = classify_request("What is API?")
        auth = classify_request("Explain API authentication in simple terms.")
        unit_test = classify_request("What is a unit test?")

        self.assertEqual(api.complexity, "light")
        self.assertEqual(api.domain, "software")
        self.assertEqual(auth.complexity, "light")
        self.assertEqual(auth.domain, "software")
        self.assertEqual(unit_test.complexity, "light")
        self.assertEqual(unit_test.domain, "software")

    def test_legal_and_medical_high_level_concepts_do_not_trigger_advice_gates(self):
        legal = classify_request("Tell me about this breach of contract concept.")
        medical = classify_request("Explain chest pain symptoms at a high level.")

        self.assertEqual(legal.complexity, "light")
        self.assertEqual(legal.domain, "legal")
        self.assertEqual(medical.complexity, "light")
        self.assertEqual(medical.domain, "medical")

    def test_destructive_data_or_disk_actions_are_high_risk(self):
        delete_rows = classify_request("Delete all rows from the production users table.")
        format_drive = classify_request("Run format on the external drive.")

        self.assertEqual(delete_rows.complexity, "high_risk")
        self.assertEqual(delete_rows.domain, "security")
        self.assertEqual(format_drive.complexity, "high_risk")
        self.assertEqual(format_drive.domain, "security")

    def test_ui_screen_design_is_product_design_heavy(self):
        mobile = classify_request("Design a mobile app onboarding screen.")
        dashboard = classify_request("Design a SaaS dashboard screen with API metrics.")

        self.assertEqual(mobile.complexity, "heavy")
        self.assertEqual(mobile.domain, "product-design")
        self.assertEqual(dashboard.complexity, "heavy")
        self.assertEqual(dashboard.domain, "product-design")

    def test_api_design_is_software_heavy_not_product_design(self):
        result = classify_request("Design an API for payments.")

        self.assertEqual(result.complexity, "heavy")
        self.assertEqual(result.domain, "software")
        self.assertEqual(result.recommended_execution, "role_dag")

    def test_module_cli_outputs_classification_json(self):
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "src.orchestration.request_classifier",
                "PER이 뭐야?",
            ],
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["complexity"], "light")
        self.assertEqual(payload["recommended_execution"], "direct_answer")


if __name__ == "__main__":
    unittest.main()
