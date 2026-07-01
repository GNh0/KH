from src.skills.base import agent_skill


@agent_skill(
    name="analyze_design_pattern",
    description="Analyze project requirements and recommend a maintainable design pattern.",
)
def analyze_design_pattern(framework: str, project_scale: str, maintainability_priority: str = "high") -> str:
    """Return a framework-aware design-pattern recommendation."""
    recommendation = f"--- Design Pattern Analysis ({framework}) ---\n"

    if framework.lower() == "wpf":
        if project_scale == "small" and maintainability_priority != "high":
            recommendation += (
                "Recommendation: Code-behind with simple data binding\n"
                "Reason: keeps small projects productive without unnecessary view-model boilerplate."
            )
        else:
            recommendation += (
                "Recommendation: strict MVVM (Model-View-ViewModel)\n"
                "Reason: separates testable view-model logic and improves long-term maintainability."
            )
    elif framework.lower() in ["winform", "winforms"]:
        if project_scale == "large" or maintainability_priority == "high":
            recommendation += (
                "Recommendation: MVP (Model-View-Presenter)\n"
                "Reason: presenter separation reduces form coupling and improves maintainability."
            )
        else:
            recommendation += (
                "Recommendation: designer-based code-behind\n"
                "Reason: fits rapid prototypes and one-off internal tools."
            )
    else:
        recommendation += (
            f"Recommendation: follow {framework} standard best practices\n"
            "Core principle: reduce coupling, keep responsibilities cohesive, and preserve test seams."
        )

    return recommendation
