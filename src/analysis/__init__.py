"""AI analysis layer (spec section 4).

`Analyzer` is the Claude-powered implementation. `RuleBasedAnalyzer` is an
offline, no-API fallback with the same interface (for runs without a key).
"""

from .analyzer import Analyzer
from .rule_based import RuleBasedAnalyzer

__all__ = ["Analyzer", "RuleBasedAnalyzer"]
