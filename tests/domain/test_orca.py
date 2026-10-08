from __future__ import annotations

import os
import hashlib
import json
import struct
import subprocess
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from src.pb.orca import (
    FALLBACK_ORDER,
    OrcaRequest,
    OrcaVersionConfig,
    PbOrcaRuntime,
    X86_PE_MACHINE,
    bundled_tool_root,
    default_version_configs,
    helper_matches_bundle,
    read_pe_machine,
)


def write_fake_pe(path: Path, machine: int = X86_PE_MACHINE) -> None:
    payload = bytearray(0x90)
    payload[0:2] = b"MZ"
    struct.pack_into("<I", payload, 0x3C, 0x80)
    payload[0x80:0x84] = b"PE\x00\x00"
    struct.pack_into("<H", payload, 0x84, machine)
    path.write_bytes(payload)


class RecordingRunner:
    def __init__(self, returncode: int = 0) -> None:
        self.returncode = returncode
        self.calls: list[tuple[list[str], dict[str, object]]] = []
        self.input_existed_during_call: bool | None = None

    def __call__(self, command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        command_copy = list(command)
        self.calls.append((command_copy, dict(kwargs)))
        if "-PblPath" in command_copy:
            pbl_index = command_copy.index("-PblPath") + 1
            self.input_existed_during_call = Path(command_copy[pbl_index]).is_file()
        if self.returncode == 0 and '-OutputDirectory' in command_copy:
            output = Path(command_copy[command_copy.index('-OutputDirectory') + 1])
            output.mkdir(parents=True, exist_ok=True)
            name = 'object-' + command_copy[command_copy.index('-Version') + 1] + '.srw'
            (output / name).write_text('global type w_test from window\nend type', encoding='utf-8')
        return subprocess.CompletedProcess(
            command_copy,
            self.returncode,
            stdout="fake stdout",
            stderr="fake stderr" if self.returncode else "",
        )


class PbOrcaRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.tool_root = self.root / "Pbl Scripter"
        self.tool_root.mkdir()
        (self.tool_root / "Export-PBL.ps1").write_text("# fake", encoding="utf-8")
        write_fake_pe(self.tool_root / "PblExporter.exe")

        self.input_directory = self.root / "입력 폴더"
        self.input_directory.mkdir()
        self.pbl_path = self.input_directory / "sample library.pbl"
        self.pbl_path.write_bytes(b"fake-pbl")
        self.output_directory = self.root / "결과 폴더"

        self.configs: dict[str, OrcaVersionConfig] = {}
        for version, api_mode in (("70", "ansi"), ("105", "unicode"), ("125", "unicode")):
            runtime_directory = self.root / f"runtime {version}"
            runtime_directory.mkdir()
            orca_dll = runtime_directory / f"PBORC{version}.DLL"
            runtime_dll = runtime_directory / f"PBVM{version}.DLL"
            orca_dll.write_bytes(b"orca")
            runtime_dll.write_bytes(b"runtime")
            self.configs[version] = OrcaVersionConfig(
                version=version,
                orca_dll=orca_dll,
                runtime_directories=(runtime_directory,),
                runtime_dll_names=(runtime_dll.name,),
                api_mode=api_mode,
            )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def request(
        self,
        version: str | None,
        *,
        action: str = "exportall",
        object_name: str | None = None,
        pbl_path: Path | None = None,
        ascii_stage_root: Path | None = None,
    ) -> OrcaRequest:
        return OrcaRequest(
            tool_root=self.tool_root,
            version=version,
            pbl_path=pbl_path or self.pbl_path,
            action=action,
            object_name=object_name,
            output_directory=self.output_directory,
            ascii_stage_root=ascii_stage_root,
        )

    def runtime(
        self,
        runner: RecordingRunner,
        *,
        ansi_encoding: str = "cp949",
        csc_candidates: tuple[Path, ...] = (),
    ) -> PbOrcaRuntime:
        return PbOrcaRuntime(
            version_configs=self.configs,
            process_runner=runner,
            base_environment={"PATH": "C:\\base-path", "KEEP": "yes"},
            powershell_executable="fake-powershell.exe",
            ansi_encoding=ansi_encoding,
            csc_candidates=csc_candidates,
        )

    def test_read_pe_machine_identifies_x86_helper_without_execution(self) -> None:
        self.assertEqual(
            X86_PE_MACHINE,
            read_pe_machine(self.tool_root / "PblExporter.exe"),
        )

    def test_probe_executes_zero_processes_for_every_supported_version(self) -> None:
        runner = RecordingRunner()
        runtime = self.runtime(runner)

        for version in ("70", "105", "125"):
            with self.subTest(version=version):
                decision = runtime.probe(self.request(version))
                self.assertTrue(decision.ready)
                self.assertEqual(0, decision.executed_process_count)
                self.assertEqual(version, decision.selected_version)

        self.assertEqual([], runner.calls)

    def test_fresh_first_conversion_launches_once_per_selected_version(self) -> None:
        for version in ("70", "105", "125"):
            with self.subTest(version=version):
                runner = RecordingRunner()
                runtime = self.runtime(runner)

                result = runtime.convert(self.request(version))

                self.assertEqual("completed", result.status)
                self.assertEqual(1, len(runner.calls))
                command, options = runner.calls[0]
                self.assertEqual(
                    [
                        "fake-powershell.exe",
                        "-NoProfile",
                        "-ExecutionPolicy",
                        "Bypass",
                        "-File",
                    ],
                    command[:5],
                )
                self.assertEqual(version, command[command.index("-Version") + 1])
                child_path = str(options["env"]["PATH"])
                selected_runtime = str(self.configs[version].runtime_directories[0])
                self.assertTrue(child_path.startswith(selected_runtime + os.pathsep))
                for other_version, other_config in self.configs.items():
                    if other_version != version:
                        self.assertNotIn(str(other_config.runtime_directories[0]), child_path)

    def test_unknown_version_returns_structured_fallback_without_execution(self) -> None:
        runner = RecordingRunner()
        result = self.runtime(runner).convert(self.request("999"))

        self.assertEqual("fallback", result.status)
        self.assertEqual("version_not_selected_or_unsupported", result.reason_code)
        self.assertEqual(FALLBACK_ORDER, result.probe.fallback_order)
        self.assertFalse(result.executed)
        self.assertEqual([], runner.calls)

    def test_missing_tool_returns_structured_fallback_without_execution(self) -> None:
        (self.tool_root / "Export-PBL.ps1").unlink()
        runner = RecordingRunner()

        result = self.runtime(runner).convert(self.request("70"))

        self.assertEqual("fallback", result.status)
        self.assertEqual("tool_not_found", result.reason_code)
        self.assertEqual("", result.stderr)
        self.assertEqual([], runner.calls)

    def test_missing_runtime_dll_does_not_start_orca(self) -> None:
        runtime_dll = self.configs["105"].runtime_directories[0] / "PBVM105.DLL"
        runtime_dll.unlink()
        runner = RecordingRunner()

        result = self.runtime(runner).convert(self.request("105"))

        self.assertEqual("runtime_dll_not_found", result.reason_code)
        self.assertEqual([], runner.calls)

    def test_child_failure_exit_code_is_preserved(self) -> None:
        runner = RecordingRunner(returncode=37)

        result = self.runtime(runner).convert(self.request("125"))

        self.assertEqual("failed", result.status)
        self.assertEqual(37, result.exit_code)
        self.assertEqual("fake stderr", result.stderr)
        self.assertEqual(1, len(runner.calls))

    def test_spaces_and_korean_arguments_remain_distinct_array_items(self) -> None:
        runner = RecordingRunner()
        request = self.request(
            "125",
            action="export",
            object_name="d_품목 조회",
        )

        result = self.runtime(runner).convert(request)

        self.assertEqual("completed", result.status)
        command = runner.calls[0][0]
        self.assertEqual(str(self.pbl_path), command[command.index("-PblPath") + 1])
        self.assertEqual(
            str(self.output_directory),
            command[command.index("-OutputDirectory") + 1],
        )
        self.assertEqual("d_품목 조회", command[command.index("-ObjectName") + 1])
        self.assertNotIn('"' + str(self.pbl_path) + '"', command)

    def test_selected_path_and_conversion_share_one_child_environment(self) -> None:
        runner = RecordingRunner()
        result = self.runtime(runner).convert(self.request("105"))

        self.assertEqual(1, len(runner.calls))
        command, options = runner.calls[0]
        selected_runtime = str(self.configs["105"].runtime_directories[0])
        self.assertEqual((selected_runtime,), result.path_prefix)
        self.assertTrue(str(options["env"]["PATH"]).startswith(selected_runtime))
        self.assertEqual(
            selected_runtime,
            command[command.index("-RuntimePath") + 1],
        )

    def test_conversion_does_not_mutate_global_path(self) -> None:
        global_path_before = os.environ.get("PATH")
        runner = RecordingRunner()

        self.runtime(runner).convert(self.request("125"))

        self.assertEqual(global_path_before, os.environ.get("PATH"))
        self.assertEqual("yes", runner.calls[0][1]["env"]["KEEP"])
        self.assertEqual("utf-8", runner.calls[0][1]["encoding"])
        self.assertEqual("replace", runner.calls[0][1]["errors"])

    def test_pb7_korean_path_is_preserved_when_ansi_round_trip_is_lossless(self) -> None:
        runner = RecordingRunner()

        result = self.runtime(runner, ansi_encoding="cp949").convert(
            self.request("70")
        )

        self.assertFalse(result.staged_input)
        command = runner.calls[0][0]
        self.assertEqual(str(self.pbl_path), command[command.index("-PblPath") + 1])

    def test_pb7_stages_only_unrepresentable_pbl_path_in_ascii_temp(self) -> None:
        ascii_stage_root = self.root / "ascii-stage"
        ascii_stage_root.mkdir()
        runner = RecordingRunner()
        request = self.request(
            "70",
            ascii_stage_root=ascii_stage_root,
        )

        result = self.runtime(runner, ansi_encoding="cp1252").convert(request)

        self.assertEqual("completed", result.status)
        self.assertTrue(result.staged_input)
        self.assertTrue(runner.input_existed_during_call)
        command = runner.calls[0][0]
        staged_argument = command[command.index("-PblPath") + 1]
        self.assertTrue(staged_argument.isascii())
        self.assertNotEqual(str(self.pbl_path), staged_argument)
        self.assertEqual(
            str(self.output_directory),
            command[command.index("-OutputDirectory") + 1],
        )
        self.assertFalse(Path(staged_argument).exists())

    def test_pb7_unrepresentable_object_name_blocks_without_lossy_conversion(self) -> None:
        ascii_stage_root = self.root / "ascii-stage"
        ascii_stage_root.mkdir()
        runner = RecordingRunner()

        result = self.runtime(runner, ansi_encoding="cp1252").convert(
            self.request(
                "70",
                action="export",
                object_name="d_품목",
                ascii_stage_root=ascii_stage_root,
            )
        )

        self.assertEqual("fallback", result.status)
        self.assertEqual("object_name_not_ansi_representable", result.reason_code)
        self.assertEqual([], runner.calls)

    def test_wrong_architecture_helper_without_compiler_blocks_before_execution(self) -> None:
        write_fake_pe(self.tool_root / "PblExporter.exe", machine=0x8664)
        runner = RecordingRunner()

        result = self.runtime(runner, csc_candidates=()).convert(self.request("125"))

        self.assertEqual("x86_helper_unavailable", result.reason_code)
        self.assertEqual([], runner.calls)

    def test_exit_zero_failure_diagnostic_is_failure_even_with_export(self):
        class DiagnosticRunner(RecordingRunner):
            def __call__(self, command, **kwargs):
                result = super().__call__(command, **kwargs)
                result.stdout = 'PBORCA_LibraryEntryExport failed: license error'
                return result
        result = self.runtime(DiagnosticRunner()).convert(self.request('125'))
        self.assertEqual('failed', result.status)
        self.assertEqual('orca_failure_diagnostic', result.reason_code)
        self.assertEqual(0, result.exit_code)

    def test_exit_zero_without_new_output_is_incomplete(self):
        def runner(command, **kwargs):
            return subprocess.CompletedProcess(command, 0, stdout='done', stderr='')
        result = self.runtime(runner).convert(self.request('125'))
        self.assertEqual('incomplete', result.status)
        self.assertEqual('export_output_unconfirmed', result.reason_code)

    def test_conversion_without_output_directory_does_not_write_beside_pbl(self):
        from dataclasses import replace

        runner = RecordingRunner()
        runtime = self.runtime(runner)
        request = replace(self.request('125'), output_directory=None)

        probe = runtime.probe(request)
        self.assertTrue(probe.ready)
        self.assertIsNone(probe.to_dict()['output_directory'])

        result = runtime.convert(request)
        self.assertEqual('fallback', result.status)
        self.assertEqual('output_directory_required', result.reason_code)
        self.assertEqual([], runner.calls)
        self.assertFalse((self.input_directory / self.pbl_path.stem).exists())

    def test_stale_export_is_not_evidence_for_this_run(self):
        self.output_directory.mkdir()
        (self.output_directory / 'old.srw').write_text('global type old from window')
        def runner(command, **kwargs):
            return subprocess.CompletedProcess(command, 0, stdout='done', stderr='')
        result = self.runtime(runner).convert(self.request('125'))
        self.assertEqual('incomplete', result.status)

    def test_nonempty_garbage_export_is_not_reported_complete(self):
        def runner(command, **kwargs):
            self.output_directory.mkdir()
            (self.output_directory / 'bad.srw').write_bytes(b'not a PB export')
            return subprocess.CompletedProcess(command, 0, stdout='done', stderr='')
        self.assertEqual('incomplete', self.runtime(runner).convert(self.request('125')).status)

    def test_helper_compile_is_an_explicit_execution_choice(self):
        from dataclasses import replace
        (self.tool_root / 'PblExporter.exe').unlink()
        compiler = self.root / 'csc.exe'; compiler.write_bytes(b'fake compiler')
        runner = RecordingRunner()
        runtime = self.runtime(runner, csc_candidates=(compiler,))
        self.assertEqual('helper_compilation_needed', runtime.probe(self.request('125')).reason_code)
        self.assertEqual([], runner.calls)
        request = replace(self.request('125'), compile_helper=True)
        self.assertEqual('compile_x86', runtime.probe(request).helper_mode)

    def test_pbl_header_number_is_not_used_as_orca_version(self):
        self.pbl_path.write_bytes(b'0600')
        runner = RecordingRunner()
        decision = self.runtime(runner).probe(self.request(None))
        self.assertTrue(decision.ready)
        self.assertEqual(('125', '105', '70'), decision.candidate_versions)
        self.assertEqual([], runner.calls)

    def test_automatic_selection_retries_failed_version_and_publishes_only_success(self):
        class CompatibleRunner(RecordingRunner):
            def __call__(self, command, **kwargs):
                result = super().__call__(command, **kwargs)
                version = command[command.index('-Version') + 1]
                if version == '125':
                    result.returncode = 5
                    result.stderr = 'PBORCA_LibraryDirectory failed: bad library'
                return result

        runner = CompatibleRunner()
        original = self.pbl_path.read_bytes()
        result = self.runtime(runner).convert(self.request(None))
        self.assertEqual('completed', result.status)
        self.assertEqual('105', result.probe.selected_version)
        self.assertEqual(['125', '105'], [r.probe.selected_version for r in result.version_attempts])
        self.assertEqual({'object-105.srw'}, {p.name for p in self.output_directory.iterdir()})
        self.assertEqual(original, self.pbl_path.read_bytes())
        for command, _ in runner.calls:
            staged_path = Path(command[command.index('-PblPath') + 1])
            self.assertNotEqual(self.pbl_path, staged_path)
            self.assertFalse(staged_path.exists())

    def test_auto_checks_fresh_source_instead_of_exit_code_alone(self):
        class NoSourceFirstRunner(RecordingRunner):
            def __call__(self, command, **kwargs):
                result = super().__call__(command, **kwargs)
                if command[command.index('-Version') + 1] == '125':
                    output = Path(command[command.index('-OutputDirectory') + 1])
                    (output / 'object-125.srw').write_text('invalid export')
                return result
        result = self.runtime(NoSourceFirstRunner()).convert(self.request('auto'))
        self.assertEqual('105', result.probe.selected_version)
        self.assertEqual('incomplete', result.version_attempts[0].status)

    def test_auto_all_fail_leaves_requested_output_untouched_and_reports_attempts(self):
        self.output_directory.mkdir()
        existing = self.output_directory / 'existing.srw'
        existing.write_text('global type existing from window')
        result = self.runtime(RecordingRunner(returncode=37)).convert(self.request(None))
        self.assertEqual('no_compatible_runtime', result.reason_code)
        self.assertIsNone(result.probe.selected_version)
        self.assertEqual(37, result.exit_code)
        self.assertEqual(3, len(result.to_dict()['version_attempts']))
        self.assertEqual({'existing.srw'}, {p.name for p in self.output_directory.iterdir()})

    def test_auto_skips_missing_runtime_without_starting_it(self):
        self.configs['125'].orca_dll.unlink()
        runner = RecordingRunner()
        result = self.runtime(runner).convert(self.request(None))
        self.assertEqual('105', result.probe.selected_version)
        self.assertEqual(1, len(runner.calls))

    def test_auto_without_output_directory_does_not_execute(self):
        runner = RecordingRunner()
        result = self.runtime(runner).convert(replace(self.request(None), output_directory=None))
        self.assertEqual('output_directory_required', result.reason_code)
        self.assertEqual([], runner.calls)

    def test_bundle_hash_pair_survives_git_or_zip_timestamp_changes(self):
        hashes = {name: hashlib.sha256((self.tool_root / name).read_bytes()).hexdigest()
                  for name in ('Export-PBL.ps1', 'PblExporter.exe')}
        (self.tool_root / 'bundle.json').write_text(json.dumps({'sha256': hashes}))
        os.utime(self.tool_root / 'PblExporter.exe', (1, 1))
        self.assertTrue(self.runtime(RecordingRunner()).probe(self.request('125')).ready)
        (self.tool_root / 'Export-PBL.ps1').write_text('# changed source')
        self.assertEqual('x86_helper_unavailable', self.runtime(RecordingRunner()).probe(self.request('125')).reason_code)

    def test_mismatched_helper_hash_is_not_accepted_even_with_newer_timestamp(self):
        hashes = {name: hashlib.sha256((self.tool_root / name).read_bytes()).hexdigest()
                  for name in ('Export-PBL.ps1', 'PblExporter.exe')}
        (self.tool_root / 'bundle.json').write_text(json.dumps({'sha256': hashes}))
        with (self.tool_root / 'PblExporter.exe').open('ab') as helper:
            helper.write(b'changed')
        self.assertFalse(helper_matches_bundle(self.tool_root))
        self.assertEqual('x86_helper_unavailable', self.runtime(RecordingRunner()).probe(self.request('125')).reason_code)

    def test_helper_build_targets_temp_without_changing_exporter_directory(self):
        helper = self.tool_root / 'PblExporter.exe'
        original = helper.read_bytes()
        (self.tool_root / 'bundle.json').write_text('{"sha256": {}}')
        compiler = self.root / 'csc.exe'
        compiler.write_bytes(b'compiler')
        runner = RecordingRunner()
        result = self.runtime(runner, csc_candidates=(compiler,)).convert(
            replace(self.request('125'), compile_helper=True))
        self.assertEqual('completed', result.status)
        command = runner.calls[0][0]
        helper_path = Path(command[command.index('-HelperPath') + 1])
        self.assertFalse(helper_path.is_relative_to(self.tool_root))
        self.assertFalse(helper_path.parent.exists())
        self.assertEqual(original, helper.read_bytes())


class BundledExporterTests(unittest.TestCase):
    def test_shipped_exporter_is_matched_x86_pair(self):
        root = bundled_tool_root()
        self.assertTrue(helper_matches_bundle(root))
        self.assertEqual(X86_PE_MACHINE, read_pe_machine(root / 'PblExporter.exe'))

    def test_runtime_discovery_finds_matching_orca_and_vm_outside_standard_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'PBORC125.DLL').write_bytes(b'dll')
            (root / 'PBVM125.DLL').write_bytes(b'vm')
            real_is_file = Path.is_file
            with patch.dict(os.environ, {'PATH': str(root)}), patch(
                    'src.pb.orca.Path.is_file', autospec=True,
                    side_effect=lambda path: real_is_file(path) if path.is_relative_to(root) else False):
                config = default_version_configs()['125']
            self.assertEqual(root / 'PBORC125.DLL', config.orca_dll)
            self.assertEqual((root,), config.runtime_directories)


if __name__ == "__main__":
    unittest.main()
