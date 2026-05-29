import argparse
import multiprocessing
import os
import sys
import time
import urllib.error
import urllib.request


def configure_utf8_stdio():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except Exception:
                pass


def start_server_process(port: int, verbose: bool):
    """Run the uvicorn server in a separate process."""
    from src.api.server import app
    import uvicorn

    log_level = "info" if verbose else "warning"
    uvicorn.run(app, host="0.0.0.0", port=port, log_level=log_level)


def wait_for_server(port: int, max_retries: int = 30, delay: float = 0.1) -> bool:
    """Poll until the local webhook server is ready."""
    url = f"http://127.0.0.1:{port}/api/health"
    print(f"[CLI] Waiting for server response for up to {max_retries * delay:.1f}s.")
    for index in range(max_retries):
        try:
            req = urllib.request.urlopen(url, timeout=0.5)
            if req.getcode() == 200:
                elapsed = (index + 1) * delay
                print(f"[CLI] Server connection established in {elapsed:.1f}s.")
                return True
        except (urllib.error.URLError, ConnectionResetError):
            time.sleep(delay)
    print(f"[CLI] Server did not respond within {max_retries * delay:.1f}s.")
    print(f"[CLI] Port {port} may be in use, or uvicorn/fastapi may be unavailable.")
    return False


def build_llm_router(args):
    from src.orchestration.llm_router import LLMRouter

    return LLMRouter(
        provider=args.provider,
        model=args.model,
        base_url=args.base_url,
        api_key=args.api_key,
    )


def build_agent_loop(router, project: str, platform_mode: str):
    from src.orchestration.agent_loop import AgentLoop

    return AgentLoop(router, project, platform_mode=platform_mode)


def should_start_background_webhook(platform_mode: str) -> bool:
    return platform_mode == "antigravity"


def is_smoke_only_provider(provider: str) -> bool:
    return (provider or "").lower() in {"offline", "deterministic"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="KH Universal Agent Framework CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py run --prompt "Create a FastAPI server"
  python cli.py run --project ./my_app --workers 20 --verbose
  python cli.py server --port 9000
        """,
    )
    parser.add_argument("command", choices=["run", "server"], help="Command to run: run or server")
    parser.add_argument("--project", type=str, default=".", help="Target project directory path")
    parser.add_argument("--prompt", type=str, default="Create a small demo app", help="Requirement prompt for the agent")
    parser.add_argument("--port", type=int, default=8000, help="Webhook server port")
    parser.add_argument("--workers", type=int, default=50, help="Requested concurrent worker count")
    parser.add_argument("--no-sandbox", action="store_true", help="Disable sandbox checks; use only for debugging")
    parser.add_argument("--verbose", action="store_true", help="Print verbose debug logs")
    parser.add_argument(
        "--allow-dir",
        dest="allow_dirs",
        action="append",
        default=[],
        metavar="PATH",
        help="Additional allowed directory path. Can be used more than once.",
    )
    parser.add_argument(
        "--platform",
        choices=["local", "antigravity"],
        default=os.environ.get("AG_PLATFORM_MODE", "local"),
        help="Dispatcher platform mode. Use antigravity for app/webhook-driven subagent dispatch.",
    )
    parser.add_argument("--provider", default=os.environ.get("AG_LLM_PROVIDER", "offline"), help="LLM provider: offline, local, openai, codex, or claude")
    parser.add_argument("--model", default=os.environ.get("AG_LLM_MODEL", "llama3"), help="LLM model name")
    parser.add_argument("--base-url", default=os.environ.get("AG_LLM_BASE_URL", "http://localhost:11434/v1"), help="OpenAI-compatible API base URL")
    parser.add_argument("--api-key", default=os.environ.get("AG_LLM_API_KEY"), help="LLM API key. If omitted, provider-specific environment variables are used.")
    parser.add_argument(
        "--mode",
        choices=["auto", "quick", "full"],
        default=os.environ.get("AG_MODE", "auto"),
        help="Execution mode: quick skips DAG/state for simple tasks, full uses complete orchestration, auto detects complexity.",
    )
    return parser


def _apply_runtime_environment(args) -> None:
    if should_start_background_webhook(args.platform):
        os.environ["AG_WEBHOOK_URL"] = f"http://127.0.0.1:{args.port}/api/webhook/subagent-result"
    else:
        os.environ.pop("AG_WEBHOOK_URL", None)
    os.environ["AG_MAX_WORKERS"] = str(args.workers)
    os.environ["AG_NO_SANDBOX"] = "1" if args.no_sandbox else "0"
    os.environ["AG_VERBOSE"] = "1" if args.verbose else "0"
    os.environ["AG_PLATFORM_MODE"] = args.platform
    os.environ["AG_MODE"] = args.mode


def _run_agent_command(args) -> None:
    if args.no_sandbox:
        print("[CLI] --no-sandbox is enabled. Code safety checks are disabled.")
    if is_smoke_only_provider(args.provider):
        print(
            "[CLI] Offline provider selected: smoke-only deterministic output. "
            "Use a model-backed provider for task-faithful implementation."
        )
    if args.mode == "quick":
        print("[CLI] Quick mode: skipping DAG orchestration, state, and multi-gate pipeline.")
    elif args.mode == "auto":
        print("[CLI] Auto mode: complexity will be assessed to select quick or full execution.")

    server_process = None
    if should_start_background_webhook(args.platform):
        print(f"[CLI] Starting background webhook server on port {args.port}.")
        server_process = multiprocessing.Process(
            target=start_server_process,
            args=(args.port, args.verbose),
            daemon=True,
        )
        server_process.start()

        if not wait_for_server(args.port):
            server_process.terminate()
            return
    else:
        print("[CLI] Local platform selected; background webhook server is not required.")

    try:
        sandbox_status = "OFF" if args.no_sandbox else "ON"
        print(f"[CLI] Starting agent loop. workers={args.workers}, sandbox={sandbox_status}.")

        from src.harness.sandbox import CodeSandbox, add_allowed_workspace, set_allowed_workspace

        workspace = os.path.abspath(args.project)
        set_allowed_workspace(workspace)
        for extra in args.allow_dirs:
            add_allowed_workspace(extra)

        router = build_llm_router(args)
        loop = build_agent_loop(router, args.project, args.platform)
        loop.run(requirement=args.prompt, framework="vanilla")

    except KeyboardInterrupt:
        print("\n[CLI] Interrupted by user.")
    except Exception as exc:
        print(f"\n[CLI] Runtime error: {exc}")
    finally:
        try:
            sandbox = CodeSandbox()
            sandbox.cleanup_workspace_temps()
        except Exception:
            pass
        if server_process is not None:
            print("[CLI] Stopping background server.")
            server_process.terminate()
            server_process.join()
        print("[CLI] All processes stopped.")


def main():
    configure_utf8_stdio()
    parser = build_parser()
    args = parser.parse_args()
    _apply_runtime_environment(args)

    if args.command == "server":
        print(f"[CLI] Webhook server mode on port {args.port}.")
        start_server_process(args.port, args.verbose)
    elif args.command == "run":
        _run_agent_command(args)


if __name__ == "__main__":
    configure_utf8_stdio()
    multiprocessing.freeze_support()
    main()
