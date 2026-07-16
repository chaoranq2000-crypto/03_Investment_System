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
from .episode_portfolio_context import (
    METRIC_REGISTRY_VERSION,
    SCHEMA_VERSION as EPISODE_PORTFOLIO_CONTEXT_SCHEMA_VERSION,
    VALIDATION_SCHEMA_VERSION as EPISODE_PORTFOLIO_CONTEXT_VALIDATION_SCHEMA_VERSION,
    EpisodePortfolioContextError,
    build_episode_portfolio_context,
    load_episode_portfolio_context,
    query_episode_portfolio_context,
    replay_validate_episode_portfolio_context,
    save_episode_portfolio_context,
    validate_episode_portfolio_context,
)
from .portfolio_context import (
    PORTFOLIO_METRIC_METHOD_REGISTRY,
    PORTFOLIO_METRIC_REGISTRY_VERSION,
    MetricEvidence,
    PortfolioContext,
    PortfolioMetric,
    PortfolioSnapshot,
    PortfolioWarning,
    PositionSnapshot,
    calculate_portfolio_evidence_metrics,
    calculate_portfolio_metrics,
    deterministic_portfolio_evidence_json,
    portfolio_metric_method_ref,
)
from .store import DataConflictError, ReviewStore

__all__ = [
    "CanonicalTradeEvent",
    "DataConflictError",
    "DecisionRecord",
    "EPISODE_PORTFOLIO_CONTEXT_SCHEMA_VERSION",
    "EPISODE_PORTFOLIO_CONTEXT_VALIDATION_SCHEMA_VERSION",
    "EpisodePortfolioContextError",
    "MetricEvidence",
    "METRIC_REGISTRY_VERSION",
    "PORTFOLIO_METRIC_METHOD_REGISTRY",
    "PORTFOLIO_METRIC_REGISTRY_VERSION",
    "PortfolioContext",
    "PortfolioMetric",
    "PortfolioSnapshot",
    "PortfolioWarning",
    "PositionSnapshot",
    "ReviewStore",
    "SourceDefinition",
    "build_episode_collection",
    "build_episode_portfolio_context",
    "calculate_portfolio_evidence_metrics",
    "calculate_portfolio_metrics",
    "deterministic_portfolio_evidence_json",
    "load_p2b_snapshot_references",
    "load_episode_portfolio_context",
    "portfolio_metric_method_ref",
    "query_episode_portfolio_context",
    "replay_validate_episode_portfolio_context",
    "query_episode_collection",
    "save_episode_portfolio_context",
    "validate_episode_portfolio_context",
    "validate_episode_collection",
]

__version__ = "0.4.0"
