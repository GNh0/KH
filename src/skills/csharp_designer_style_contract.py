"""Legacy entrypoint without signed evidence, temporary approvals or profile authentication."""
from src.csharp.checks import verify_csharp_edit_contract, check_csharp
__all__ = ["verify_csharp_edit_contract", "check_csharp"]
