"""Conservative V1 risk catalog. Unknown actions/domains cannot be authorized."""

from .models import Risk

LEVELS: tuple[Risk, ...] = ("low", "medium", "high", "critical")
ACTION_RISK: dict[str, Risk] = {
    "read": "low", "turn_on": "medium", "turn_off": "medium",
    "toggle": "medium", "set_value": "medium", "set_brightness": "medium",
    "set_color": "low", "set_temperature": "high", "open": "high",
    "close": "medium", "stop": "medium", "lock": "medium", "unlock": "high",
    "arm": "medium", "disarm": "high", "reset": "high", "acknowledge": "low",
    "start": "high", "stop_process": "critical",
}
DOMAIN_FLOOR: dict[str, Risk] = {
    "light": "low", "sensor": "low", "switch": "medium", "climate": "medium",
    "cover": "medium", "lock": "high", "alarm": "high", "valve": "high",
    "machine": "critical",
}


def classify_risk(action: str, domain: str) -> Risk:
    return max(
        ACTION_RISK.get(action, "critical"), DOMAIN_FLOOR.get(domain, "critical"),
        key=LEVELS.index,
    )
