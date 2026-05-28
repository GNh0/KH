import argparse
import multiprocessing
import time
import os
import sys
import urllib.request
import urllib.error


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
    for i in range(max_retries):
        try:
            req = urllib.request.urlopen(url, timeout=0.5)
            if req.getcode() == 200:
                elapsed = (i + 1) * delay
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


def main():
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(
        description="Antigravity Universal Agent Framework CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  python cli.py run --prompt "FastAPI 서버 만들어줘"
  python cli.py run --project ./my_app --workers 20 --verbose
  python cli.py server --port 9000
        """
    )
    parser.add_argument("command", choices=["run", "server"],
                        help="실행할 명령어 (run: 통합 실행, server: 서버 단독)")
    parser.add_argument("--project", type=str, default=".",
                        help="대상 프로젝트 디렉토리 경로 (기본값: 현재 디렉토리)")
    parser.add_argument("--prompt", type=str, default="간단한 웹사이트 만들어줘",
                        help="에이전트에게 지시할 요구사항")
    parser.add_argument("--port", type=int, default=8000,
                        help="웹훅 서버 포트 (기본값: 8000)")
    # [V2.4] 고급 옵션
    parser.add_argument("--workers", type=int, default=50,
                        help="동시 실행 워커 수 (기본값: 50 / CPU 코어 * 10 초과 불가)")
    parser.add_argument("--no-sandbox", action="store_true",
                        help="보안 샌드박스 비활성화 - 디버그 전용, 운영 환경에서 사용 금지")
    parser.add_argument("--verbose", action="store_true",
                        help="상세 디버그 로그 출력 (서버 로그 포함)")
    parser.add_argument("--allow-dir", dest="allow_dirs", action="append", default=[],
                        metavar="PATH",
                        help="추가로 허용할 폴더 경로 (여러 번 사용 가능). 예: --allow-dir C:/shared")

    parser.add_argument("--platform", choices=["local", "antigravity"], default=os.environ.get("AG_PLATFORM_MODE", "local"),
                        help="Dispatcher platform mode. Use antigravity for app/webhook-driven subagent dispatch.")

    parser.add_argument("--provider", default=os.environ.get("AG_LLM_PROVIDER", "local"),
                        help="LLM provider: local, openai, codex, or claude")
    parser.add_argument("--model", default=os.environ.get("AG_LLM_MODEL", "llama3"),
                        help="LLM model name")
    parser.add_argument("--base-url", default=os.environ.get("AG_LLM_BASE_URL", "http://localhost:11434/v1"),
                        help="OpenAI-compatible API base URL")
    parser.add_argument("--api-key", default=os.environ.get("AG_LLM_API_KEY"),
                        help="LLM API key. If omitted, provider-specific environment variables are used.")

    args = parser.parse_args()

    # 환경변수로 프레임워크 내부 모듈에 옵션 전달 (결합도 제거)
    os.environ["AG_WEBHOOK_URL"] = f"http://127.0.0.1:{args.port}/api/webhook/subagent-result"
    os.environ["AG_MAX_WORKERS"] = str(args.workers)
    os.environ["AG_NO_SANDBOX"] = "1" if args.no_sandbox else "0"
    os.environ["AG_VERBOSE"] = "1" if args.verbose else "0"
    os.environ["AG_PLATFORM_MODE"] = args.platform

    if args.command == "server":
        print(f"[CLI] Webhook server mode on port {args.port}.")
        start_server_process(args.port, args.verbose)

    elif args.command == "run":
        if args.no_sandbox:
            print("[CLI] --no-sandbox is enabled. Code safety checks are disabled.")

        print(f"[CLI] Starting background webhook server on port {args.port}.")
        server_process = multiprocessing.Process(
            target=start_server_process,
            args=(args.port, args.verbose),
            daemon=True
        )
        server_process.start()

        if not wait_for_server(args.port):
            server_process.terminate()
            return

        try:
            sandbox_status = "OFF" if args.no_sandbox else "ON"
            print(f"[CLI] Starting agent loop. workers={args.workers}, sandbox={sandbox_status}.")

            from src.harness.sandbox import set_allowed_workspace, add_allowed_workspace, CodeSandbox

            # [V2.5] 기본 작업 폴더 등록
            workspace = os.path.abspath(args.project)
            set_allowed_workspace(workspace)

            # [V2.5] --allow-dir 로 지정한 추가 폴더 등록
            for extra in args.allow_dirs:
                add_allowed_workspace(extra)

            router = build_llm_router(args)
            loop = build_agent_loop(router, args.project, args.platform)
            loop.run(requirement=args.prompt, framework="vanilla")

        except KeyboardInterrupt:
            print("\n[CLI] Interrupted by user.")
        except Exception as e:
            print(f"\n[CLI] Runtime error: {e}")
        finally:
            try:
                sandbox = CodeSandbox()
                sandbox.cleanup_workspace_temps()
            except Exception:
                pass
            print("[CLI] Stopping background server.")
            server_process.terminate()
            server_process.join()
            print("[CLI] All processes stopped.")


if __name__ == "__main__":
    configure_utf8_stdio()
    multiprocessing.freeze_support()
    main()
