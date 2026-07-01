import argparse
import os
import sys

from src.core.architect import SystemArchitect
from src.core.mcp_server import serve_mcp
from src.harness.evaluator import Evaluator
from src.orchestration.agent_loop import AgentLoop
from src.orchestration.llm_router import LLMRouter


def main():
    parser = argparse.ArgumentParser(description="Universal Agent Framework CLI Runner")
    parser.add_argument(
        "--mode",
        choices=["architect", "evaluate", "mcp", "orchestrate"],
        required=True,
        help="Execution mode",
    )
    parser.add_argument("--project_dir", type=str, default="./workspace", help="Project workspace path")

    parser.add_argument("--reqs", type=str, help="[Architect/Orchestrate] Requirements text")
    parser.add_argument("--framework", type=str, help="[Architect/Orchestrate] Target framework")
    parser.add_argument(
        "--libs",
        type=str,
        nargs="*",
        default=[],
        help="[Architect/Orchestrate] External libraries to consider",
    )

    parser.add_argument("--agent_code_path", type=str, help="[Evaluate] Agent code file path")
    parser.add_argument("--test_code_path", type=str, help="[Evaluate] Test code file path")

    parser.add_argument(
        "--llm_provider",
        type=str,
        default="local",
        help="[Orchestrate] LLM provider: openai, claude, local, offline, deterministic",
    )
    parser.add_argument("--llm_model", type=str, default="llama3", help="[Orchestrate] LLM model name")
    parser.add_argument(
        "--llm_base_url",
        type=str,
        default="http://localhost:11434/v1",
        help="[Orchestrate] OpenAI-compatible base URL",
    )
    parser.add_argument(
        "--platform_mode",
        choices=["local", "antigravity"],
        default=os.environ.get("AG_PLATFORM_MODE", "local"),
        help="[Orchestrate] Dispatcher platform mode",
    )

    args = parser.parse_args()

    if args.mode == "mcp":
        serve_mcp()
        return

    if args.mode == "architect":
        if not args.reqs or not args.framework:
            print("Error: --reqs and --framework are required in architect mode")
            sys.exit(1)

        architect = SystemArchitect(project_dir=args.project_dir)
        print(">>> [System] Starting system architecture pipeline...")
        result = architect.draft_architecture(
            requirements=args.reqs,
            framework=args.framework,
            libraries=args.libs,
        )
        print(f">>> [Result] {result}")
        return

    if args.mode == "orchestrate":
        if not args.reqs or not args.framework:
            print("Error: --reqs and --framework are required in orchestrate mode")
            sys.exit(1)

        print(">>> [System] Starting multi-agent orchestration loop...")
        router = LLMRouter(provider=args.llm_provider, model=args.llm_model, base_url=args.llm_base_url)
        loop = AgentLoop(llm_router=router, project_dir=args.project_dir, platform_mode=args.platform_mode)
        loop.run(requirement=args.reqs, framework=args.framework, libs=args.libs)
        return

    if args.mode == "evaluate":
        if not args.agent_code_path or not args.test_code_path:
            print("Error: --agent_code_path and --test_code_path are required in evaluate mode")
            sys.exit(1)

        try:
            with open(args.agent_code_path, "r", encoding="utf-8") as f:
                agent_code = f.read()
            with open(args.test_code_path, "r", encoding="utf-8") as f:
                test_code = f.read()
        except FileNotFoundError as exc:
            print(f"Error: file not found. {exc}")
            sys.exit(1)

        evaluator = Evaluator()
        print(">>> [System] Starting harness evaluation...")
        feedback = evaluator.evaluate_code(agent_code, test_code)

        if feedback["passed"]:
            print(f">>> [Success] {feedback['message']}")
        else:
            print(f">>> [Fail] {feedback['message']}")
            print(f"--- Stderr Logs ---\n{feedback['stderr']}")


if __name__ == "__main__":
    main()
