from __future__ import annotations

import ast
import re
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "docs/meta/DOCS_REPORTS_RETENTION_DEPENDENCY_MANIFEST.yaml"
TEXT_SUFFIXES = {
    ".css",
    ".csv",
    ".html",
    ".js",
    ".json",
    ".jsx",
    ".md",
    ".ps1",
    ".py",
    ".sh",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}
CURRENT_TEXT_ROUTE_PREFIXES = (
    ".github/",
    ".agents/",
    "config/",
    "docs/architecture/",
    "docs/contracts/",
    "docs/meta/",
    "docs/playbooks/",
    "docs/policies/",
    "docs/workflows/",
    "schemas/",
    "scripts/",
    "src/",
)


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def load_manifest() -> dict[str, Any]:
    data = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def ready_items() -> dict[str, dict[str, Any]]:
    manifest = load_manifest()
    return {
        item["path"]: item
        for group in manifest["candidate_groups"]
        if group["status"] == "READY_FOR_MANUAL_DELETE"
        for item in group["items"]
    }


def iter_active_text_files() -> list[Path]:
    tracked = subprocess.check_output(
        ["git", "-C", str(ROOT), "ls-files", "-z"],
    ).decode("utf-8").split("\0")
    return sorted(
        ROOT / relative
        for relative in tracked
        if relative
        and (ROOT / relative).is_file()
        and (ROOT / relative).suffix.lower() in TEXT_SUFFIXES
    )


def _expr_strings(
    node: ast.AST | None,
    assignments: Mapping[str, set[str]],
) -> set[str]:
    if node is None:
        return set()
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return {node.value}
    if isinstance(node, ast.Name):
        return set(assignments.get(node.id, set()))
    if isinstance(node, ast.JoinedStr):
        pieces: list[set[str]] = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                pieces.append({value.value})
            elif isinstance(value, ast.FormattedValue):
                pieces.append(_expr_strings(value.value, assignments) or {""})
        combined = {""}
        for options in pieces:
            combined = set(
                sorted(left + right for left in combined for right in options)[:128]
            )
        return combined
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Div)):
        left = _expr_strings(node.left, assignments)
        right = _expr_strings(node.right, assignments)
        if not left:
            return right
        if not right:
            return left
        separator = "/" if isinstance(node.op, ast.Div) else ""
        return set(sorted(f"{a}{separator}{b}" for a in left for b in right)[:128])
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return {
            value
            for item in node.elts
            for value in _expr_strings(item, assignments)
        }
    if isinstance(node, ast.IfExp):
        return _expr_strings(node.body, assignments) | _expr_strings(
            node.orelse, assignments
        )
    if isinstance(node, ast.BoolOp):
        return {
            value
            for item in node.values
            for value in _expr_strings(item, assignments)
        }
    if isinstance(node, ast.Call):
        name = (
            node.func.id
            if isinstance(node.func, ast.Name)
            else node.func.attr
            if isinstance(node.func, ast.Attribute)
            else ""
        )
        values = {
            value
            for arg in node.args
            for value in _expr_strings(arg, assignments)
        }
        if name in {"join", "joinpath"} and len(node.args) > 1:
            options = [_expr_strings(arg, assignments) for arg in node.args]
            combined = {""}
            for choices in options:
                combined = {
                    f"{left.rstrip('/')}/{right.lstrip('/')}" if left else right
                    for left in combined
                    for right in choices
                }
            values.update(combined)
        return values
    if isinstance(node, ast.Attribute):
        return _expr_strings(node.value, assignments)
    return set()


def _token_hits(values: Iterable[str], tokens: Mapping[str, str]) -> set[str]:
    rendered = "\n".join(value.replace("\\", "/") for value in values)
    return {target for token, target in tokens.items() if token in rendered}


def _python_dynamic_references(
    source_path: str,
    text: str,
    tokens: Mapping[str, str],
) -> set[str]:
    tree = ast.parse(text, filename=source_path)
    parents: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent

    assignments: dict[str, set[str]] = defaultdict(set)
    expressions: dict[str, list[ast.AST]] = defaultdict(list)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    expressions[target.id].append(node.value)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            expressions[node.target.id].append(node.value)
    for _ in range(8):
        changed = False
        for name, nodes in expressions.items():
            before = len(assignments[name])
            for node in nodes:
                assignments[name].update(_expr_strings(node, assignments))
            changed = changed or len(assignments[name]) != before
        if not changed:
            break

    temporary_names = {
        argument.arg
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        for argument in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)
        if argument.arg in {"tmp_path", "tmp_path_factory"}
    }

    def is_temporary(node: ast.AST | None) -> bool:
        if isinstance(node, ast.Name):
            return node.id in temporary_names
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            return is_temporary(node.left)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "Path":
            return bool(node.args) and is_temporary(node.args[0])
        if isinstance(node, ast.Attribute):
            return is_temporary(node.value)
        return False

    def called_name(node: ast.Call) -> str:
        if isinstance(node.func, ast.Name):
            return node.func.id
        if isinstance(node.func, ast.Attribute):
            return node.func.attr
        return ""

    function_nodes = {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    immutable_git_readers = {
        name
        for name, function in function_nodes.items()
        if "cat-file" in (ast.get_source_segment(text, function) or "")
        and "rev-parse" in (ast.get_source_segment(text, function) or "")
        and "assert" in (ast.get_source_segment(text, function) or "")
    }

    def enclosing_function(node: ast.AST) -> str | None:
        current = parents.get(node)
        while current is not None:
            if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return current.name
            current = parents.get(current)
        return None

    physical = {
        "append", "dump", "exists", "glob", "is_dir", "is_file", "iterdir",
        "load", "mkdir", "open", "read", "read_bytes", "read_csv", "read_text",
        "rglob", "save", "stat", "update", "upsert", "write", "write_bytes",
        "write_readout", "write_text", "_write_yaml",
    }
    indirect = re.compile(
        r"(?i)(load|read|validate|build|render|compose|materialize|resolve|run|write|append|update|upsert|emit|persist|save|dump)"
    )
    path_key = re.compile(r"(?i)(path|root|dir|file|workflow_id|context|report|artifact|input|source)")
    hits: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = called_name(node)
        if name in immutable_git_readers or name in {"historical_blob_bytes", "historical_blob_file"}:
            continue
        if enclosing_function(node) in immutable_git_readers:
            continue
        receiver = node.func.value if isinstance(node.func, ast.Attribute) else None
        values = set(_expr_strings(receiver, assignments))
        for arg in node.args:
            values.update(_expr_strings(arg, assignments))
        for keyword in node.keywords:
            values.update(_expr_strings(keyword.value, assignments))
        matched = _token_hits(values, tokens)
        if not matched:
            continue
        temporary = is_temporary(receiver) or (bool(node.args) and is_temporary(node.args[0]))
        explicit_paths = sum(
            bool(keyword.arg and path_key.search(keyword.arg))
            for keyword in node.keywords
            if keyword.arg not in {"workflow_id"}
        ) >= 2
        if temporary:
            continue
        if name == "add_argument" and any(keyword.arg == "default" for keyword in node.keywords):
            hits.update(matched)
        elif name in physical:
            hits.update(matched)
        elif indirect.search(name) and not explicit_paths:
            hits.update(matched)
    return hits


def _scan_probe(token: str) -> str:
    parts = token.rstrip("/").split("/")
    if parts[-1] in {"CONTRACT.md", "START_HERE.md"} and len(parts) > 1:
        return parts[-2]
    return parts[-1]


def _text_route_hits(text: str, tokens: Mapping[str, str]) -> set[str]:
    physical_context = re.compile(
        r"(?i)(default|path|root|dir|file|artifact|input|output|source|run:|uses:|include|pytest|python)"
    )
    hits: set[str] = set()
    for line in text.splitlines():
        if not physical_context.search(line):
            continue
        hits.update(_token_hits([line], tokens))
    return hits


def test_ready_candidates_have_no_undeclared_active_worktree_dependency() -> None:
    items = ready_items()
    candidate_paths = set(items)
    declared = {
        path: {
            ref["source_path"]
            for ref in item["inbound_references"]
        }
        for path, item in items.items()
    }
    observed: dict[str, set[str]] = {path: set() for path in candidate_paths}

    for source in iter_active_text_files():
        source_rel = source.relative_to(ROOT).as_posix()
        if source_rel == MANIFEST_PATH.relative_to(ROOT).as_posix():
            continue
        if source_rel in candidate_paths:
            continue
        text = source.read_text(encoding="utf-8", errors="replace")
        for candidate in candidate_paths:
            if candidate in text:
                observed[candidate].add(source_rel)

    unexpected = {
        path: sorted(sources - declared[path])
        for path, sources in observed.items()
        if sources - declared[path]
    }
    assert unexpected == {}
    assert all(
        ref["relation"] != "current_worktree_physical"
        for item in items.values()
        for ref in item["inbound_references"]
    )


def test_dynamic_python_routes_are_declared_or_absent() -> None:
    items = ready_items()
    tokens = {path: path for path in items}
    declared = {
        target: {ref["source_path"] for ref in item["inbound_references"]}
        for target, item in items.items()
    }
    unexpected: dict[str, list[str]] = {}

    for source in iter_active_text_files():
        if source.suffix.lower() != ".py":
            continue
        source_rel = source.relative_to(ROOT).as_posix()
        if source_rel in items or source_rel == MANIFEST_PATH.relative_to(ROOT).as_posix():
            continue
        source_text = source.read_text(encoding="utf-8", errors="replace")
        if not any(_scan_probe(token) in source_text for token in tokens):
            continue
        hits = _python_dynamic_references(
            source_rel,
            source_text,
            tokens,
        )
        for target in sorted(hits):
            if source_rel not in declared[target]:
                unexpected.setdefault(target, []).append(source_rel)

    assert unexpected == {}


def test_retired_route_tokens_have_no_active_default_or_physical_reader() -> None:
    manifest = load_manifest()
    tokens = {
        token: row["id"]
        for row in manifest["retired_route_tokens"]
        for token in row["tokens"]
    }
    allowed = {
        row["id"]: {reader["source_path"] for reader in row["allowed_readers"]}
        for row in manifest["retired_route_tokens"]
    }
    observed: dict[str, set[str]] = {row["id"]: set() for row in manifest["retired_route_tokens"]}

    for source in iter_active_text_files():
        if source.suffix.lower() != ".py":
            continue
        source_rel = source.relative_to(ROOT).as_posix()
        if source_rel == MANIFEST_PATH.relative_to(ROOT).as_posix():
            continue
        source_text = source.read_text(encoding="utf-8", errors="replace")
        if not any(_scan_probe(token) in source_text for token in tokens):
            continue
        hits = _python_dynamic_references(
            source_rel,
            source_text,
            tokens,
        )
        for target in sorted(hits):
            observed[target].add(source_rel)

    unexpected = {
        target: sorted(sources - allowed[target])
        for target, sources in observed.items()
        if sources - allowed[target]
    }
    assert unexpected == {}


def test_declared_retired_route_readers_are_git_or_temp_bound() -> None:
    manifest = load_manifest()
    for route in manifest["retired_route_tokens"]:
        for reader in route["allowed_readers"]:
            source = read(reader["source_path"])
            relation = reader["relation"]
            if relation in {
                "immutable_git_snapshot_replay",
                "immutable_git_snapshot_validation",
                "immutable_git_fixture_source",
            }:
                assert "cat-file" in source, reader
                assert "rev-parse" in source, reader
                assert "sha256" in source or "hashlib.sha1" in source, reader
                assert (
                    "assert" in source
                    or "raise ReplayContractError" in source
                    or "raise ValueError" in source
                ), reader
            elif relation == "immutable_git_fixture_or_temp_only":
                assert (
                    "historical_blob_bytes" in source
                    or "historical_blob_file" in source
                    or "historical_fixture_root" in source
                ), reader
            elif relation == "explicit_legacy_writer":
                argument = re.search(
                    r"add_argument\(\s*['\"]--repo-root['\"](?P<body>.*?)\)",
                    source,
                    re.DOTALL,
                )
                assert argument is not None, reader
                assert "required=True" in argument.group("body"), reader
                assert "WORKFLOW_ID" in source, reader
                assert "_write_yaml" in source or "write_readout" in source, reader
            elif relation == "explicit_scoped_legacy_writer":
                for flag in (
                    "--workflow-id",
                    "--run-dir",
                    "--dropzone-output",
                    "--readout-output",
                ):
                    argument = re.search(
                        rf"add_argument\(\s*['\"]{re.escape(flag)}['\"](?P<body>.*?)\)",
                        source,
                        re.DOTALL,
                    )
                    assert argument is not None, (reader, flag)
                    assert "required=True" in argument.group("body"), (reader, flag)
            elif relation == "explicit_workflow_run_writer":
                argument = re.search(
                    r"add_argument\(\s*['\"]--workflow-run['\"](?P<body>.*?)\)",
                    source,
                    re.DOTALL,
                )
                assert argument is not None, reader
                assert "required=True" in argument.group("body"), reader
            else:
                raise AssertionError(f"unknown retired reader relation: {relation}")


def test_retired_routes_do_not_reenter_current_text_defaults() -> None:
    manifest = load_manifest()
    tokens = {
        token: row["id"]
        for row in manifest["retired_route_tokens"]
        for token in row["tokens"]
    }
    declared_surfaces = {
        row["path"]: "old_002837_workflow"
        for row in manifest["legacy_route_surfaces"]
    }
    observed: dict[str, set[str]] = {}
    for source in iter_active_text_files():
        source_rel = source.relative_to(ROOT).as_posix()
        if source.suffix.lower() == ".py" or source_rel == MANIFEST_PATH.relative_to(ROOT).as_posix():
            continue
        if not source_rel.startswith(CURRENT_TEXT_ROUTE_PREFIXES):
            continue
        source_text = source.read_text(encoding="utf-8", errors="replace")
        for target in sorted(_text_route_hits(source_text, tokens)):
            observed.setdefault(target, set()).add(source_rel)

    unexpected = {
        target: sorted(
            source
            for source in sources
            if declared_surfaces.get(source) != target
        )
        for target, sources in observed.items()
        if any(declared_surfaces.get(source) != target for source in sources)
    }
    assert unexpected == {}
    assert observed.get("old_002837_workflow", set()) == set(declared_surfaces)


def test_legacy_gate_clis_require_explicit_rules_and_inputs() -> None:
    expectations = {
        "scripts/build_r5_bundle5_forecast_valuation_onboarding.py": (
            "--repo-root",
            "--reviewed-at",
        ),
        "scripts/build_r5_bundle5_market_peer_onboarding.py": (
            "--repo-root",
            "--reviewed-at",
        ),
        "scripts/validate_r5_bundle9r_generation_binding.py": (
            "--binding",
        ),
        "scripts/r5_next_pilot_gate.py": (
            "--rules",
            "--readiness",
            "--market-peer-input-registry",
            "--forecast-assumption-registry",
            "--evidence-request-review-ledger",
        ),
        "scripts/r5_pack_promotion_gate.py": (
            "--rules",
            "--pack",
            "--dry-run",
        ),
        "scripts/r5_readiness_gate.py": (
            "--rules",
            "--smoke-result",
            "--inventory-status",
            "--format-guard",
            "--source-gapped-pack",
            "--source-gap-report",
            "--evidence-plan",
            "--valuation-handoff-example",
        ),
        "scripts/r5_reviewed_input_pilot_gate.py": (
            "--rules",
            "--strict-smoke-result",
            "--source-gapped-pack",
            "--reviewed-input-dry-run-result",
            "--quality-scorecard-v2",
            "--promotion-rules",
        ),
    }
    forbidden_defaults = {
        "config/r5_bundle9r_generation_binding.yaml",
        "config/r5_next_pilot_gate_rules.yaml",
        "config/r5_pack_promotion_rules.yaml",
        "config/r5_readiness_gate_rules.yaml",
        "config/r5_reviewed_input_pilot_gate_rules.yaml",
    }

    for source_path, flags in expectations.items():
        source = read(source_path)
        for flag in flags:
            argument = re.search(
                rf"add_argument\(\s*['\"]{re.escape(flag)}['\"](?P<body>.*?)\)",
                source,
                re.DOTALL,
            )
            assert argument is not None, (source_path, flag)
            assert "required=True" in argument.group("body"), (source_path, flag)
        assert forbidden_defaults.isdisjoint(set(re.findall(r"config/r5_[a-z0-9_]+\.yaml", source)))


def test_dynamic_scanner_distinguishes_tmp_git_and_active_routes() -> None:
    candidate = "reports/workflow_runs/example_retired_run/input.yaml"
    tokens = {candidate: candidate}
    pure_tmp = f'''\nfrom pathlib import Path\ndef case(tmp_path):\n    return (tmp_path / {candidate!r}).read_text()\n'''
    active = f'''\nfrom pathlib import Path\nROOT = Path.cwd()\nTARGET = ROOT / "reports/workflow_runs" / "example_retired_run" / "input.yaml"\ndef load():\n    return TARGET.read_text()\n'''
    cli_default = f'''\nimport argparse\np = argparse.ArgumentParser()\np.add_argument("--input", default={candidate!r})\n'''
    indirect = f'''\nfrom pathlib import Path\nTARGET = Path({candidate!r})\ndef validate_context(path):\n    return path\nvalidate_context(TARGET)\n'''
    active_write = f'''\nfrom pathlib import Path\nTARGET = Path({candidate!r})\ndef _write_yaml(path, payload):\n    path.write_text(str(payload))\n_write_yaml(TARGET, {{}})\n'''
    git_reader = f'''\nimport subprocess\ndef historical_blob():\n    spec = "baseline:" + {candidate!r}\n    oid = subprocess.check_output(["git", "rev-parse", spec])\n    payload = subprocess.check_output(["git", "cat-file", "blob", spec])\n    assert oid and payload\n    return payload\nhistorical_blob()\n'''

    assert _python_dynamic_references("tmp.py", pure_tmp, tokens) == set()
    assert _python_dynamic_references("active.py", active, tokens) == {candidate}
    assert _python_dynamic_references("default.py", cli_default, tokens) == {candidate}
    assert _python_dynamic_references("indirect.py", indirect, tokens) == {candidate}
    assert _python_dynamic_references("writer.py", active_write, tokens) == {candidate}
    assert _python_dynamic_references("git_fixture.py", git_reader, tokens) == set()


def test_current_pointer_has_no_legacy_selection_surface() -> None:
    index = yaml.safe_load(read("config/r5_readout_canonical_index.yaml"))

    assert index["schema_version"] == "research_current_run_pointer_v1"
    assert "readouts" not in index
    assert "policy_migrations" not in index
    assert index["history"]["current_selection_allowed"] is False
    assert index["authority"]["project_rules"] == "AGENTS.md"
    assert index["authority"]["research_workflow"] == (
        "docs/workflows/RESEARCH_WORKFLOW.md"
    )


def test_ci_and_manual_workflow_do_not_invoke_retired_cleanup_tool() -> None:
    ci = read(".github/workflows/ci.yml")
    manual = read(".github/workflows/legacy_compatibility.yml")
    combined = ci + "\n" + manual

    assert "tests/test_r5_v1_active_routing_retirement.py" in ci
    assert "manage_r5_v1_historical_cleanup.py" not in combined
    assert "v1_governance_integration_cleanup_v8/CONTRACT.md" not in combined
    assert "v1_governance_integration_cleanup_v11/CONTRACT.md" not in combined
    assert "tests/test_r5_v1_replay_002837.py" in manual
    assert "workflow_dispatch" in manual


def test_operational_source_route_proof_uses_current_quality_location() -> None:
    registry = read("config/adapter_contract_registry.yaml")
    catalog = read("config/a_stock_data_capability_catalog.yaml")
    current_proof = "reports/quality/source_route_quality_report.yaml"
    retired_proof = "reports/p1_6/" + (
        "r5_v1_governance_cleanup/validation/source_route_quality_report.yaml"
    )

    assert current_proof in registry
    assert current_proof in catalog
    assert retired_proof not in registry
    assert retired_proof not in catalog
    assert (ROOT / current_proof).is_file()


def test_retained_builders_require_explicit_workflow_roots() -> None:
    explicit_cli_paths = (
        "scripts/build_r5_bundle10_reader_pack.py",
        "scripts/build_r5_bundle9_forecast.py",
        "scripts/build_r5_reader_section_payloads.py",
        "src/ingest/business_segment_extraction.py",
        "src/qa/r4_disclosure_backflow_review.py",
    )
    for path in explicit_cli_paths:
        source = read(path)
        assert 'add_argument("--workflow-run", required=True)' in source, path

    valuation = read("scripts/build_r5_bundle9_valuation.py")
    assert 'f"reports/workflow_runs/{run_dir.name}/valuation"' in valuation
    backflow = read("src/research/r5_bundle13r_evidence_backflow.py")
    assert '(output_root.parent / "bundle12r_rerun_after_13r").as_posix()' in backflow


def test_retained_bundle_evaluators_are_explicit_and_noncanonical() -> None:
    bundle11 = read("scripts/run_r5_bundle11r_runtime.py")
    bundle12 = read("scripts/run_r5_bundle12r_operating_evidence_gate.py")
    bundle13 = read("scripts/run_r5_bundle13r_evidence_backflow.py")
    sources = "\n".join(
        read(path)
        for path in (
            "src/research/r5_bundle11r_runtime.py",
            "src/research/r5_bundle12r_operating_evidence.py",
            "src/research/r5_bundle13r_evidence_backflow.py",
        )
    )

    assert 'parser.add_argument("--segment-plan", required=True)' in bundle11
    assert 'parser.add_argument("--output", required=True)' in bundle11
    assert 'parser.add_argument("--input", required=True' in bundle12
    assert 'parser.add_argument("--output-dir", required=True' in bundle12
    assert 'parser.add_argument("--bundle12r-context-dir", required=True)' in bundle13
    assert 'parser.add_argument("--reviewed-backfill", required=True)' in bundle13
    assert 'parser.add_argument("--output-dir", required=True)' in bundle13
    assert "workflow_state.yaml" not in sources
    assert "validate_workflow_state" not in sources


def test_standard_ci_keeps_full_history_and_drops_retired_routes() -> None:
    ci = read(".github/workflows/ci.yml")
    runtime = read(".github/workflows/r5_bundle11r_runtime.yml")

    assert "fetch-depth: 0" in ci
    assert "tests/test_r5_night_shift_" not in ci
    assert "reports/p1_6/r5_night_shift/" not in ci
    assert "reports/p1_6/r5_bundle17r" not in ci
    assert "test_r5_bundle11r_runtime_integration.py" not in runtime
    assert "scripts/audit_r5_bundle11r_target.py" not in runtime
    assert "scripts/integrate_r5_bundle11r_workflow.py" not in runtime
