from src.skills.base import agent_skill

@agent_skill(name="analyze_design_pattern", description="프로젝트 요구사항을 분석하여 유지보수성이 뛰어난 최적의 디자인 패턴을 동적으로 추천합니다.")
def analyze_design_pattern(framework: str, project_scale: str, maintainability_priority: str = "high") -> str:
    """
    단순한 프레임워크 룰 강제가 아닌, 프로젝트 규모와 성격에 맞춰 유지보수성을 극대화하는 패턴을 분석하여 반환합니다.
    """
    recommendation = f"--- 디자인 패턴 분석 결과 ({framework}) ---\n"
    
    if framework.lower() == "wpf":
        if project_scale == "small" and maintainability_priority != "high":
            recommendation += "추천: Code-Behind 기반 + 단순 Data Binding\n이유: 소규모 프로젝트에서 불필요한 보일러플레이트 코드를 줄여 생산성 극대화."
        else:
            recommendation += "추천: 엄격한 MVVM (Model-View-ViewModel) 패턴 적용\n이유: 확장이 용이하고 테스트 가능한 뷰모델 분리를 통해 장기적인 유지보수성 완벽 보장."
            
    elif framework.lower() in ["winform", "winforms"]:
        if project_scale == "large" or maintainability_priority == "high":
            recommendation += "추천: MVP (Model-View-Presenter) 패턴 도입\n이유: 기본 Code-behind는 폼 종속성이 강해 스파게티 코드가 되기 쉬우므로, Presenter 계층 분리를 통한 유지보수성 확보 필수."
        else:
            recommendation += "추천: 폼 디자이너 기반 Code-behind\n이유: 빠른 프로토타이핑 및 일회성 도구 개발에 적합."
            
    else:
        recommendation += f"추천: {framework} 표준 모범 사례(Best Practice) 준수\n핵심 원칙: SOLID 원칙 기반의 결합도 최소화 및 응집도 극대화."
        
    return recommendation
