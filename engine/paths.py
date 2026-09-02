"""
Where persistent, writable state lives.

Locally, that's the repo root -- `warehouse/` and `data/raw/` sit right next
to the code, which is what every test and the local dev workflow already
expect. On a serverless deploy (Vercel's Lambda-based runtime mounts the
deployed code read-only; only `/tmp` is writable) writing there raises
`OSError: [Errno 30] Read-only file system`, which is exactly what took down
every endpoint that touches the warehouse, the feedback store, or the LLM
cache the first time this app was deployed there.

Every module that writes persistent state (`engine/warehouse.py`,
`feedback/store.py`, `narrative/provider.py`, `data/generate.py`) roots
its output through `writable_root()` instead of hardcoding the repo root,
so the same code works unmodified in both places. On a read-only deploy,
state lives under the OS temp dir instead: it survives for the life of a
warm container (so a cold request regenerates the ~326k-row synthetic
dataset once, subsequent warm requests reuse it) and is regenerated
cheaply if a fresh container drops it -- there is nothing here a real
deployment would need to persist across cold starts, since it is entirely
derived from `data/generate.py`'s deterministic, seeded output.
"""
from __future__ import annotations

import os
import pathlib
import tempfile

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

_writable_root: pathlib.Path | None = None


def _can_write(path: pathlib.Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_test"
        probe.touch()
        probe.unlink()
        return True
    except OSError:
        return False


def writable_root() -> pathlib.Path:
    """The repo root if it's actually writable, otherwise a stable directory
    under the OS temp dir. Resolved once per process and cached -- the
    filesystem's writability doesn't change mid-process, and re-probing it
    on every call would mean a stat + touch + unlink on every single request."""
    global _writable_root
    if _writable_root is not None:
        return _writable_root

    # VERCEL is set unconditionally by the platform (build and runtime) --
    # trust it over probing when present, since a probe against `/var/task`
    # can behave inconsistently across providers, and this is the one we
    # know for certain is read-only.
    if os.environ.get("VERCEL") or not _can_write(REPO_ROOT):
        _writable_root = pathlib.Path(tempfile.gettempdir()) / "businessintelligence-ai"
    else:
        _writable_root = REPO_ROOT
    return _writable_root
