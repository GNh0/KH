import ast
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from src.skills.pb_event_state_contract import (
    ISSUE_ARTIFACT_SHA256_MISMATCH,
    ISSUE_EDGE_DUPLICATE,
    ISSUE_GRAPH_INPUT_MISMATCH,
    ISSUE_NODE_DUPLICATE,
    ISSUE_NODE_INVENTED,
    ISSUE_NODE_OMITTED,
    ISSUE_ORDERING_DRIFT,
    ISSUE_TIMING_DRIFT,
    validate_pb_event_state_contract,
)


class PbEventStateContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.graph = {
            "nodes": [
                {
                    "id": "transition_a",
                    "order": 10,
                    "commands": ["command_a"],
                    "preconditions": ["ready_a"],
                    "state_mutations": ["state_a=1"],
                    "calls": ["call_a"],
                    "side_effects": ["effect_a"],
                    "timing": {"stage": "before_call"},
                },
                {
                    "id": "transition_b",
                    "order": 20,
                    "commands": ["command_b"],
                    "preconditions": ["ready_b"],
                    "state_mutations": ["state_b=1"],
                    "calls": ["call_b"],
                    "side_effects": ["effect_b"],
                    "timing": {"stage": "after_call"},
                },
            ],
            "edges": [
                {"id": "edge_a", "source": "transition_a", "target": "transition_b", "timing": "immediate"}
            ],
        }

    def tearDown(self):
        self.temp.cleanup()

    def _write_artifact(self, name, graph):
        path = self.root / name
        raw = json.dumps(graph, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        path.write_bytes(raw)
        return {
            "path": str(path),
            "sha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
            "graph_sha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
        }

    def _artifact(self, name, graph):
        path = self.root / name
        raw = json.dumps(graph, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        path.write_bytes(raw)
        graph_sha = "sha256:" + hashlib.sha256(raw).hexdigest()
        return {
            "path": str(path),
            "sha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
            "graph_sha256": graph_sha,
        }

    def test_exact_artifact_bound_graph_passes(self):
        pb = self._artifact("pb.json", self.graph)
        cs = self._artifact("cs.json", self.graph)
        result = validate_pb_event_state_contract(self.graph, self.graph, pb_artifact=pb, csharp_artifact=cs)
        self.assertTrue(result.success, result.to_dict())
        self.assertEqual(result.metadata["status"], "passed")
        self.assertEqual(result.exit_code, 0)

    def test_forged_file_sha_is_rejected(self):
        pb = self._artifact("pb.json", self.graph)
        cs = self._artifact("cs.json", self.graph)
        pb["sha256"] = "0" * 64
        result = validate_pb_event_state_contract(pb_artifact=pb, csharp_artifact=cs)
        self.assertFalse(result.success)
        self.assertIn(ISSUE_ARTIFACT_SHA256_MISMATCH, [item["code"] for item in result.metadata["issues"]])

    def test_caller_graph_json_cannot_override_artifact_graph(self):
        pb = self._artifact("pb.json", self.graph)
        cs = self._artifact("cs.json", self.graph)
        forged = json.loads(json.dumps(self.graph))
        forged["nodes"][0]["commands"] = ["invented_command"]
        result = validate_pb_event_state_contract(forged, self.graph, pb_artifact=pb, csharp_artifact=cs)
        self.assertIn(ISSUE_GRAPH_INPUT_MISMATCH, [item["code"] for item in result.metadata["issues"]])

    def test_omitted_and_invented_nodes_are_rejected(self):
        pb = self._artifact("pb.json", self.graph)
        changed = json.loads(json.dumps(self.graph))
        changed["nodes"] = [changed["nodes"][0], {"id": "invented_transition", "order": 30}]
        cs = self._artifact("cs.json", changed)
        result = validate_pb_event_state_contract(pb_artifact=pb, csharp_artifact=cs)
        codes = [item["code"] for item in result.metadata["issues"]]
        self.assertIn(ISSUE_NODE_OMITTED, codes)
        self.assertIn(ISSUE_NODE_INVENTED, codes)

    def test_duplicate_edge_is_rejected(self):
        duplicate = json.loads(json.dumps(self.graph))
        duplicate["edges"].append(dict(duplicate["edges"][0]))
        pb = self._artifact("pb.json", duplicate)
        cs = self._artifact("cs.json", duplicate)
        result = validate_pb_event_state_contract(pb_artifact=pb, csharp_artifact=cs)
        self.assertIn(ISSUE_EDGE_DUPLICATE, [item["code"] for item in result.metadata["issues"]])

    def test_duplicate_node_is_rejected(self):
        duplicate = json.loads(json.dumps(self.graph))
        duplicate["nodes"].append(dict(duplicate["nodes"][0]))
        pb = self._artifact("pb.json", duplicate)
        cs = self._artifact("cs.json", duplicate)
        result = validate_pb_event_state_contract(pb_artifact=pb, csharp_artifact=cs)
        self.assertIn(ISSUE_NODE_DUPLICATE, [item["code"] for item in result.metadata["issues"]])

    def test_order_and_timing_drift_are_not_equivalent(self):
        changed = json.loads(json.dumps(self.graph))
        changed["nodes"].reverse()
        changed["nodes"][0]["timing"] = {"stage": "wrong_stage"}
        pb = self._artifact("pb.json", self.graph)
        cs = self._artifact("cs.json", changed)
        result = validate_pb_event_state_contract(pb_artifact=pb, csharp_artifact=cs)
        codes = [item["code"] for item in result.metadata["issues"]]
        self.assertIn(ISSUE_ORDERING_DRIFT, codes)
        self.assertIn(ISSUE_TIMING_DRIFT, codes)

    def test_aliases_are_supported_without_event_name_vocabulary(self):
        pb = self._artifact("pb.json", self.graph)
        cs = self._artifact("cs.json", self.graph)
        result = validate_pb_event_state_contract(
            pb_event_graph=self.graph,
            csharp_event_graph=self.graph,
            artifact_bindings={"pb": pb, "csharp": cs},
        )
        self.assertTrue(result.success, result.to_dict())

    def test_new_module_and_test_are_ast_parseable(self):
        for path in (Path(__file__), Path(__file__).resolve().parents[1] / "src/skills/pb_event_state_contract.py"):
            ast.parse(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
