"""Evidence-first investment review data foundation.

The package stays read-only with respect to the existing portfolio ledger.  It
stores normalized review events, decision notes, and reviewed snapshots in a
separate SQLite database so later analysis remains traceable and reversible.
"""

from .models import CanonicalTradeEvent, DecisionRecord, SourceDefinition
from .episodes import (
    build_episode_collection,
    load_p2b_snapshot_references,
    query_episode_collection,
    validate_episode_collection,
)
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
    "build_episode_collection",
    "calculate_portfolio_metrics",
    "load_p2b_snapshot_references",
    "query_episode_collection",
    "validate_episode_collection",
]

__version__ = "0.3.0"
