"""Materialize a fixture directory into a temporary git repository with a file:// URL.

Fixtures are stored as plain directories so the main repository does not contain nested .git dirs.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


def materialize(name: str, root: Path | None = None) -> str:
    src = FIXTURES / name
    if not src.is_dir():
        raise FileNotFoundError(f"fixture {name} not found under {FIXTURES}")
    dest = Path(root or tempfile.mkdtemp(prefix="archon-fixture-")) / name
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns(".git", "__pycache__", ".venv", "*.egg-info"))
    env = {
        "GIT_AUTHOR_NAME": "ARCHON Fixtures",
        "GIT_AUTHOR_EMAIL": "fixtures@example.com",
        "GIT_COMMITTER_NAME": "ARCHON Fixtures",
        "GIT_COMMITTER_EMAIL": "fixtures@example.com",
        "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
    }
    for cmd in (
        ["git", "init", "-q", "-b", "main"],
        ["git", "add", "-A"],
        ["git", "commit", "-q", "-m", f"fixture {name}"],
    ):
        subprocess.run(cmd, cwd=dest, env=env, check=True, capture_output=True)
    return f"file://{dest}"
