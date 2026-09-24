"""Model-based nonlinear mediation for observed variables."""

__version__ = "0.1.0"

from .api import analyze_mediation
from .spec import compile_template, estimate_plan, load_model_spec
from .types import MediationResult

__all__ = [
    "MediationResult",
    "__version__",
    "analyze_mediation",
    "compile_template",
    "estimate_plan",
    "load_model_spec",
]
