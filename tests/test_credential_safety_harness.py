import unittest

from src.skills.credential_safety import (
    CredentialSafetyPlan,
    build_credential_safety_plan,
    classify_credential_command,
    normalize_credential_name,
    validate_credential_safety_plan,
)


class CredentialSafetyHarnessTests(unittest.TestCase):
    def test_build_powershell_plan_checks_presence_without_printing_secret(self):
        plan = build_credential_safety_plan(
            "ncbi_api_key",
            env_file="C:\\Users\\User\\.env",
            platform="powershell",
        )

        self.assertEqual(plan.credential_name, "NCBI_API_KEY")
        self.assertIn("Select-String", plan.check_command)
        self.assertIn("-Quiet", plan.check_command)
        self.assertNotIn("Get-Content", plan.check_command)
        self.assertNotIn("echo $env:NCBI_API_KEY", plan.check_command)
        validation = validate_credential_safety_plan(plan)
        self.assertTrue(validation["valid"], validation)
        self.assertEqual(validation["check_command_verdict"]["verdict"], "safe_presence_check")

    def test_secret_read_commands_are_blocked(self):
        commands = [
            "cat ~/.env",
            "Get-Content $HOME\\.env",
            "echo $env:OPENAI_API_KEY",
            "printenv OPENAI_API_KEY",
            "Write-Output $env:OPENAI_API_KEY",
            "Write-Host $env:OPENAI_API_KEY",
            "Get-ChildItem Env:OPENAI_API_KEY",
            "Select-String -LiteralPath ~/.env -Pattern '^OPENAI_API_KEY='",
            "python -c \"import os; print(os.environ['OPENAI_API_KEY'])\"",
            "node -e \"console.log(process.env.OPENAI_API_KEY)\"",
            "cmd /c echo %OPENAI_API_KEY%",
            "cmd /c echo %GITHUB_TOKEN%",
            "cmd /c set OPENAI_API_KEY",
            "echo %NCBI_API_KEY%",
            "echo ${OPENAI_API_KEY}",
        ]

        for command in commands:
            with self.subTest(command=command):
                verdict = classify_credential_command(command)
                self.assertFalse(verdict["allowed"], verdict)
                self.assertEqual(verdict["verdict"], "unsafe_secret_exposure")

    def test_invalid_credential_name_rejects_shell_injection(self):
        with self.assertRaises(ValueError):
            normalize_credential_name("TOKEN; Get-Content ~/.env")

    def test_env_file_rejects_shell_expansion_and_quote_injection(self):
        unsafe_paths = [
            "x'$(Write-Host LEAK)'",
            "~/.env; Get-Content ~/.env",
            "$HOME/.env",
            "~/my*.env",
        ]

        for unsafe_path in unsafe_paths:
            with self.subTest(unsafe_path=unsafe_path):
                with self.assertRaises(ValueError):
                    build_credential_safety_plan("OPENAI_API_KEY", env_file=unsafe_path)

    def test_plan_roundtrip_preserves_contract_fields(self):
        plan = build_credential_safety_plan("SQL_CONNECTION_STRING")

        restored = CredentialSafetyPlan.from_dict(plan.to_dict())

        self.assertEqual(restored.to_dict(), plan.to_dict())

    def test_bash_presence_check_is_allowed(self):
        plan = build_credential_safety_plan("OPENAI_API_KEY", env_file="~/.env", platform="bash")

        self.assertIn("grep -sq", plan.check_command)
        self.assertTrue(validate_credential_safety_plan(plan)["valid"])

    def test_standalone_quiet_presence_checks_are_allowed(self):
        commands = [
            "Select-String -LiteralPath ~/.env -Pattern '^OPENAI_API_KEY=' -Quiet",
            "grep -sq '^OPENAI_API_KEY=' ~/.env",
            "Test-Path -LiteralPath ~/.env",
        ]

        for command in commands:
            with self.subTest(command=command):
                verdict = classify_credential_command(command)
                self.assertTrue(verdict["allowed"], verdict)
                self.assertEqual(verdict["verdict"], "safe_presence_check")


if __name__ == "__main__":
    unittest.main()
