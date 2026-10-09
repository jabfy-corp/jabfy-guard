import pytest

from jabfy_guard import evaluate


def decision(simulation=False, permission=False, action="unlock", params=None, parameters=None):
    return evaluate(
        {"correlation_id": "r", "home_id": "h", "device_id": "d", "action": action, "params": params or {}},
        {"home_id": "h", "actor_id": "server", "roles": ["resident"], "mode": "normal",
         "simulation": simulation, "observed_at": 100.0,
         "devices": {"d": {"domain": "lock" if action == "unlock" else "light",
                            "actions": {action: {"parameters": parameters or {}}}}}},
        {"version": "v1", "rules": [{"id": "p", "effect": "allow", "home_id": "h",
         "roles": ["resident"], "devices": ["d"], "actions": [action],
         "allow_sensitive_simulation": permission}]}, now=100.0,
    )


@pytest.mark.parametrize("simulation,permission,allowed", [(False, False, False),
    (False, True, False), (True, False, False), (True, True, True)])
def test_sensitive_permission_is_only_for_trusted_simulation(simulation, permission, allowed):
    assert decision(simulation, permission).allowed is allowed


@pytest.mark.parametrize("color,allowed", [({"r": 10, "g": 20, "b": 30}, True),
    ({"r": True, "g": 20, "b": 30}, False), ({"r": 256, "g": 20, "b": 30}, False),
    ({"r": 1, "g": 2}, False), ({"r": 1, "g": 2, "b": 3, "extra": 0}, False),
    ({"r": float("nan"), "g": 2, "b": 3}, False)])
def test_rgb_strict_contract(color, allowed):
    parameters = {"color": {"type": "object", "properties": {
        key: {"type": "integer", "minimum": 0, "maximum": 255} for key in "rgb"
    }}}
    assert decision(action="set_color", params={"color": color}, parameters=parameters).allowed is allowed


def test_unknown_critical_action_cannot_be_enabled_for_simulation():
    assert not decision(True, True, action="unknown").allowed
