from __future__ import annotations

from pathlib import Path
from string import Template


class TemplateEngine:
    def __init__(self, root: str = "templates") -> None:
        self._root = Path(root)

    def render(self, name: str, context: dict[str, object]) -> str:
        source = (self._root / name).read_text(encoding="utf-8")
        return Template(source).safe_substitute({k: str(v) for k, v in context.items()})
