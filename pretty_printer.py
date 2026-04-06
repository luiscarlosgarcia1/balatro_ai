from __future__ import annotations

from dataclasses import fields, is_dataclass
from datetime import datetime, timezone
from pathlib import Path

from balatro_ai.models import GameObservation
from balatro_ai.observation import BalatroObserver


PRINTS_DIR = Path("prints")
INDENT = "  "


def _format_value(value: object, *, level: int = 0) -> str:
    indent = INDENT * level
    child_indent = INDENT * (level + 1)

    if is_dataclass(value):
        lines = [f"{type(value).__name__}("]
        for field in fields(value):
            field_value = getattr(value, field.name)
            rendered = _format_value(field_value, level=level + 1)
            lines.append(f"{child_indent}{field.name}={rendered},")
        lines.append(f"{indent})")
        return "\n".join(lines)

    if isinstance(value, tuple):
        if not value:
            return "()"
        lines = ["("]
        for item in value:
            lines.append(f"{child_indent}{_format_value(item, level=level + 1)},")
        lines.append(f"{indent})")
        return "\n".join(lines)

    if isinstance(value, list):
        if not value:
            return "[]"
        lines = ["["]
        for item in value:
            lines.append(f"{child_indent}{_format_value(item, level=level + 1)},")
        lines.append(f"{indent}]")
        return "\n".join(lines)

    if isinstance(value, dict):
        if not value:
            return "{}"
        lines = ["{"]
        for key, item in value.items():
            rendered_item = _format_value(item, level=level + 1)
            lines.append(f"{child_indent}{repr(key)}: {rendered_item},")
        lines.append(f"{indent}}}")
        return "\n".join(lines)

    return repr(value)


def render_observation(observation: GameObservation) -> str:
    """Return a readable dataclass tree for the exact typed observation values."""

    return _format_value(observation)


def write_observation_print(
    observation: GameObservation,
    *,
    output_dir: Path = PRINTS_DIR,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_path = output_dir / f"game_observation_{timestamp}.txt"
    counter = 1
    while output_path.exists():
        output_path = output_dir / f"game_observation_{timestamp}_{counter}.txt"
        counter += 1

    output_path.write_text(render_observation(observation), encoding="utf-8")
    return output_path


def main() -> None:
    observation = BalatroObserver().observe()
    output_path = write_observation_print(observation)
    print(f"GameObservation printed to {output_path}")


if __name__ == "__main__":
    main()
