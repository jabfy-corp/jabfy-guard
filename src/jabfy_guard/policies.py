"""Load trusted local policy files. No permissive fallback on invalid configuration."""

import json
from pathlib import Path

from .models import Command, Context, Policy, PolicySet


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate policy JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"Non-finite JSON constant: {value}")


def load_policies(path: str | Path) -> PolicySet:
    data = json.loads(Path(path).read_text(encoding="utf-8"),
                      object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    return PolicySet.model_validate(data)


def matches_scope(rule: Policy, command: Command, context: Context) -> bool:
    return (
        rule.home_id == command.home_id
        and bool(set(rule.roles) & set(context.roles))
        and command.device_id in rule.devices
        and command.action in rule.actions
    )
