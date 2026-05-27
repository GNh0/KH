import os
import csv
from src.skills.pattern_analyzer import analyze_design_pattern
from src.skills.license_checker import check_license

class SystemArchitect:
    """
    개발 설계자(Architect) 에이전트 파이프라인.
    LLM을 활용하여 짧은 요구사항을 '상세 기능정의서(엑셀 호환 CSV)'로 변환하고, 코더 에이전트가 참조할 마크다운 설계 문서를 생성합니다.
    """
    def __init__(self, project_dir: str, llm_router=None):
        self.project_dir = project_dir
        self.llm = llm_router

    def _generate_functional_spec(self, requirements: str) -> str:
        """LLM을 호출하여 상세 기능정의서를 생성하고 CSV로 저장합니다."""
        if not self.llm:
            return f"(LLM이 연결되지 않아 요구사항 원본을 사용합니다)\n{requirements}"
            
        sys_prompt = "당신은 IT 서비스 기획자(Architect)입니다."
        user_prompt = f"""
다음 사용자의 요구사항을 분석하여 상세 기능정의서를 작성하세요.
결과는 반드시 CSV 포맷으로 작성하고 마크다운 ```csv ... ``` 블록 안에 넣어주세요.
첫 줄은 헤더(ID, 대분류, 기능명, 상세설명)여야 합니다. 쉼표(,)가 내용에 포함될 경우 반드시 쌍따옴표(")로 감싸세요.

[요구사항]
{requirements}
"""
        try:
            response = self.llm.chat(sys_prompt, user_prompt)
            # 마크다운 블록 파싱
            if "```csv" in response:
                csv_data = response.split("```csv")[1].split("```")[0].strip()
            elif "```" in response:
                csv_data = response.split("```")[1].strip()
            else:
                csv_data = response.strip()
                
            # 엑셀(CSV) 파일 출력 (utf-8-sig로 저장하여 엑셀 한글 깨짐 방지)
            csv_path = os.path.join(self.project_dir, "기능정의서.csv")
            with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
                f.write(csv_data)
                
            return f"기능정의서가 엑셀(CSV) 포맷으로 추출되었습니다: {csv_path}\n\n[상세 내역 요약]\n{csv_data}"
        except Exception as e:
            return f"[기능정의서 자동 생성 실패] {e}\n\n[원본 요구사항]\n{requirements}"

    def draft_architecture(self, requirements: str, framework: str, libraries: list, scale: str = "large") -> str:
        """
        요구사항을 분석하고 기능정의서 작성, 패턴 검사, 라이선스 검사 후 최종 설계 문서를 생성합니다.
        """
        doc_path = os.path.join(self.project_dir, "design_doc.md")
        os.makedirs(self.project_dir, exist_ok=True)
        
        # 1. 상세 기능정의서 생성 (LLM 연동 및 엑셀 출력)
        functional_spec_text = self._generate_functional_spec(requirements)
        
        # 2. 디자인 패턴 동적 분석
        pattern_strategy = analyze_design_pattern.__skill_meta__.execute(
            framework=framework, 
            project_scale=scale, 
            maintainability_priority="high"
        )
        
        # 3. 라이선스 체크
        license_reports = []
        for lib in libraries:
            report = check_license.__skill_meta__.execute(package_name=lib, registry="pypi")
            license_reports.append(report)
            
        # 4. 마크다운 시스템 아키텍처 문서(design_doc.md) 조립
        design_doc = f"""# 시스템 아키텍처 및 상세 기능정의서

## 1. 요구사항 및 상세 기능정의 (기획서)
{functional_spec_text}

## 2. 아키텍처 및 디자인 패턴 정책 (유지보수성 중심)
{pattern_strategy}

## 3. 외부 라이브러리 라이선스 검토 결과
{chr(10).join(license_reports)}

## 4. 코더 에이전트 개발 지침 (중요)
- 위 아키텍처 설계와 기능정의서를 철저히 준수할 것.
- 라이선스 문제가 있는 라이브러리는 대체재를 탐색할 것.
- 모든 비즈니스 로직은 향후 유지보수를 위해 철저히 분리할 것.
"""
        
        # 파일 저장
        with open(doc_path, 'w', encoding='utf-8') as f:
            f.write(design_doc)
            
        return doc_path
