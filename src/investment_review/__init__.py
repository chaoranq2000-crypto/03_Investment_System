"""Evidence-first investment review data foundation.

The package stays read-only with respect to the existing portfolio ledger.  It
stores normalized review events, decision notes, and reviewed snapshots in a
separate SQLite database so later analysis remains traceable and reversible.
"""

from .models import CanonicalTradeEvent, DecisionRecord, SourceDefinition
from .portfolio_context import (
    PortfolioContext,
    PortfolioSnapshot,
    PositionSnapshot,
    calculate_portfolio_metrics,
)
from .store import DataConflictError, ReviewStore

__all__ = [
    "CanonicalTradeEvent",
    "DataConflictError",
    "DecisionRecord",
    "PortfolioContext",
    "PortfolioSnapshot",
    "PositionSnapshot",
    "ReviewStore",
    "SourceDefinition",
    "calculate_portfolio_metrics",
]

__version__ = "0.2.0"
