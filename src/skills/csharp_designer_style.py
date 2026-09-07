"""Legacy module location for current-source Designer checks; old workflow APIs are removed."""
from src.csharp.checks import check_csharp
from src.csharp.designer import check_designer
from src.csharp.designer_model import parse_designer_source
__all__ = ["check_csharp", "check_designer", "parse_designer_source"]
