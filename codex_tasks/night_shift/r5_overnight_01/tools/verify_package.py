from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import yaml


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else '.').resolve()
    required = [
        'START_HERE.md',
        'PACKAGE_MANIFEST.yaml',
        'CODEX_SCHEDULED_TASK_PROMPT.md',
        'OVERNIGHT_MISSION.md',
        'EXECPLAN.md',
        'task_queue.yaml',
        'acceptance_matrix.yaml',
        'SAFETY_AND_GIT_POLICY.md',
        'BF2_INPUT_HANDOFF.md',
        'contracts/night_shift_task_queue.schema.json',
        'contracts/morning_readout.schema.json',
    ]
    missing = [name for name in required if not (root / name).is_file()]
    if missing:
        print('Missing required files:')
        for name in missing:
            print(f'  - {name}')
        return 2

    manifest = yaml.safe_load((root / 'PACKAGE_MANIFEST.yaml').read_text(encoding='utf-8'))
    queue = yaml.safe_load((root / 'task_queue.yaml').read_text(encoding='utf-8'))
    schema = json.loads((root / 'contracts/night_shift_task_queue.schema.json').read_text(encoding='utf-8'))
    json.loads((root / 'contracts/morning_readout.schema.json').read_text(encoding='utf-8'))

    assert manifest['package_id'] == 'r5_overnight_01_autonomous_harness_and_bf2_activation'
    assert queue['schema_version'] == schema['properties']['schema_version']['const']
    ids = [task['id'] for task in queue['tasks']]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate task IDs')
    known = set(ids)
    for task in queue['tasks']:
        unknown = set(task['depends_on']) - known
        if unknown:
            raise ValueError(f"{task['id']} has unknown dependencies: {sorted(unknown)}")

    checksums = root / 'CHECKSUMS.sha256'
    if checksums.exists():
        for line in checksums.read_text(encoding='utf-8').splitlines():
            if not line.strip():
                continue
            expected, rel = line.split('  ', 1)
            path = root / rel
            if rel == 'CHECKSUMS.sha256':
                continue
            actual = sha256(path)
            if actual != expected:
                raise ValueError(f'Checksum mismatch: {rel}')

    print(f'Package OK: {root}')
    print(f'Tasks: {len(ids)}')
    print(f"Baseline SHA: {manifest['repository']['source_commit']}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
