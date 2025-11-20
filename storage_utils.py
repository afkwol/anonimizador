import os
import time
from pathlib import Path
from typing import Iterable


def cleanup_old_artifacts(paths: Iterable[Path], ttl_days: int) -> None:
    """Delete files older than ttl_days in provided directories."""
    if ttl_days <= 0:
        return

    cutoff = time.time() - (ttl_days * 24 * 3600)
    for root in paths:
        if not root.exists() or not root.is_dir():
            continue
        for entry in root.iterdir():
            try:
                if entry.is_file() and entry.stat().st_mtime < cutoff:
                    entry.unlink()
            except OSError:
                # Best-effort cleanup; ignore deletion errors.
                continue
