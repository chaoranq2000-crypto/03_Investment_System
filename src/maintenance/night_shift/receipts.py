"""Trusted acceptance-command execution and deterministic execution receipts."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .models import ContractError
from .queue import atomic_write


RECEIPT_SCHEMA_VERSION = "r5_night_shift_execution_receipt_v1"
FAILURE_PACKET_SCHEMA_VERSION = "r5_night_shift_failure_packet_v1"
TRUSTED_EXECUTABLES = {"python", "python3", "pytest", "git"}
TRUSTED_GIT_SUBCOMMANDS = {
    "diff",
    "status",
    "rev-parse",
    "ls-files",
    "ls-remote",
    "show",
}
SHELL_CONTROL = re.compile(r"(?:&&|\|\||[|;&<>`\r\n])")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def parse_trusted_command(command: str) -> list[str]:
    if not command.strip():
        raise ContractError("acceptance command must not be empty")
    if "<" in command and ">" in command:
        raise ContractError(f"acceptance command contains an unresolved placeholder: {command}")
    if SHELL_CONTROL.search(command):
        raise ContractError(f"acceptance command contains shell control syntax: {command}")
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError as exc:
        raise ContractError(f"acceptance command cannot be parsed: {command}: {exc}") from exc
    if not tokens:
        raise ContractError("acceptance command must not be empty")
    executable = Path(tokens[0]).name.casefold()
    if executable.endswith(".exe"):
        executable = executable[:-4]
    if executable not in TRUSTED_EXECUTABLES:
        raise ContractError(f"acceptance executable is not trusted: {tokens[0]}")
    if executable in {"python", "python3"}:
        tokens[0] = sys.executable
    elif executable == "pytest":
        tokens = [sys.executable, "-m", "pytest", *tokens[1:]]
    elif executable == "git":
        if len(tokens) < 2 or tokens[1] not in TRUSTED_GIT_SUBCOMMANDS:
            subcommand = tokens[1] if len(tokens) > 1 else ""
            raise ContractError(f"git acceptance subcommand is not trusted: {subcommand!r}")
        tokens[0] = "git"
    return tokens


@dataclass(frozen=True)
class CommandReceipt:
    command: str
    argv: tuple[str, ...]
    exit_code: int
    stdout_length: int
    stdout_sha256: str
    stdout_summary: str
    stderr_length: int
    stderr_sha256: str
    stderr_summary: str

    def to_mapping(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "argv": list(self.argv),
            "exit_code": self.exit_code,
            "stdout_length": self.stdout_length,
            "stdout_sha256": self.stdout_sha256,
            "stdout_summary": self.stdout_summary,
            "stderr_length": self.stderr_length,
            "stderr_sha256": self.stderr_sha256,
            "stderr_summary": self.stderr_summary,
        }


def output_summary(payload: bytes, *, limit: int = 2000) -> str:
    text = payload[-limit:].decode("utf-8", errors="replace")
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def run_acceptance_commands(
    commands: Sequence[str],
    *,
    cwd: Path,
    environment: dict[str, str] | None = None,
) -> tuple[list[CommandReceipt], int]:
    receipts: list[CommandReceipt] = []
    overall = 0
    run_environment = os.environ.copy()
    if environment:
        run_environment.update(environment)
    for command in commands:
        argv = parse_trusted_command(command)
        completed = subprocess.run(
            argv,
            cwd=cwd,
            env=run_environment,
            check=False,
            capture_output=True,
        )
        stdout = completed.stdout or b""
        stderr = completed.stderr or b""
        receipts.append(
            CommandReceipt(
                command=command,
                argv=tuple(argv),
                exit_code=completed.returncode,
                stdout_length=len(stdout),
                stdout_sha256=sha256_bytes(stdout),
                stdout_summary=output_summary(stdout),
                stderr_length=len(stderr),
                stderr_sha256=sha256_bytes(stderr),
                stderr_summary=output_summary(stderr),
            )
        )
        if completed.returncode:
            overall = completed.returncode
            break
    return receipts, overall


def git_value(cwd: Path, *args: str) -> str | None:
    completed = subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip() if completed.returncode == 0 else None


def changed_paths(cwd: Path) -> list[str]:
    completed = subprocess.run(
        ["git", "-C", str(cwd), "status", "--porcelain=v1", "--untracked-files=normal"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode:
        return []
    paths: list[str] = []
    for line in completed.stdout.splitlines():
        value = line[3:] if len(line) >= 4 else line
        if " -> " in value:
            value = value.split(" -> ", 1)[1]
        paths.append(value.replace("\\", "/"))
    return sorted(set(paths))


def artifact_records(cwd: Path, artifacts: Sequence[str]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    root = cwd.resolve()
    for value in sorted(set(artifacts)):
        if "<" in value and ">" in value:
            raise ContractError(f"required artifact has unresolved placeholder: {value}")
        candidate = (root / value).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise ContractError(f"required artifact escapes repository: {value}") from exc
        if not candidate.is_file() or candidate.is_symlink():
            records.append(
                {
                    "path": value.replace("\\", "/"),
                    "present": False,
                    "sha256": None,
                    "size_bytes": None,
                }
            )
            continue
        records.append(
            {
                "path": value.replace("\\", "/"),
                "present": True,
                "sha256": sha256_file(candidate),
                "size_bytes": candidate.stat().st_size,
            }
        )
    return records


def stable_receipt_projection(receipt: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in receipt.items()
        if key not in {"started_at", "finished_at", "stable_receipt_sha256"}
    }


def build_receipt(
    *,
    run_id: str,
    task_id: str,
    attempt: int,
    executor: str,
    cwd: Path,
    commands: Sequence[CommandReceipt],
    exit_code: int,
    artifacts: Sequence[str],
    started_at: datetime,
    finished_at: datetime,
    terminal_status: str,
    reason: str,
    blocker_claimed: int = 0,
    blocker_resolved: int = 0,
    blocker_unchanged: int = 0,
    remote_sha: str | None = None,
) -> dict[str, Any]:
    if blocker_resolved > blocker_claimed:
        raise ContractError("resolved blocker count cannot exceed claimed blocker count")
    local_commit_sha = git_value(cwd, "rev-parse", "HEAD")
    local_tree_sha = git_value(cwd, "rev-parse", "HEAD^{tree}")
    receipt: dict[str, Any] = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "run_id": run_id,
        "task_id": task_id,
        "attempt": attempt,
        "started_at": started_at.astimezone(timezone.utc).isoformat(),
        "finished_at": finished_at.astimezone(timezone.utc).isoformat(),
        "executor": executor,
        "cwd": str(cwd.resolve()),
        "commands": [item.to_mapping() for item in commands],
        "exit_code": exit_code,
        "changed_paths": changed_paths(cwd),
        "required_artifacts": artifact_records(cwd, artifacts),
        "local_commit_sha": local_commit_sha,
        "remote_commit_sha": remote_sha,
        "implementation_identity": {
            "commit_sha": local_commit_sha,
            "tree_sha": local_tree_sha,
            "publication_head": None,
        },
        "blocker_occurrences": {
            "claimed": blocker_claimed,
            "resolved": blocker_resolved,
            "unchanged": blocker_unchanged,
        },
        "terminal_status": terminal_status,
        "reason": reason,
    }
    receipt["stable_receipt_sha256"] = sha256_bytes(
        canonical_json_bytes(stable_receipt_projection(receipt))
    )
    return receipt


def write_receipt(path: Path, receipt: dict[str, Any]) -> None:
    supplied = str(receipt.get("stable_receipt_sha256") or "").casefold()
    if not SHA256_PATTERN.fullmatch(supplied):
        raise ContractError(
            "receipt.stable_receipt_sha256: expected 64 hexadecimal characters"
        )
    calculated = sha256_bytes(
        canonical_json_bytes(stable_receipt_projection(receipt))
    )
    if supplied != calculated:
        raise ContractError(
            "receipt.stable_receipt_sha256 does not match the recomputed payload"
        )
    payload = (
        json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")
    atomic_write(path, payload)
    try:
        written = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"receipt[{path}]: cannot verify written JSON: {exc}") from exc
    verified = sha256_bytes(
        canonical_json_bytes(stable_receipt_projection(written))
    )
    if verified != supplied:
        raise ContractError(
            f"receipt[{path}]: digest changed after write; expected {supplied}, got {verified}"
        )


def write_validation_report(
    path: Path, receipt: Mapping[str, Any], *, receipt_path: Path
) -> None:
    lines = [
        "# Night-shift validation record",
        "",
        f"- Run ID: `{receipt.get('run_id')}`",
        f"- Task ID: `{receipt.get('task_id')}`",
        f"- Terminal status: `{receipt.get('terminal_status')}`",
        f"- Receipt: `{receipt_path.as_posix()}`",
        "",
        "| Exit | Command | Output summary |",
        "|---:|---|---|",
    ]
    for command in receipt.get("commands", []):
        summary_lines = str(command.get("stdout_summary") or "").splitlines()
        summary = summary_lines[-1] if summary_lines else ""
        lines.append(
            f"| {command.get('exit_code')} | `{command.get('command')}` | "
            f"{summary.replace('|', '/')} |"
        )
    lines.extend(
        [
            "",
            "All command bodies are represented by exit code, byte length and SHA-256 in the receipt.",
            "",
        ]
    )
    atomic_write(path, "\n".join(lines).encode("utf-8"))


def execute_acceptance(
    *,
    run_id: str,
    task_id: str,
    attempt: int,
    executor: str,
    cwd: Path,
    commands: Sequence[str],
    artifacts: Sequence[str],
    receipt_path: Path,
    failure_status: str = "failed_retryable",
    reason: str = "",
    blocker_claimed: int = 0,
    blocker_resolved: int = 0,
    blocker_unchanged: int = 0,
    now: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    clock = now or (lambda: datetime.now(tz=timezone.utc))
    started = clock()
    command_receipts, exit_code = run_acceptance_commands(commands, cwd=cwd)
    finished = clock()
    artifacts_state = artifact_records(cwd, artifacts)
    artifacts_present = all(item["present"] for item in artifacts_state)
    terminal_status = "passed" if exit_code == 0 and artifacts_present else failure_status
    final_reason = reason
    if exit_code == 0 and not artifacts_present and not final_reason:
        final_reason = "one or more required artifacts are missing"
    receipt = build_receipt(
        run_id=run_id,
        task_id=task_id,
        attempt=attempt,
        executor=executor,
        cwd=cwd,
        commands=command_receipts,
        exit_code=exit_code,
        artifacts=artifacts,
        started_at=started,
        finished_at=finished,
        terminal_status=terminal_status,
        reason=final_reason,
        blocker_claimed=blocker_claimed,
        blocker_resolved=blocker_resolved,
        blocker_unchanged=blocker_unchanged,
    )
    write_receipt(receipt_path, receipt)
    return receipt


def write_failure_packet(
    path: Path,
    *,
    run_id: str,
    task_id: str,
    failure_type: str,
    observed: str,
    expected: str,
    next_action: str,
) -> None:
    lines = [
        "# Night-shift failure packet",
        "",
        f"- Schema: `{FAILURE_PACKET_SCHEMA_VERSION}`",
        f"- Run ID: `{run_id}`",
        f"- Task ID: `{task_id}`",
        f"- Failure type: `{failure_type}`",
        f"- Observed: {observed}",
        f"- Expected: {expected}",
        f"- Next action: {next_action}",
        "- Research blocker resolved: `false`",
        "- Canonical/sample-quality/P2 mutation: `false`",
        "",
    ]
    atomic_write(path, "\n".join(lines).encode("utf-8"))
