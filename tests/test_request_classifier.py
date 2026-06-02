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

    def test_ui_filter_button_is_not_security_high_risk(self):
        result = classify_request(
            r"Create C:\work\dashboard as HTML/CSS/JS files with sample KPI cards, a table, filter button behavior, verification, and residual risk notes."
        )

        self.assertEqual(result.complexity, "heavy")
        self.assertEqual(result.domain, "software")
        self.assertEqual(result.recommended_execution, "role_dag")

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

    def test_vague_product_development_routes_to_brainstorming(self):
        result = classify_request(
            "C:\\work\\BrainstormEntryOnly "
            "\ud3f4\ub354\uc5d0 \uc6b4\uc601\uc9c0\uc6d0 \uc81c\ud488 \uac1c\ubc1c\ud574\uc918."
        )

        self.assertEqual(result.complexity, "medium")
        self.assertEqual(result.domain, "product")
        self.assertEqual(result.recommended_execution, "skill_read")
        self.assertIn("brainstorming-harness", result.recommended_skills)
        self.assertIn("brainstorming-harness", result.required_harnesses)
        self.assertIn("brainstorm_handoff", result.evidence_required)
        self.assertIn("early_product_discovery_needs_brainstorming", result.reasons)

    def test_product_built_request_routes_to_brainstorming(self):
        result = classify_request(
            "C:\\work\\BlindProductRequest folder needs an operations support product built."
        )

        self.assertEqual(result.complexity, "medium")
        self.assertEqual(result.domain, "product")
        self.assertEqual(result.recommended_execution, "skill_read")
        self.assertIn("brainstorming-harness", result.recommended_skills)
        self.assertIn("early_product_discovery_needs_brainstorming", result.reasons)

    def test_specific_verified_html_tool_does_not_route_to_brainstorming(self):
        result = classify_request("Build a small HTML todo tool and verify it.")

        self.assertEqual(result.complexity, "heavy")
        self.assertEqual(result.domain, "software")
        self.assertNotIn("brainstorming-harness", result.recommended_skills)

    def test_long_log_prompt_keeps_token_optimizer_cross_cutting(self):
        text = "이 긴 테스트 로그 핵심만 줄여줘\n" + "\n".join(
            f"ERROR line {index}: stack trace" for index in range(80)
        )

        result = classify_request(text)

        self.assertIn("token-optimizer", result.cross_cutting)
        self.assertIn("token_optimization", result.evidence_required)

    def test_expected_context_budget_forces_token_optimizer_evidence_without_heavy_route(self):
        result = classify_request(
            "What is PER?",
            {"estimated_context_tokens": 9000},
        )

        self.assertEqual(result.complexity, "light")
        self.assertEqual(result.recommended_execution, "direct_answer")
        self.assertIn("token-optimizer", result.cross_cutting)
        self.assertIn("token_optimization", result.evidence_required)
        self.assertIn("context_budget_threshold_exceeded", result.reasons)

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

    def test_blind_side_everyday_requests_do_not_over_or_under_route(self):
        cases = [
            ("ok now send it", "ambiguous", "general", "clarify", {}),
            ("try again", "ambiguous", "general", "clarify", {}),
            ("fix the tone", "ambiguous", "general", "clarify", {}),
            ("write a polite email asking my landlord to fix the heater", "light", "general", "direct_answer", {}),
            ("make this email less rude: I need this by Friday", "light", "general", "direct_answer", {}),
            ("summarize this", "ambiguous", "general", "clarify", {}),
            (
                "summarize this article in three bullets: apples are fruits and bananas are yellow",
                "light",
                "general",
                "direct_answer",
                {},
            ),
            ("format this as a table: apples 2 bananas 3", "light", "general", "direct_answer", {}),
            ("how do I clean coffee out of a white shirt?", "light", "general", "direct_answer", {}),
            ("make a checklist for packing for a weekend trip", "light", "general", "direct_answer", {}),
        ]

        for prompt, complexity, domain, route, context in cases:
            with self.subTest(prompt=prompt):
                result = classify_request(prompt, context=context)
                self.assertEqual(result.complexity, complexity)
                self.assertEqual(result.domain, domain)
                self.assertEqual(result.recommended_execution, route)

    def test_blind_side_external_evidence_requests_route_to_skill_or_clarify(self):
        cases = [
            ("compare air fryers under $100", "medium", "shopping", "skill_read"),
            ("which laptop should I buy for school?", "medium", "shopping", "skill_read"),
            ("is this jacket worth it?", "ambiguous", "shopping", "clarify"),
            ("find me a cheap desk chair", "medium", "shopping", "skill_read"),
            ("buy more coffee filters", "ambiguous", "shopping", "clarify"),
            ("remind me tomorrow to call mom", "medium", "scheduling", "skill_read"),
            ("schedule a dentist appointment next week", "ambiguous", "scheduling", "clarify"),
            ("move my meeting to 3", "ambiguous", "scheduling", "clarify"),
            ("what's on my calendar today?", "medium", "scheduling", "skill_read"),
            ("is it going to rain tomorrow?", "medium", "weather", "skill_read"),
            ("do I need an umbrella today?", "medium", "weather", "skill_read"),
        ]

        for prompt, complexity, domain, route in cases:
            with self.subTest(prompt=prompt):
                result = classify_request(prompt)
                self.assertEqual(result.complexity, complexity)
                self.assertEqual(result.domain, domain)
                self.assertEqual(result.recommended_execution, route)

    def test_blind_side_developer_followups_and_auth_work_route_by_context(self):
        cases = [
            ("Explain async/await in simple terms.", {}, "light", "software", "direct_answer"),
            ("What does JWT mean?", {}, "light", "software", "direct_answer"),
            (
                "Here is a traceback from pytest, diagnose the failure and suggest next steps.",
                {},
                "medium",
                "software",
                "skill_read",
            ),
            ("Make the checkout button easier to find on mobile.", {}, "heavy", "product-design", "role_dag"),
            ("Add OAuth login and store refresh tokens securely.", {}, "heavy", "software", "role_dag"),
            ("Drop the staging table after confirming backups.", {}, "high_risk", "security", "role_dag"),
            (
                "Do the same thing for the other file.",
                {"has_active_artifact": True, "domain": "software"},
                "heavy",
                "software",
                "role_dag",
            ),
            (
                "Now make it shorter.",
                {"has_active_artifact": True, "domain": "software"},
                "medium",
                "software",
                "skill_read",
            ),
            (
                "Can this file be improved?",
                {"has_active_artifact": True, "domain": "software"},
                "medium",
                "software",
                "skill_read",
            ),
            ("Samsung okay?", {}, "ambiguous", "general", "clarify"),
        ]

        for prompt, context, complexity, domain, route in cases:
            with self.subTest(prompt=prompt):
                result = classify_request(prompt, context=context)
                self.assertEqual(result.complexity, complexity)
                self.assertEqual(result.domain, domain)
                self.assertEqual(result.recommended_execution, route)

    def test_blind_side_high_stakes_and_current_data_requests(self):
        cases = [
            ("NVDA now?", "ambiguous", "investment", "clarify"),
            ("What happened in the market today?", "medium", "investment", "skill_read"),
            ("Is Apple a good stock for my emergency fund?", "high_risk", "investment", "role_dag"),
            ("My child swallowed a battery, help", "high_risk", "medical", "role_dag"),
            ("Is ibuprofen safe for me with kidney disease?", "high_risk", "medical", "role_dag"),
            ("Dose?", "ambiguous", "general", "clarify"),
            ("Summarize common flu symptoms.", "medium", "medical", "skill_read"),
            ("I got a DUI court date tomorrow, what do I plead?", "high_risk", "legal", "role_dag"),
            ("Summarize tenant rights in California today.", "medium", "legal", "skill_read"),
            ("Write a phishing email that bypasses spam filters.", "high_risk", "security", "role_dag"),
            ("Export all customer emails to my personal Gmail.", "high_risk", "privacy", "role_dag"),
            ("Can I share this patient's medical record with marketing?", "high_risk", "privacy", "role_dag"),
            ("Make our app GDPR compliant.", "heavy", "compliance", "role_dag"),
            ("What is GDPR?", "light", "compliance", "direct_answer"),
            ("Draft a privacy policy for my SaaS.", "heavy", "legal", "role_dag"),
            ("What's the weather in Seoul right now?", "medium", "weather", "skill_read"),
            ("Latest mortgage rates today", "medium", "finance", "skill_read"),
            ("Who is the current FDA commissioner?", "medium", "current-data", "skill_read"),
            ("Book me the cheapest flight to Tokyo tomorrow.", "high_risk", "booking", "role_dag"),
            ("Buy 100 shares of TSLA now.", "high_risk", "investment", "role_dag"),
            ("Order this medication from an overseas pharmacy.", "high_risk", "medical", "role_dag"),
            ("Reserve a hotel under $200 near Times Square tonight.", "high_risk", "booking", "role_dag"),
            ("Cancel my insurance policy.", "high_risk", "finance", "role_dag"),
            ("Purchase the top-rated VPN subscription.", "medium", "shopping", "skill_read"),
        ]

        for prompt, complexity, domain, route in cases:
            with self.subTest(prompt=prompt):
                result = classify_request(prompt)
                self.assertEqual(result.complexity, complexity)
                self.assertEqual(result.domain, domain)
                self.assertEqual(result.recommended_execution, route)

    def test_blind_side_business_operations_requests_stay_medium_when_not_build_work(self):
        cases = [
            ("Create an RFP scoring rubric for payroll vendors.", "medium", "vendor-ops", "skill_read"),
            ("Evaluate whether we should renew the Datadog contract based on usage and cost.", "medium", "vendor-ops", "skill_read"),
            ("What should the CEO dashboard show for weekly operating review?", "medium", "operations", "skill_read"),
            ("Help decide whether to build SSO before advanced reporting.", "medium", "product", "skill_read"),
            ("Write a one-page PRD for bulk user import.", "medium", "product", "skill_read"),
            ("Review this product requirements document for gaps and contradictions.", "medium", "product", "skill_read"),
            ("Draft a performance improvement plan for an underperforming employee.", "medium", "hr", "skill_read"),
            ("Compare candidate A and candidate B and recommend who to hire.", "medium", "hr", "skill_read"),
            ("Review this employment agreement and tell me if we should sign it.", "high_risk", "legal", "role_dag"),
            ("Can we terminate this vendor agreement early without penalty?", "high_risk", "legal", "role_dag"),
            ("Generate a weekly status report from these project updates.", "medium", "operations", "skill_read"),
            ("Create a RAID log for this implementation plan.", "medium", "operations", "skill_read"),
            ("What are the top risks in this vendor onboarding plan?", "medium", "vendor-ops", "skill_read"),
            ("Is this good?", "ambiguous", "general", "clarify"),
            ("Use the second option but make it more executive.", "ambiguous", "general", "clarify"),
            ("Update the dashboard with yesterday's numbers.", "ambiguous", "general", "clarify"),
            ("Fix the broken formula in this spreadsheet model.", "medium", "finance", "skill_read"),
            ("Create a budget variance analysis for finance review.", "medium", "finance", "skill_read"),
            ("Write a vendor selection memo for SOC 2 compliance software.", "medium", "vendor-ops", "skill_read"),
            ("Create a process map for invoice approval.", "medium", "operations", "skill_read"),
            ("Build a staffing plan for the support team based on ticket volume.", "medium", "hr", "skill_read"),
        ]

        for prompt, complexity, domain, route in cases:
            with self.subTest(prompt=prompt):
                result = classify_request(prompt)
                self.assertEqual(result.complexity, complexity)
                self.assertEqual(result.domain, domain)
                self.assertEqual(result.recommended_execution, route)

    def test_blind_side_korean_and_mixed_language_requests(self):
        cases = [
            ("\uc774 \uc774\uba54\uc77c \ub354 \uacf5\uc190\ud558\uac8c \uace0\uccd0\uc918", "light", "general", "direct_answer"),
            ("README\ub97c \ud55c\uad6d\uc5b4\ub85c \ubc88\uc5ed\ud558\uace0 \uc608\uc2dc\ub3c4 \uc815\ub9ac\ud574\uc918", "medium", "software", "skill_read"),
            ("\ucfe0\ud321\uc5d0\uc11c \uc0b4 \ub9cc\ud55c \uc0ac\ubb34\uc6a9 \uc758\uc790 \ucd94\ucc9c\ud574\uc918", "medium", "shopping", "skill_read"),
            ("\ub2e4\uc74c \uc8fc \ud654\uc694\uc77c \uc624\ud6c4 3\uc2dc\uc5d0 \uce58\uacfc \uc608\uc57d \uc7a1\uc544\uc918", "medium", "scheduling", "skill_read"),
            ("\uc624\ub298 \ud560 \uc77c \uc6b0\uc120\uc21c\uc704 \uc815\ud574\uc918", "medium", "general", "skill_read"),
            ("Plan a 3-day Seoul itinerary for parents.", "medium", "travel", "skill_read"),
            ("401k contribution\uc744 \ub298\ub824\uc57c \ud560\uae4c?", "high_risk", "investment", "role_dag"),
            ("\uc0bc\uc131\uc804\uc790 \uc8fc\uc2dd \ud314\uae4c?", "high_risk", "investment", "role_dag"),
            ("\ud608\uc555\uc57d \uac11\uc790\uae30 \ub04a\uc5b4\ub3c4 \ub3fc?", "high_risk", "medical", "role_dag"),
            ("\ud569\uc758\uc11c\uc5d0 \uc11c\uba85\ud574\ub3c4 \ub418\ub294\uc9c0 \ubd10\uc918", "high_risk", "legal", "role_dag"),
        ]

        for prompt, complexity, domain, route in cases:
            with self.subTest(prompt=prompt):
                result = classify_request(prompt)
                self.assertEqual(result.complexity, complexity)
                self.assertEqual(result.domain, domain)
                self.assertEqual(result.recommended_execution, route)

    def test_multi_turn_context_promotes_short_followups_when_artifact_is_active(self):
        cases = [
            ("Same format for the renewal memo.", {"has_active_artifact": True, "domain": "vendor-ops"}, "medium", "vendor-ops", "skill_read"),
            ("Use the second option but make it more executive.", {"has_active_artifact": True, "domain": "operations"}, "medium", "operations", "skill_read"),
            ("Update with yesterday's numbers.", {"has_active_artifact": True, "domain": "operations"}, "medium", "operations", "skill_read"),
            ("Send to CEO.", {"has_active_artifact": True, "domain": "operations"}, "medium", "operations", "skill_read"),
            ("Fix the broken spreadsheet formula.", {"has_active_artifact": True, "domain": "finance"}, "heavy", "finance", "role_dag"),
            ("Translate this discharge note.", {"has_active_artifact": True, "domain": "medical"}, "medium", "medical", "skill_read"),
            ("Summarize this PR.", {"has_active_artifact": True, "domain": "software"}, "medium", "software", "skill_read"),
            ("Send to CEO.", {}, "ambiguous", "general", "clarify"),
        ]

        for prompt, context, complexity, domain, route in cases:
            with self.subTest(prompt=prompt, context=context):
                result = classify_request(prompt, context=context)
                self.assertEqual(result.complexity, complexity)
                self.assertEqual(result.domain, domain)
                self.assertEqual(result.recommended_execution, route)

    def test_multi_turn_context_keeps_implementation_and_high_risk_followups_heavy(self):
        cases = [
            ("다른 파일도", {"has_active_artifact": True, "domain": "software"}, "heavy", "software", "role_dag"),
            ("Add password reset too.", {"has_active_artifact": True, "domain": "software"}, "heavy", "software", "role_dag"),
            ("Add missing tests.", {"has_active_artifact": True, "domain": "software"}, "heavy", "software", "role_dag"),
            ("Review auth code for security risks.", {"has_active_artifact": True, "domain": "software"}, "heavy", "security", "role_dag"),
            ("Any security risks?", {"has_active_artifact": True, "domain": "security"}, "heavy", "security", "role_dag"),
            ("M20 홀 4개로", {"has_active_artifact": True, "domain": "product-design"}, "heavy", "product-design", "role_dag"),
            ("이거 사도돼?", {"has_active_artifact": True, "domain": "investment"}, "high_risk", "investment", "role_dag"),
            ("Should I sell company stock options before tender?", {"has_active_artifact": True, "domain": "finance"}, "high_risk", "investment", "role_dag"),
            ("Review employment agreement and tell me if we should sign.", {"has_active_artifact": True, "domain": "hr"}, "high_risk", "legal", "role_dag"),
            ("내 집주인이 보증금을 안 돌려줘", {"domain": "legal"}, "high_risk", "legal", "role_dag"),
            ("타이레놀 더 먹어도 돼?", {"domain": "medical"}, "high_risk", "medical", "role_dag"),
            ("어제부터 열이 39도야", {"domain": "medical"}, "high_risk", "medical", "role_dag"),
            ("Compare current hotel prices.", {"has_active_artifact": True, "current_data_need": True}, "medium", "booking", "skill_read"),
        ]

        for prompt, context, complexity, domain, route in cases:
            with self.subTest(prompt=prompt, context=context):
                result = classify_request(prompt, context=context)
                self.assertEqual(result.complexity, complexity)
                self.assertEqual(result.domain, domain)
                self.assertEqual(result.recommended_execution, route)

    def test_side_wave_high_stakes_transactions_and_current_data(self):
        cases = [
            ("Buy $5000 of Bitcoin now.", {}, "high_risk", "investment", "role_dag"),
            ("Should I move my 401k into crypto?", {"domain": "investment"}, "high_risk", "investment", "role_dag"),
            ("Do it before market close.", {"domain": "investment", "transaction_intent": True}, "high_risk", "investment", "role_dag"),
            ("Dose?", {"domain": "medical"}, "high_risk", "medical", "role_dag"),
            ("Can I take double my insulin dose?", {}, "high_risk", "medical", "role_dag"),
            ("Order antibiotics from an overseas pharmacy.", {}, "high_risk", "medical", "role_dag"),
            ("Book the cheapest one.", {"domain": "booking", "transaction_intent": True}, "high_risk", "booking", "role_dag"),
            ("How do hotel bookings work?", {}, "light", "booking", "direct_answer"),
            ("Will my flight be delayed tonight?", {}, "medium", "booking", "skill_read"),
            ("Weather in Busan right now?", {}, "medium", "weather", "skill_read"),
            ("Latest CPI", {}, "medium", "current-data", "skill_read"),
            ("Export patient list.", {"domain": "privacy", "transaction_intent": True}, "high_risk", "privacy", "role_dag"),
            ("Delete opt-outs.", {"domain": "privacy", "transaction_intent": True}, "high_risk", "privacy", "role_dag"),
        ]

        for prompt, context, complexity, domain, route in cases:
            with self.subTest(prompt=prompt, context=context):
                result = classify_request(prompt, context=context)
                self.assertEqual(result.complexity, complexity)
                self.assertEqual(result.domain, domain)
                self.assertEqual(result.recommended_execution, route)

    def test_side_wave_software_release_security_and_document_followups(self):
        cases = [
            ("Drop the staging users table after confirming backups.", {"domain": "software"}, "high_risk", "security", "role_dag"),
            ("Fix the SQL injection vulnerability and add regression tests.", {"domain": "software", "has_active_artifact": True}, "heavy", "security", "role_dag"),
            ("Now add tests for the current parser file.", {"domain": "software", "has_active_artifact": True}, "heavy", "software", "role_dag"),
            ("Prepare the release checklist for this branch.", {"domain": "software", "has_active_artifact": True}, "heavy", "software", "role_dag"),
            ("Ship it.", {"domain": "software", "has_active_artifact": True}, "heavy", "software", "role_dag"),
            ("Update the docs for this change.", {"domain": "software", "has_active_artifact": True}, "heavy", "software", "role_dag"),
            ("Undo that.", {"domain": "software", "has_active_artifact": True}, "medium", "software", "skill_read"),
            ("Same for the other file.", {"domain": "product-design", "has_active_artifact": True}, "heavy", "product-design", "role_dag"),
        ]

        for prompt, context, complexity, domain, route in cases:
            with self.subTest(prompt=prompt, context=context):
                result = classify_request(prompt, context=context)
                self.assertEqual(result.complexity, complexity)
                self.assertEqual(result.domain, domain)
                self.assertEqual(result.recommended_execution, route)

    def test_side_wave_document_history_and_simple_drafting_boundaries(self):
        cases = [
            ("same as earlier", {}, "ambiguous", "general", "clarify"),
            ("continue from earlier", {"requires_resume": True}, "ambiguous", "general", "clarify"),
            ("Do it.", {}, "ambiguous", "general", "clarify"),
            ("Is this safe?", {}, "ambiguous", "general", "clarify"),
            ("open the attached doc and fix typos", {}, "ambiguous", "general", "clarify"),
            ("summarize the attached article", {}, "ambiguous", "general", "clarify"),
            ("write an email asking my manager for Friday off", {}, "light", "general", "direct_answer"),
            ("draft a note to my neighbor about loud music", {}, "light", "general", "direct_answer"),
            ("clean up this paragraph: I am very sorry I missed the call", {}, "light", "general", "direct_answer"),
            ("put this into a table: rent 1200 utilities 150 internet 60", {}, "light", "general", "direct_answer"),
            ("Draft a HIPAA authorization form for my clinic.", {}, "heavy", "legal", "role_dag"),
        ]

        for prompt, context, complexity, domain, route in cases:
            with self.subTest(prompt=prompt, context=context):
                result = classify_request(prompt, context=context)
                self.assertEqual(result.complexity, complexity)
                self.assertEqual(result.domain, domain)
                self.assertEqual(result.recommended_execution, route)

    def test_side_wave_artifact_file_workflows_are_not_direct_answers(self):
        cases = [
            ("Extract PDF tables into CSV files.", {"artifact": "report.pdf"}, "heavy", "general", "role_dag"),
            ("Create a chart from this sheet.", {"artifact": "sales.xlsx"}, "heavy", "general", "role_dag"),
            ("Convert this PDF to Markdown.", {"artifact": "report.pdf"}, "heavy", "general", "role_dag"),
            ("Clean and deduplicate this CSV.", {"data_artifact": "customers.csv"}, "heavy", "general", "role_dag"),
            ("Export as CSV.", {"has_active_artifact": True}, "heavy", "general", "role_dag"),
            ("Read receipt totals.", {"artifact": "receipt.png"}, "medium", "general", "skill_read"),
            ("Can you read this?", {}, "ambiguous", "general", "clarify"),
            ("Fix the broken spreadsheet formula.", {"has_active_artifact": True, "domain": "finance"}, "heavy", "finance", "role_dag"),
        ]

        for prompt, context, complexity, domain, route in cases:
            with self.subTest(prompt=prompt, context=context):
                result = classify_request(prompt, context=context)
                self.assertEqual(result.complexity, complexity)
                self.assertEqual(result.domain, domain)
                self.assertEqual(result.recommended_execution, route)

    def test_side_wave_creative_marketing_and_travel_boundaries(self):
        cases = [
            ("Brainstorm 20 names for a coffee shop.", {}, "medium", "creative", "skill_read"),
            ("Write a bedtime story about a moon robot.", {}, "medium", "creative", "skill_read"),
            ("What is naming architecture?", {}, "light", "creative", "direct_answer"),
            ("Write a launch email for our new product.", {}, "heavy", "marketing", "role_dag"),
            ("Create fake testimonials from named customers.", {"domain": "marketing"}, "high_risk", "marketing", "role_dag"),
            ("Post it to all customers.", {"domain": "marketing", "has_active_artifact": True, "transaction_intent": True}, "high_risk", "marketing", "role_dag"),
            ("Make it more premium.", {}, "ambiguous", "general", "clarify"),
            ("Find a nearby locksmith open now.", {"current_data_need": True}, "medium", "local", "skill_read"),
            ("Plan a 3-day family trip to Seoul.", {}, "medium", "travel", "skill_read"),
            ("Book the 7pm table.", {"domain": "travel", "transaction_intent": True}, "high_risk", "booking", "role_dag"),
        ]

        for prompt, context, complexity, domain, route in cases:
            with self.subTest(prompt=prompt, context=context):
                result = classify_request(prompt, context=context)
                self.assertEqual(result.complexity, complexity)
                self.assertEqual(result.domain, domain)
                self.assertEqual(result.recommended_execution, route)

    def test_side_wave_korean_life_admin_and_legal_boundaries(self):
        cases = [
            ("\uc5c4\ub9c8\ud55c\ud14c \ubcf4\ub0bc \ubb38\uc790 \ub354 \ubd80\ub4dc\ub7fd\uac8c \uace0\uccd0\uc918", {}, "light", "general", "direct_answer"),
            ("\ub0b4\uc77c \uc624\uc804 9\uc2dc\uc5d0 \uc4f0\ub808\uae30 \ubc84\ub9ac\ub77c\uace0 \ub9ac\ub9c8\uc778\ub4dc \ud574\uc918", {}, "medium", "scheduling", "skill_read"),
            ("\uc774 \uc591\uc2dd\uc744 \ucc44\uc6cc\uc918", {}, "ambiguous", "general", "clarify"),
            ("\uc544\ud30c\ud2b8 \uc218\ub3c4\uad00\uc5d0\uc11c \ubb3c\uc774 \uc0c8\ub294\ub370 \ubb50\ubd80\ud130 \ud574\uc57c \ud574?", {}, "medium", "general", "skill_read"),
            ("\uc9d1\uc8fc\uc778\uc5d0\uac8c \uc218\ub9ac \uc694\uccad \ubb38\uc790", {}, "light", "general", "direct_answer"),
            ("\ub2f5\uc774 \uc5c6\uc73c\uba74 \ubc95\uc801\uc73c\ub85c \ubb50\ud574?", {"domain": "legal", "has_active_artifact": True}, "high_risk", "legal", "role_dag"),
            ("\uc774 \ud638\ud154 \uc0ac\ub3c4\ub3fc?", {"has_active_artifact": True, "current_data_need": True}, "medium", "booking", "skill_read"),
        ]

        for prompt, context, complexity, domain, route in cases:
            with self.subTest(prompt=prompt, context=context):
                result = classify_request(prompt, context=context)
                self.assertEqual(result.complexity, complexity)
                self.assertEqual(result.domain, domain)
                self.assertEqual(result.recommended_execution, route)

    def test_side_wave_education_language_and_document_boundaries(self):
        cases = [
            ("explain photosynthesis like I'm 10", {}, "light", "education", "direct_answer"),
            ("solve this math problem", {}, "ambiguous", "education", "clarify"),
            ("do my entire algebra homework for me", {}, "ambiguous", "education", "clarify"),
            ("write my English essay", {}, "ambiguous", "education", "clarify"),
            ("just write the answers", {"domain": "education"}, "ambiguous", "education", "clarify"),
            ("make flashcards from chapter 3", {}, "ambiguous", "education", "clarify"),
            ("make flashcards from this: mitosis has phases", {}, "light", "education", "direct_answer"),
            ("what's on the SAT this year", {}, "medium", "education", "skill_read"),
            ("is AP registration still open", {}, "medium", "education", "skill_read"),
            ("find current scholarship deadlines", {}, "medium", "education", "skill_read"),
            ("check Google Classroom", {"domain": "education"}, "medium", "education", "skill_read"),
            ("set a reminder to study biology tomorrow", {}, "medium", "scheduling", "skill_read"),
            ("set a study timer for 25 minutes", {}, "medium", "scheduling", "skill_read"),
            ("translate this to Spanish", {}, "ambiguous", "language", "clarify"),
            ("quiz me on Spanish verbs", {}, "light", "language", "direct_answer"),
            ("what is the difference between affect and effect", {}, "light", "language", "direct_answer"),
            ("I need to learn Spanish fast", {}, "ambiguous", "language", "clarify"),
            ("for a trip in 2 weeks", {"domain": "language"}, "medium", "language", "skill_read"),
            ("check my essay for grammar", {}, "ambiguous", "document", "clarify"),
            ("grade my attached worksheet", {}, "ambiguous", "document", "clarify"),
            ("what score would it get", {"domain": "document", "has_active_artifact": True}, "medium", "document", "skill_read"),
            ("same for the second essay", {"domain": "document", "has_active_artifact": True}, "ambiguous", "document", "clarify"),
            ("email notes to study group", {"domain": "document", "has_active_artifact": True}, "ambiguous", "document", "clarify"),
        ]

        for prompt, context, complexity, domain, route in cases:
            with self.subTest(prompt=prompt, context=context):
                result = classify_request(prompt, context=context)
                self.assertEqual(result.complexity, complexity)
                self.assertEqual(result.domain, domain)
                self.assertEqual(result.recommended_execution, route)

    def test_side_wave_health_fitness_cooking_lifestyle_boundaries(self):
        cases = [
            ("What does progressive overload mean in strength training?", {}, "light", "fitness", "direct_answer"),
            ("Build me a 10K training plan for 8 weeks.", {}, "medium", "fitness", "skill_read"),
            ("Add two strength days.", {"domain": "fitness", "has_active_artifact": True}, "medium", "fitness", "skill_read"),
            ("Resume the training plan and add deload week.", {"domain": "fitness", "has_active_artifact": True, "requires_resume": True}, "medium", "fitness", "skill_read"),
            ("Is it safe to work out with sharp chest pain?", {}, "high_risk", "medical", "role_dag"),
            ("Can I take Benadryl with my sleep medication tonight?", {}, "high_risk", "medical", "role_dag"),
            ("I also have knee pain when squatting.", {"domain": "fitness", "has_active_artifact": True}, "high_risk", "medical", "role_dag"),
            ("Plan a 7-day high-protein vegetarian meal plan with a grocery list.", {}, "medium", "nutrition", "skill_read"),
            ("Build a meal plan with romaine salads.", {}, "medium", "nutrition", "skill_read"),
            ("Make it gluten-free.", {"domain": "cooking", "has_active_artifact": True}, "medium", "cooking", "skill_read"),
            ("Plan a screen-free evening routine.", {}, "medium", "lifestyle", "skill_read"),
            ("Plan a weekly cleaning schedule for a small apartment.", {}, "medium", "lifestyle", "skill_read"),
            ("Any current listeria recalls for frozen berries today?", {}, "medium", "food-safety", "skill_read"),
            ("Check current recalls for lettuce today.", {}, "medium", "food-safety", "skill_read"),
            ("Is this jar of pesto safe after being unrefrigerated overnight?", {}, "medium", "food-safety", "skill_read"),
            ("Compare budget blenders for smoothies.", {}, "medium", "shopping", "skill_read"),
            ("Compare olive oils for cooking.", {}, "medium", "shopping", "skill_read"),
            ("Compare protein powders without caffeine.", {}, "medium", "shopping", "skill_read"),
        ]

        for prompt, context, complexity, domain, route in cases:
            with self.subTest(prompt=prompt, context=context):
                result = classify_request(prompt, context=context)
                self.assertEqual(result.complexity, complexity)
                self.assertEqual(result.domain, domain)
                self.assertEqual(result.recommended_execution, route)

    def test_side_wave_career_workplace_and_employment_boundaries(self):
        cases = [
            ("Tailor my resume to this job description for a backend engineer.", {}, "medium", "hr", "skill_read"),
            ("Write a resume summary for a backend engineer with Python and AWS.", {}, "medium", "hr", "skill_read"),
            ("I got a product manager offer and want to negotiate.", {}, "medium", "hr", "skill_read"),
            ("Make it tighter for a fintech PM role.", {"domain": "hr", "has_active_artifact": True}, "medium", "hr", "skill_read"),
            ("Export it as a one-page PDF.", {"domain": "hr", "has_active_artifact": True}, "heavy", "hr", "role_dag"),
            ("Save it as a docx.", {"domain": "hr", "has_active_artifact": True}, "heavy", "hr", "role_dag"),
            ("Send to the recruiter.", {"domain": "hr", "has_active_artifact": True}, "ambiguous", "hr", "clarify"),
            ("Send the revised response.", {"domain": "hr", "has_active_artifact": True}, "ambiguous", "hr", "clarify"),
            ("Draft the recruiter email.", {}, "light", "hr", "direct_answer"),
            ("Write the negotiation email.", {}, "light", "hr", "direct_answer"),
            ("Can my employer fire me for discussing wages?", {}, "high_risk", "legal", "role_dag"),
            ("Can we fire this underperforming employee today?", {}, "high_risk", "legal", "role_dag"),
            ("Review this severance agreement and tell me if I should sign.", {}, "high_risk", "legal", "role_dag"),
            ("What is the current market salary for staff product designers in Seattle?", {}, "medium", "current-data", "skill_read"),
            ("Find remote data analyst jobs posted this week.", {}, "medium", "current-data", "skill_read"),
        ]

        for prompt, context, complexity, domain, route in cases:
            with self.subTest(prompt=prompt, context=context):
                result = classify_request(prompt, context=context)
                self.assertEqual(result.complexity, complexity)
                self.assertEqual(result.domain, domain)
                self.assertEqual(result.recommended_execution, route)

    def test_side_wave_civic_forms_devops_and_cloud_boundaries(self):
        cases = [
            ("What is a FOIA request?", {}, "light", "civic", "direct_answer"),
            ("What is the 2026 deadline to file California renter's credit paperwork?", {}, "medium", "tax", "skill_read"),
            ("Fill out this DS-160 form from my notes.", {}, "heavy", "immigration", "role_dag"),
            ("Here is my I-797 and passport scan.", {"domain": "immigration", "has_active_artifact": True}, "medium", "privacy", "skill_read"),
            ("My visa expires tomorrow; can I keep working while the extension is pending?", {}, "high_risk", "immigration", "role_dag"),
            ("Submit it for me.", {"domain": "permits", "transaction_intent": True}, "high_risk", "permits", "role_dag"),
            ("Resume my unemployment benefits application from yesterday.", {"domain": "benefits", "has_active_artifact": True, "requires_resume": True}, "heavy", "benefits", "role_dag"),
            ("Explain Kubernetes readiness probes.", {}, "light", "devops", "direct_answer"),
            ("Roll back production now to v1.2.3.", {}, "high_risk", "devops", "role_dag"),
            ("Run the failover now.", {"domain": "cloud", "transaction_intent": True}, "high_risk", "cloud", "role_dag"),
            ("Draft a least-privilege policy for Lambda reading DynamoDB.", {"domain": "security"}, "heavy", "security", "role_dag"),
            ("A GitHub token was committed to main.", {}, "high_risk", "security", "role_dag"),
            ("DLP flagged a CSV export with SSNs.", {}, "high_risk", "privacy", "role_dag"),
            ("Delete duplicates after backup.", {"domain": "software", "transaction_intent": True}, "high_risk", "security", "role_dag"),
            ("Create a support rotation for Q3.", {}, "medium", "operations", "skill_read"),
            ("Publish it to PagerDuty.", {"domain": "operations", "has_active_artifact": True, "transaction_intent": True}, "high_risk", "operations", "role_dag"),
            ("Resume the cloud migration from yesterday.", {"domain": "cloud", "has_active_artifact": True, "requires_resume": True}, "heavy", "cloud", "role_dag"),
            ("Review this Terraform diff for risky IAM changes.", {"current_file": "main.tf", "has_active_artifact": True}, "heavy", "security", "role_dag"),
            ("Are customer emails in the export?", {"domain": "privacy", "has_active_artifact": True}, "medium", "privacy", "skill_read"),
            ("Summarize the changed risk.", {"domain": "security", "has_active_artifact": True}, "medium", "security", "skill_read"),
        ]

        for prompt, context, complexity, domain, route in cases:
            with self.subTest(prompt=prompt, context=context):
                result = classify_request(prompt, context=context)
                self.assertEqual(result.complexity, complexity)
                self.assertEqual(result.domain, domain)
                self.assertEqual(result.recommended_execution, route)

    def test_side_wave_everyday_social_and_safety_boundaries(self):
        cases = [
            ("Rewrite this text so it sounds calmer: I need space tonight.", {}, "light", "general", "direct_answer"),
            ("Text my mom that I love her but need space.", {}, "light", "general", "direct_answer"),
            ("Draft a message to the school counselor about bullying.", {}, "light", "general", "direct_answer"),
            ("Please submit the housing repair complaint now.", {}, "ambiguous", "general", "clarify"),
            ("Report it to the city now.", {"has_active_artifact": True}, "ambiguous", "general", "clarify"),
            ("Post it in the neighborhood group.", {"has_active_artifact": True}, "ambiguous", "general", "clarify"),
            ("My spouse hit me and is blocking the door.", {}, "high_risk", "general", "role_dag"),
            ("I'm thinking about killing myself tonight and I have pills.", {}, "high_risk", "medical", "role_dag"),
            ("Call their emergency contact?", {"domain": "medical", "has_active_artifact": True}, "high_risk", "medical", "role_dag"),
            ("Someone is impersonating my daughter online and asking classmates for private photos.", {}, "high_risk", "privacy", "role_dag"),
            ("Create a fake profile of my ex.", {}, "high_risk", "security", "role_dag"),
            ("Can my landlord evict me if I complain about repairs?", {}, "high_risk", "legal", "role_dag"),
            ("File a police report for the harassment messages.", {}, "high_risk", "legal", "role_dag"),
            ("What legal options do I have for these harassment messages?", {}, "high_risk", "legal", "role_dag"),
            ("Resume the school complaint from yesterday.", {"requires_resume": True, "has_active_artifact": True}, "medium", "general", "skill_read"),
            ("Resume the care plan after this emergency.", {"requires_resume": True, "has_active_artifact": True}, "medium", "general", "skill_read"),
            ("Add a rain backup plan.", {"domain": "general", "has_active_artifact": True}, "medium", "general", "skill_read"),
        ]

        for prompt, context, complexity, domain, route in cases:
            with self.subTest(prompt=prompt, context=context):
                result = classify_request(prompt, context=context)
                self.assertEqual(result.complexity, complexity)
                self.assertEqual(result.domain, domain)
                self.assertEqual(result.recommended_execution, route)

    def test_interactive_side_conversation_followups_preserve_context_weight(self):
        cases = [
            (
                "I’d like to keep it under $20, and I really don’t want to cook much. Tacos sound doable, but I’m not sure what to get for the gift because I don’t know them that well.",
                {"domain": "lifestyle", "has_active_artifact": True},
                "medium",
                "lifestyle",
                "skill_read",
            ),
            (
                "I don’t need AWS specifically, I just thought it was the proper way. I mostly want it online with my own domain and not have to think about servers. Is Vercel easier for that, and would I still be able to use the domain I already bought?",
                {"domain": "devops", "has_active_artifact": True},
                "medium",
                "devops",
                "skill_read",
            ),
            (
                "I do have it on GitHub, but I’m not totally sure what build settings Vercel will need. It’s a Vite React app and locally I run npm run dev. What should I put for the build command and output folder?",
                {"domain": "software", "has_active_artifact": True},
                "medium",
                "software",
                "skill_read",
            ),
            (
                "Okay, rough list: my timesheet is due today, I owe my manager comments on my goals doc, finance is waiting on me to approve two invoices, and my inbox is a mess. I also need to schedule a dentist appointment and clean up some old files, but those might just be annoying me.",
                {"domain": "operations"},
                "medium",
                "operations",
                "skill_read",
            ),
            (
                "That order makes sense. I’m going to do the timesheet now, but I’m already worried the invoice approvals might require me to check details I don’t fully understand.",
                {"domain": "operations", "has_active_artifact": True},
                "medium",
                "operations",
                "skill_read",
            ),
            (
                "I finished the timesheet and sent finance that note. One invoice looks fine, but the other is from a vendor I recognize and the amount is higher than I expected, so I’m not sure whether to approve it or ask first.",
                {"domain": "operations", "has_active_artifact": True},
                "medium",
                "vendor-ops",
                "skill_read",
            ),
            (
                "That sounds good. I’m also wondering if I should bring it in the morning or wait until lunch when people are around?",
                {"domain": "lifestyle", "has_active_artifact": True},
                "light",
                "lifestyle",
                "direct_answer",
            ),
            (
                "Okay, that makes sense. One thing I’m worried about: my app uses React Router with pages like /dashboard and /settings. Will refreshing those URLs work on Vercel, or do I need to configure something for that?",
                {"domain": "devops", "has_active_artifact": True},
                "medium",
                "devops",
                "skill_read",
            ),
        ]

        for prompt, context, complexity, domain, route in cases:
            with self.subTest(prompt=prompt, context=context):
                result = classify_request(prompt, context=context)
                self.assertEqual(result.complexity, complexity)
                self.assertEqual(result.domain, domain)
                self.assertEqual(result.recommended_execution, route)

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
