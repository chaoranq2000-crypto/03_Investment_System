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
    items = {path: {"path": path, "inbound_references": []} for path in manifest["retired_paths"]}
    for row in manifest["allowed_retired_references"]:
        for target in row["targets"]:
            items[target]["inbound_references"].append({
                "source_path": row["source_path"], "relation": row["relation"],
            })
    for candidate in manifest["manual_delete_candidates"] + manifest["completed_manual_deletions"]:
        items[candidate["path"]] = candidate
    return items


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


def _actual_git_commands(node: ast.AST, forwarders: Iterable[str] = ()) -> set[str]:
    commands = set()
    for call in ast.walk(node):
        if not isinstance(call, ast.Call) or not call.args:
            continue
        if isinstance(call.func, ast.Name) and call.func.id in forwarders:
            commands.update(x.value for x in call.args if isinstance(x, ast.Constant))
            continue
        if ast.unparse(call.func) not in {"subprocess.check_output", "subprocess.run"}:
            continue
        argument = call.args[0]
        if isinstance(argument, (ast.List, ast.Tuple)) and argument.elts:
            if isinstance(argument.elts[0], ast.Constant) and argument.elts[0].value == "git":
                commands.update(x.value for x in argument.elts if isinstance(x, ast.Constant))
    return commands


def _verified_history_delegate(source: str, helper: str) -> bool:
    """Recognize only the explicit blocker-map reader contract and its real helper."""
    tree, helper_tree = ast.parse(source), ast.parse(helper)
    imports = [node for node in tree.body if isinstance(node, ast.ImportFrom)
               and node.module == "conftest"
               and any(alias.name == "GIT_HISTORY" and alias.asname is None for alias in node.names)]
    if len(imports) != 1 or any(isinstance(node, ast.Name) and node.id == "GIT_HISTORY"
                              and isinstance(node.ctx, ast.Store) for node in ast.walk(tree)):
        return False
    constants = {node.targets[0].id: node.value for node in tree.body
                 if isinstance(node, ast.Assign) and len(node.targets) == 1
                 and isinstance(node.targets[0], ast.Name)}
    baseline = constants.get("HISTORICAL_BASELINE")
    if not isinstance(baseline, ast.Constant) or not re.fullmatch(r"[0-9a-f]{40}", str(baseline.value)):
        return False
    try:
        triplets = ast.literal_eval(constants.get("EXPECTED_BASELINE_BLOB_TRIPLETS"))
    except (ValueError, TypeError):
        return False
    if not isinstance(triplets, dict) or not triplets or any(
        not isinstance(row, tuple) or len(row) != 3
        or not re.fullmatch(r"[0-9a-f]{40}", str(row[0]))
        or not isinstance(row[1], int) or row[1] < 0
        or not re.fullmatch(r"[0-9a-f]{64}", str(row[2])) for row in triplets.values()
    ):
        return False
    wrappers = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                and node.name == "git_blob_bytes"]
    classes = [node for node in helper_tree.body if isinstance(node, ast.ClassDef)
               and node.name == "HistoricalGit"]
    if len(wrappers) != 1 or len(classes) != 1:
        return False
    wrapper = wrappers[0]
    required = ast.parse('''
assert revision == HISTORICAL_BASELINE
expected_oid, expected_bytes, expected_sha256 = EXPECTED_BASELINE_BLOB_TRIPLETS[relative_path]
blob = GIT_HISTORY.blob(revision, relative_path)
observed_oid = blob.oid
assert observed_oid == expected_oid, relative_path
object_type = blob.object_type
assert object_type == "blob", relative_path
observed_bytes = blob.byte_count
assert observed_bytes == expected_bytes, relative_path
payload = blob.payload
assert len(payload) == expected_bytes, relative_path
assert hashlib.sha256(payload).hexdigest() == expected_sha256, relative_path
return payload
''').body
    observed = [ast.dump(node) for node in wrapper.body]
    if not all(ast.dump(node) in observed for node in required):
        return False
    if sum(isinstance(node, ast.Return) for node in ast.walk(wrapper)) != 1 or not isinstance(wrapper.body[-1], ast.Return):
        return False
    permitted_calls = {"GIT_HISTORY.blob", "prefetch_baseline_blobs", "len",
                       "hashlib.sha256", "hashlib.sha256(payload).hexdigest"}
    if any(not isinstance(node, (ast.Assign, ast.Assert, ast.Expr, ast.Return)) for node in wrapper.body):
        return False
    if any(ast.unparse(node.func) not in permitted_calls for node in ast.walk(wrapper)
           if isinstance(node, ast.Call)):
        return False
    # Do not allow later assignments to replace a checked value before it is returned.
    assignments = [ast.dump(target) for node in wrapper.body if isinstance(node, ast.Assign)
                   for target in node.targets]
    if len(assignments) != len(set(assignments)):
        return False
    methods = {node.name: node for node in classes[0].body if isinstance(node, ast.FunctionDef)}
    if not {"_commit", "_path", "blobs", "blob"} <= methods.keys():
        return False
    if any(isinstance(node, ast.Call) and (
               isinstance(node.func, ast.Name) and node.func.id == "open"
               or isinstance(node.func, ast.Attribute)
               and node.func.attr in {"open", "read_bytes", "read_text", "write_bytes", "write_text"})
           for node in ast.walk(classes[0])):
        return False
    if "rev-parse" not in _actual_git_commands(methods["_commit"]) or not {
        "cat-file", "--batch"
    } <= _actual_git_commands(methods["blobs"]):
        return False
    helper_checks = {
        "_commit": ["re.fullmatch(r'[0-9a-f]{40}', commit)", "resolved == commit"],
        "blobs": ["len(header) == 3 and header[1] == b'blob'",
                  "len(payload) == size and stream.read(1) == b'\\n'",
                  "oid == header[0].decode('ascii')"],
    }
    for name, checks in helper_checks.items():
        assertions = {ast.dump(node.test) for node in ast.walk(methods[name]) if isinstance(node, ast.Assert)}
        if not all(ast.dump(ast.parse(check, mode="eval").body) in assertions for check in checks):
            return False
    helper_calls = {ast.unparse(node.func) for node in ast.walk(methods["blobs"])
                    if isinstance(node, ast.Call)}
    if not {"self._commit", "self._path", "hashlib.sha1", "hashlib.sha256"} <= helper_calls:
        return False
    binding = ast.parse("GIT_HISTORY = HistoricalGit(Path(__file__).resolve().parents[1])").body[0]
    forwarding = ast.parse("return self.blobs(commit, [source_path])[source_path]").body[0]
    return (any(ast.dump(node) == ast.dump(binding) for node in helper_tree.body)
            and sum(isinstance(node, ast.Name) and node.id == "GIT_HISTORY"
                    and isinstance(node.ctx, ast.Store) for node in ast.walk(helper_tree)) == 1
            and len(methods["blob"].body) == 1
            and ast.dump(methods["blob"].body[0]) == ast.dump(forwarding))


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
    git_forwarders = {
        name for name, function in function_nodes.items()
        if function.args.vararg and len(function.body) == 1
        and isinstance(function.body[0], ast.Return)
        and "git" in _actual_git_commands(function)
        and any(isinstance(node, ast.Starred) and isinstance(node.value, ast.Name)
                and node.value.id == function.args.vararg.arg for node in ast.walk(function))
    }
    immutable_git_readers = {
        name
        for name, function in function_nodes.items()
        if {"cat-file", "rev-parse"} <= _actual_git_commands(function, git_forwarders)
        and any(isinstance(node, ast.Assert) for node in ast.walk(function))
    }
    delegated_reader = source_path == "tests/test_r5_v1_blocker_root_cause_map.py"
    if delegated_reader and _verified_history_delegate(text, read("tests/conftest.py")):
        immutable_git_readers.add("git_blob_bytes")

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
        elif name in physical or (delegated_reader and name == "git_blob_bytes"):
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


def test_registered_retirements_have_no_physical_python_consumer() -> None:
    manifest = load_manifest()
    for candidate in manifest["manual_delete_candidates"] + manifest["completed_manual_deletions"]:
        for reference in candidate["inbound_references"]:
            source = reference["source_path"]
            if not source.endswith(".py") or reference["relation"] != "git_history_only":
                continue
            text = read(source)
            assert "historical_blob_bytes" in text or "historical_blob_file" in text
            assert not _python_dynamic_references(
                source, text, {candidate["path"]: candidate["path"]}
            ), (candidate["path"], source)


def test_retired_python_modules_have_no_live_imports() -> None:
    modules = {
        module: path
        for path in ready_items() if path.endswith(".py")
        for module in (path[:-3].replace("/", "."), Path(path).stem)
    }
    unexpected = []
    for source in iter_active_text_files():
        if source.suffix != ".py":
            continue
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            imported = []
            if isinstance(node, ast.Import):
                imported = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                imported = [node.module or ""] + [
                    f"{node.module}.{alias.name}" for alias in node.names
                ]
            for name in imported:
                if name in modules:
                    unexpected.append((source.relative_to(ROOT).as_posix(), modules[name]))
    assert unexpected == []


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
                if reader["source_path"] == "tests/test_r5_v1_blocker_root_cause_map.py":
                    assert _verified_history_delegate(source, read("tests/conftest.py")), reader
                else:
                    tree = ast.parse(source)
                    assert {"cat-file", "rev-parse"} <= _actual_git_commands(tree), reader
                    assert any(isinstance(node, ast.Call) and ast.unparse(node.func)
                               in {"hashlib.sha256", "hashlib.sha1"} for node in ast.walk(tree)), reader
                    assert any(isinstance(node, (ast.Assert, ast.Raise)) for node in ast.walk(tree)), reader
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
    physical_declared = {
        source for source in declared_surfaces if (ROOT / source).is_file()
    }
    approved_missing = set(declared_surfaces) - physical_declared
    ready = set(manifest["retired_paths"]) | {
        row["path"] for row in manifest["manual_delete_candidates"] + manifest["completed_manual_deletions"]
    }
    assert unexpected == {}
    if approved_missing:
        assert manifest["deletion_control"]["prior_approvals_apply_to_new_candidates"] is False
        assert approved_missing <= ready
    assert observed.get("old_002837_workflow", set()) == physical_declared


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


def test_history_delegate_rejects_spoofed_or_weakened_wrapper_contracts() -> None:
    source = read("tests/test_r5_v1_blocker_root_cause_map.py")
    helper = read("tests/conftest.py")
    assert _verified_history_delegate(source, helper)
    changes = (
        ("from conftest import GIT_HISTORY", "from elsewhere import GIT_HISTORY"),
        ("GIT_HISTORY.blob(revision, relative_path)", "other.blob(revision, relative_path)"),
        ('HISTORICAL_BASELINE = "a96c1b717bf15905d72fd142efd946fa01bce666"',
         'HISTORICAL_BASELINE = "HEAD"'),
        ("assert observed_oid == expected_oid, relative_path", "assert observed_oid"),
        ("assert object_type == \"blob\", relative_path", "assert object_type"),
        ("assert len(payload) == expected_bytes, relative_path", "assert payload"),
        ("assert hashlib.sha256(payload).hexdigest() == expected_sha256, relative_path", "assert payload"),
        ("return payload", "return (ROOT / relative_path).read_bytes()"),
    )
    for old, new in changes:
        assert old in source
        assert not _verified_history_delegate(source.replace(old, new, 1), helper), old
    assert not _verified_history_delegate(source + "\nGIT_HISTORY = object()\n", helper)


def test_history_delegate_requires_helper_commands_and_integrity_checks() -> None:
    source = read("tests/test_r5_v1_blocker_root_cause_map.py")
    helper = read("tests/conftest.py")
    changes = (
        ('"rev-parse"', '"not-rev-parse"'),
        ('"cat-file"', '"not-cat-file"'),
        ('assert oid == header[0].decode("ascii")', 'assert oid'),
        ('assert len(payload) == size and stream.read(1) == b"\\n"', 'assert payload'),
        ("hashlib.sha1(", "hashlib.md5("),
        ("self._commit(commit)", "self.other(commit)"),
        ("paths = list(dict.fromkeys(source_paths))",
         "paths = list(dict.fromkeys(source_paths))\n        self.root.read_bytes()"),
        ("payload = stream.read(size)",
         "payload = open(self.root / path, 'rb').read()"),
    )
    for old, new in changes:
        assert old in helper
        assert not _verified_history_delegate(source, helper.replace(old, new, 1)), old
    assert not _verified_history_delegate(source, helper + "\nGIT_HISTORY = object()\n")


def test_dynamic_scanner_checks_delegate_and_ignores_comment_only_git_evidence() -> None:
    candidate = "reports/workflow_runs/example_retired_run/input.yaml"
    tokens = {candidate: candidate}
    path = "tests/test_r5_v1_blocker_root_cause_map.py"
    source = read(path) + f"\ngit_blob_bytes(HISTORICAL_BASELINE, {candidate!r})\n"
    assert _python_dynamic_references(path, source, tokens) == set()
    spoofed = source.replace("from conftest import GIT_HISTORY", "from elsewhere import GIT_HISTORY")
    assert _python_dynamic_references(path, spoofed, tokens) == {candidate}
    comment_only = f'''\nfrom pathlib import Path\ndef historical_blob():\n    """cat-file rev-parse assert"""\n    return Path({candidate!r}).read_bytes()\nhistorical_blob()\n'''
    assert _python_dynamic_references("spoofed_reader.py", comment_only, tokens) == {candidate}


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
    workflow = yaml.safe_load(manual)
    command = workflow["jobs"]["provenance-and-replay"]["steps"][-1]["run"].strip()
    assert command == "python -m pytest -q -m legacy_compatibility"
    assert "pytestmark = pytest.mark.legacy_compatibility" in read(
        "tests/test_r5_v1_replay_002837.py"
    )
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
        "scripts/build_r5_reader_section_payloads.py",
        "src/ingest/business_segment_extraction.py",
        "src/qa/r4_disclosure_backflow_review.py",
    )
    for path in explicit_cli_paths:
        source = read(path)
        assert 'add_argument("--workflow-run", required=True)' in source, path

    backflow = read("src/research/r5_bundle13r_evidence_backflow.py")
    assert '(output_root.parent / "bundle12r_rerun_after_13r").as_posix()' in backflow


def test_retained_bundle_evaluators_are_explicit_and_noncanonical() -> None:
    bundle11 = read("scripts/run_r5_bundle11r_runtime.py")
    bundle12 = read("scripts/run_r5_bundle12r_operating_evidence_gate.py")
    bundle13 = read("scripts/run_r5_bundle13r_evidence_backflow.py")
    sources = "\n".join(
        read(path)
        for path in (
            "scripts/run_r5_bundle11r_runtime.py",
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
    workflow = yaml.safe_load(ci)
    commands = [step.get("run", "").strip() for step in workflow["jobs"]["tests"]["steps"]]

    assert "fetch-depth: 0" in ci
    assert "tests/test_r5_night_shift_" not in ci
    assert "reports/p1_6/r5_night_shift/" not in ci
    assert "reports/p1_6/r5_bundle17r" not in ci
    assert "python -m pytest -q" in commands
    assert "python -m py_compile $(git ls-files '*.py')" in commands
    for path in (
        "tests/test_r5_bundle11r_runtime_contracts.py",
        "tests/test_r5_bundle11r_runtime_engine.py",
        "tests/test_r5_bundle11r_runtime_semantic.py",
    ):
        source = read(path)
        assert "def test_" in source
        assert "legacy_compatibility" not in source
    assert "test_runtime_cli_matches_engine_output_and_exit_code" in read(
        "tests/test_r5_bundle11r_runtime_engine.py"
    )
