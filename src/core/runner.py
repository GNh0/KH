import argparse
import sys
from src.core.architect import SystemArchitect
from src.harness.evaluator import Evaluator
from src.core.mcp_server import serve_mcp
from src.orchestration.llm_router import LLMRouter
from src.orchestration.agent_loop import AgentLoop

def main():
    parser = argparse.ArgumentParser(description="Universal Agent Framework CLI Runner")
    parser.add_argument("--mode", choices=["architect", "evaluate", "mcp", "orchestrate"], required=True, help="실행 모드 선택")
    parser.add_argument("--project_dir", type=str, default="./workspace", help="프로젝트 작업 경로")
    
    # Architect 모드 인자
    parser.add_argument("--reqs", type=str, help="[Architect] 요구사항 명세")
    parser.add_argument("--framework", type=str, help="[Architect] 타겟 프레임워크")
    parser.add_argument("--libs", type=str, nargs="*", default=[], help="[Architect] 사용할 외부 라이브러리 목록")
    
    # Evaluate 모드 인자
    parser.add_argument("--agent_code_path", type=str, help="[Evaluate] 에이전트 작성 코드 경로")
    parser.add_argument("--test_code_path", type=str, help="[Evaluate] 테스트 코드 경로")
    
    # Orchestrate 모드 인자
    parser.add_argument("--llm_provider", type=str, default="local", help="[Orchestrate] LLM 제공자 (openai, claude, local)")
    parser.add_argument("--llm_model", type=str, default="llama3", help="[Orchestrate] LLM 모델명")
    parser.add_argument("--llm_base_url", type=str, default="http://localhost:11434/v1", help="[Orchestrate] 로컬 LLM Base URL")

    args = parser.parse_args()

    if args.mode == "mcp":
        # MCP 모드는 stdin/stdout을 점유하므로 다른 출력을 끄고 바로 실행합니다.
        serve_mcp()
        return

    elif args.mode == "architect":
        if not args.reqs or not args.framework:
            print("Error: architect 모드에서는 --reqs와 --framework 인자가 필수입니다.")
            sys.exit(1)
        
        architect = SystemArchitect(project_dir=args.project_dir)
        print(">>> [System] 아키텍트 파이프라인 시작...")
        result = architect.draft_architecture(
            requirements=args.reqs,
            framework=args.framework,
            libraries=args.libs
        )
        print(f">>> [Result] {result}")

    elif args.mode == "orchestrate":
        if not args.reqs or not args.framework:
            print("Error: orchestrate 모드에서는 --reqs와 --framework 인자가 필수입니다.")
            sys.exit(1)
        
        print(">>> [System] 다중 LLM 오케스트레이션 루프 시작...")
        router = LLMRouter(provider=args.llm_provider, model=args.llm_model, base_url=args.llm_base_url)
        loop = AgentLoop(llm_router=router, project_dir=args.project_dir)
        loop.run(requirement=args.reqs, framework=args.framework, libs=args.libs)

    elif args.mode == "evaluate":
        if not args.agent_code_path or not args.test_code_path:
            print("Error: evaluate 모드에서는 --agent_code_path와 --test_code_path 인자가 필수입니다.")
            sys.exit(1)
            
        try:
            with open(args.agent_code_path, 'r', encoding='utf-8') as f:
                agent_code = f.read()
            with open(args.test_code_path, 'r', encoding='utf-8') as f:
                test_code = f.read()
        except FileNotFoundError as e:
            print(f"Error: 파일을 찾을 수 없습니다. {str(e)}")
            sys.exit(1)
            
        evaluator = Evaluator()
        print(">>> [System] 하네스 샌드박스 평가 시작...")
        feedback = evaluator.evaluate_code(agent_code, test_code)
        
        if feedback["passed"]:
            print(f">>> [Success] {feedback['message']}")
        else:
            print(f">>> [Fail] {feedback['message']}")
            print(f"--- Stderr Logs ---\n{feedback['stderr']}")

if __name__ == "__main__":
    main()
