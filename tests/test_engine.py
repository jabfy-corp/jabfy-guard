from copy import deepcopy

import pytest

from jabfy_guard import Command, Context, PolicySet, evaluate


@pytest.fixture
def inputs():
    command = dict(correlation_id="request-1", home_id="home", device_id="lamp",
                   action="set_brightness", params={"brightness": 50})
    parameter = {"type": "integer", "minimum": 0, "maximum": 100}
    context = dict(home_id="home", actor_id="alice", roles=["resident"], mode="normal",
                   observed_at=100.0, devices={"lamp": {"domain": "light", "actions": {
                       "set_brightness": {"parameters": {"brightness": parameter}}
                   }}}, recent_counts={"light": 0})
    policies = dict(version="v1", rules=[dict(id="light", effect="allow", home_id="home",
                    roles=["resident"], devices=["lamp"], actions=["set_brightness"],
                    parameters={"brightness": parameter}, max_per_minute=3)])
    return command, context, policies


def test_allow_and_traceability(inputs):
    result = evaluate(*inputs, now=101.0)
    assert result.allowed
    assert result.code == "ALLOWED"
    assert result.risk == "medium"
    assert result.policy_version == "v1"
    assert result.policy_ids == ["light"]
    assert result.correlation_id == "request-1"


@pytest.mark.parametrize("value", [True, 50.0, "50", -1, 101, None, [], {}, float("nan"), float("inf")])
def test_invalid_parameter_values(inputs, value):
    inputs[0]["params"]["brightness"] = value
    assert not evaluate(*inputs, now=101.0).allowed


@pytest.mark.parametrize("params", [{}, {"brightness": 50, "target": "mqtt://evil"}])
def test_missing_or_extra_parameters(inputs, params):
    inputs[0]["params"] = params
    assert evaluate(*inputs, now=101.0).code == "INVALID_PARAMETERS"


@pytest.mark.parametrize("field,value", [("approved", True), ("actor_id", "admin"),
                                           ("trust_level", "internal"), ("confirmed", True)])
def test_client_cannot_supply_authority(inputs, field, value):
    inputs[0][field] = value
    assert evaluate(*inputs, now=101.0).code == "INVALID_COMMAND"


@pytest.mark.parametrize("field,value,code", [
    ("home_id", "other", "HOME_MISMATCH"),
    ("device_id", "other", "UNKNOWN_DEVICE"),
    ("action", "unlock", "UNSUPPORTED_ACTION"),
])
def test_unknown_targets(inputs, field, value, code):
    inputs[0][field] = value
    assert evaluate(*inputs, now=101.0).code == code


@pytest.mark.parametrize("field,value,code", [
    ("roles", ["guest"], "NO_MATCHING_POLICY"),
    ("mode", "restricted", "RESTRICTED_MODE"),
    ("mode", "unknown", "INVALID_CONTEXT"),
    ("observed_at", 0.0, "STALE_CONTEXT"),
    ("observed_at", 102.0, "STALE_CONTEXT"),
    ("recent_counts", {}, "MISSING_RATE_CONTEXT"),
    ("recent_counts", {"light": 3}, "RATE_LIMIT"),
    ("recent_counts", {"light": -1}, "INVALID_CONTEXT"),
    ("recent_counts", {"light": True}, "INVALID_CONTEXT"),
    ("actor_id", "", "INVALID_CONTEXT"),
])
def test_context_checks(inputs, field, value, code):
    inputs[1][field] = value
    assert evaluate(*inputs, now=101.0).code == code


@pytest.mark.parametrize("now", [float("nan"), float("inf"), -1, "101", True, None])
def test_invalid_clock(inputs, now):
    assert evaluate(*inputs, now=now).code == "INVALID_CONTEXT"


@pytest.mark.parametrize("first", [True, False])
def test_explicit_deny_wins_regardless_of_order(inputs, first):
    deny = deepcopy(inputs[2]["rules"][0])
    deny.update(id="deny", effect="deny", parameters={})
    inputs[2]["rules"].insert(0 if first else 1, deny)
    result = evaluate(*inputs, now=101.0)
    assert result.code == "EXPLICIT_DENY"
    assert result.policy_ids == ["deny"]


def test_low_risk_still_requires_permission(inputs):
    inputs[0].update(action="read", params={})
    inputs[1]["devices"]["lamp"]["actions"]["read"] = {}
    inputs[2]["rules"] = []
    assert evaluate(*inputs, now=101.0).code == "NO_MATCHING_POLICY"


@pytest.mark.parametrize("domain,action", [("lock", "unlock"), ("climate", "set_temperature"),
                                          ("machine", "stop_process"), ("alien", "read"),
                                          ("light", "unknown")])
def test_sensitive_commands_blocked_even_with_allow(inputs, domain, action):
    inputs[0].update(action=action, params={})
    inputs[1]["devices"]["lamp"] = dict(domain=domain, actions={action: {}})
    inputs[2]["rules"][0].update(actions=[action], parameters={})
    assert evaluate(*inputs, now=101.0).code == "SENSITIVE_ACTION_BLOCKED"


def test_broad_allow_cannot_bypass_narrow_constraint(inputs):
    narrow = deepcopy(inputs[2]["rules"][0])
    narrow.update(id="narrow", max_per_minute=None)
    narrow["parameters"]["brightness"]["maximum"] = 20
    inputs[2]["rules"].append(narrow)
    assert evaluate(*inputs, now=101.0).code == "POLICY_CONSTRAINT"


@pytest.mark.parametrize("field", ["roles", "devices", "actions"])
def test_no_implicit_wildcards(inputs, field):
    inputs[2]["rules"][0][field] = ["*"]
    assert evaluate(*inputs, now=101.0).code == "NO_MATCHING_POLICY"


def test_models_are_revalidated_after_nested_mutation(inputs):
    command = Command.model_validate(inputs[0])
    context = Context.model_validate(inputs[1])
    policies = PolicySet.model_validate(inputs[2])
    command.params["brightness"] = float("nan")
    assert evaluate(command, context, policies, now=101.0).code == "INVALID_COMMAND"


def test_deterministic_and_no_mutation(inputs):
    original = deepcopy(inputs)
    assert evaluate(*inputs, now=101.0) == evaluate(*inputs, now=101.0)
    assert inputs == original


def test_freshness_boundary(inputs):
    assert evaluate(*inputs, now=130.0).allowed
    assert evaluate(*inputs, now=130.001).code == "STALE_CONTEXT"


def test_duplicate_policy_ids_fail_closed(inputs):
    inputs[2]["rules"].append(deepcopy(inputs[2]["rules"][0]))
    assert evaluate(*inputs, now=101.0).code == "INVALID_CONTEXT"


def test_conditional_deny(inputs):
    deny = deepcopy(inputs[2]["rules"][0])
    deny.update(id="deny-bright", effect="deny")
    deny["parameters"]["brightness"]["minimum"] = 80
    inputs[2]["rules"].append(deny)
    assert evaluate(*inputs, now=101.0).allowed
    inputs[0]["params"]["brightness"] = 90
    assert evaluate(*inputs, now=101.0).code == "EXPLICIT_DENY"
