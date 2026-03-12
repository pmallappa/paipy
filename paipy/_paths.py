"""Internal path resolution — single source of truth for PAI_DIR helpers.

All paipy submodules and external handlers import from here instead of
duplicating the six-line pattern locally.
"""

import os
from pathlib import Path
from typing import Optional


_pai_dir: Optional[str] = None


def get_pai_dir() -> str:
    """Return PAI_DIR as a resolved string (lazy-cached per process)."""
    global _pai_dir
    if _pai_dir is None:
        raw = os.environ.get("PAI_DIR", str(Path.home() / ".claude"))
        _pai_dir = os.path.expandvars(raw).replace("~", str(Path.home()))
    return _pai_dir


def pai_path(*segments: str) -> str:
    """Join path segments onto PAI_DIR."""
    return os.path.join(get_pai_dir(), *segments)


def memory_path(*segments: str) -> str:
    """Join path segments onto <project_root>/.claude_data/memory/."""
    base = os.path.join(os.path.dirname(get_pai_dir()), ".claude_data", "MEMORY")
    return os.path.join(base, *segments)


class Paths:
    """Class-based facade over path resolution functions."""

    @staticmethod
    def pai_dir() -> Path:
        """Return Path to the PAI root directory ($PAI_DIR or ~/.claude)."""
        return Path(get_pai_dir())

    @staticmethod
    def project_dir() -> Path:
        """Return Path to the project root (parent of .claude/)."""
        return Paths.pai_dir().parent

    @staticmethod
    def data_dir() -> Path:
        """Return Path to project-specific data directory (.claude_data/)."""
        return Paths.project_dir() / ".claude_data"

    @staticmethod
    def memory(subpath: str = "") -> Path:
        """Return (and create) a MEMORY subdirectory path under .claude_data/."""
        p = Paths.data_dir() / "MEMORY" / subpath if subpath else Paths.data_dir() / "MEMORY"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @staticmethod
    def settings_file() -> Path:
        """Return Path to settings.json."""
        return Paths.pai_dir() / "settings.json"

    @staticmethod
    def pai_str() -> str:
        """Return PAI_DIR as a string."""
        return get_pai_dir()

    @staticmethod
    def memory_str(*segments: str) -> str:
        """Join path segments onto <project_root>/.claude_data/memory/ as string."""
        return memory_path(*segments)
