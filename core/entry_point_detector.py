"""Detects probable application entry points using static (AST) analysis.

Never imports or executes any file under the scanned project.
"""
from __future__ import annotations

import ast
from pathlib import Path

from models.project import EntryPointCandidate, EntryPointConfidence
from utils.logging_config import get_logger

logger = get_logger("entry_point_detector")

_STRONG_NAME_HINTS = {"main.py": "Named 'main.py', a conventional entry point.",
                       "app.py": "Named 'app.py', a conventional entry point.",
                       "run.py": "Named 'run.py', a conventional entry point.",
                       "launcher.py": "Named 'launcher.py', a conventional entry point."}

_WEAK_NAME_HINTS = {"__main__.py": "Named '__main__.py', used as a package entry point."}


def _has_dunder_main_block(tree: ast.Module) -> bool:
    """True if the module contains `if __name__ == "__main__":`."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        if not isinstance(test, ast.Compare):
            continue
        left, right = test.left, test.comparators[0] if test.comparators else None
        names = []
        for side in (left, right):
            if isinstance(side, ast.Name):
                names.append(side.id)
            elif isinstance(side, ast.Constant):
                names.append(side.value)
        if "__name__" in names and "__main__" in names:
            return True
    return False


def _has_gui_mainloop_call(tree: ast.Module) -> bool:
    """True if the module calls something like `.mainloop()` or `App().run()`."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in ("mainloop", "run", "exec", "exec_"):
                return True
    return False


class EntryPointDetector:
    """Ranks candidate entry points among a project's Python files."""

    def detect(self, python_files: list[Path]) -> list[EntryPointCandidate]:
        candidates: list[EntryPointCandidate] = []

        for file_path in python_files:
            reasons: list[str] = []
            score = 0

            name = file_path.name
            if name in _STRONG_NAME_HINTS:
                reasons.append(_STRONG_NAME_HINTS[name])
                score += 3
            elif name in _WEAK_NAME_HINTS:
                reasons.append(_WEAK_NAME_HINTS[name])
                score += 1

            tree = self._safe_parse(file_path)
            if tree is None:
                if reasons:
                    # Name hint alone, but file has a syntax error — still
                    # surface it, with a low-confidence note, so the user
                    # isn't left with zero candidates.
                    reasons.append("File has a syntax error; could not confirm with AST analysis.")
                    candidates.append(
                        EntryPointCandidate(
                            path=file_path,
                            confidence=EntryPointConfidence.LOW,
                            reasons=tuple(reasons),
                        )
                    )
                continue

            if _has_dunder_main_block(tree):
                reasons.append('Contains an `if __name__ == "__main__":` block.')
                score += 3

            if _has_gui_mainloop_call(tree):
                reasons.append("Calls a GUI main-loop / run method (e.g. mainloop(), .run()).")
                score += 1

            if not reasons:
                continue

            if score >= 4:
                confidence = EntryPointConfidence.HIGH
            elif score >= 2:
                confidence = EntryPointConfidence.MEDIUM
            else:
                confidence = EntryPointConfidence.LOW

            candidates.append(
                EntryPointCandidate(path=file_path, confidence=confidence, reasons=tuple(reasons))
            )

        order = {EntryPointConfidence.HIGH: 0, EntryPointConfidence.MEDIUM: 1, EntryPointConfidence.LOW: 2}
        candidates.sort(key=lambda c: (order[c.confidence], c.path.name))
        return candidates

    @staticmethod
    def _safe_parse(file_path: Path) -> ast.Module | None:
        try:
            source = file_path.read_text(encoding="utf-8", errors="replace")
            return ast.parse(source, filename=str(file_path))
        except (SyntaxError, OSError, UnicodeError) as exc:
            logger.debug("Could not parse %s: %s", file_path, exc)
            return None
