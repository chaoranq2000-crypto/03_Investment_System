"""Evidence-first investment review data foundation.

Phase 1 deliberately stays read-only with respect to the existing portfolio
ledger.  It stores normalized review events and decision notes in a separate
SQLite database so later analysis remains traceable and reversible.
"""

from .models import CanonicalTradeEvent, DecisionRecord, SourceDefinition
from .store import DataConflictError, ReviewStore

__all__ = [
    "CanonicalTradeEvent",
    "DataConflictError",
    "DecisionRecord",
    "ReviewStore",
    "SourceDefinition",
]

__version__ = "0.1.0"
