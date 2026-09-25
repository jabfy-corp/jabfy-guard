"""Pure authorization function; neither network access nor execution side effects."""

import math

from pydantic import ValidationError

from .models import Command, Context, Decision, PolicySet
from .policies import matches_scope
from .risk import classify_risk
from .validation import valid_parameters


def evaluate(command: Command | dict, context: Context | dict, policies: PolicySet | dict,
             *, now: float) -> Decision:
    """Evaluate trusted snapshots at a server-supplied Unix time.

    Revalidate model instances too: frozen models can still contain mutable dicts/lists.
    Invalid input becomes a denial; policy file loading errors should stop startup.
    """
    def validated(model, value):
        return model.model_validate(value.model_dump() if isinstance(value, model) else value)

    try:
        command = validated(Command, command)
    except (ValidationError, ValueError, TypeError):
        return Decision(status="deny", code="INVALID_COMMAND", reason="Invalid command.")

    def deny(code, reason, **details):
        return Decision(status="deny", code=code, reason=reason,
                        correlation_id=command.correlation_id, **details)

    try:
        context = validated(Context, context)
        policies = validated(PolicySet, policies)
        if type(now) not in (int, float) or not math.isfinite(now) or now < 0:
            raise ValueError("Invalid clock")
    except (ValidationError, ValueError, TypeError, OverflowError):
        return deny("INVALID_CONTEXT", "Invalid security context, clock or policies.")

    details = {"policy_version": policies.version}
    if command.home_id != context.home_id:
        return deny("HOME_MISMATCH", "The command does not belong to this home.", **details)
    if not 0 <= now - context.observed_at <= context.max_age_seconds:
        return deny("STALE_CONTEXT", "The home context is stale or dated in the future.", **details)
    if context.mode != "normal":
        return deny("RESTRICTED_MODE", "Commands are blocked in restricted mode.", **details)
    device = context.devices.get(command.device_id)
    if device is None:
        return deny("UNKNOWN_DEVICE", "The device is not registered.", **details)
    capability = device.actions.get(command.action)
    if capability is None:
        return deny("UNSUPPORTED_ACTION", "The device does not advertise this action.", **details)
    if not valid_parameters(command.params, capability.parameters, exact=True):
        return deny("INVALID_PARAMETERS", "Parameters do not match device capabilities.", **details)
    risk = classify_risk(command.action, device.domain)
    details["risk"] = risk
    scoped = [rule for rule in policies.rules if matches_scope(rule, command, context)]
    denied = [rule.id for rule in scoped if rule.effect == "deny" and
              valid_parameters(command.params, rule.parameters, exact=False)]
    if denied:
        return deny("EXPLICIT_DENY", "An explicit deny rule applies.", policy_ids=denied, **details)
    if risk in {"high", "critical"}:
        return deny("SENSITIVE_ACTION_BLOCKED", "V1 does not authorize sensitive actions.", **details)
    allowed = [rule for rule in scoped if rule.effect == "allow"]
    if not allowed:
        return deny("NO_MATCHING_POLICY", "No explicit permission for this actor and command.", **details)
    details["policy_ids"] = [rule.id for rule in allowed]
    # All scoped allow constraints apply, so a broad rule cannot bypass a tighter one.
    for rule in allowed:
        if not valid_parameters(command.params, rule.parameters, exact=False):
            return deny("POLICY_CONSTRAINT", "Parameters violate a policy constraint.", **details)
        if rule.max_per_minute is not None:
            count = context.recent_counts.get(rule.id)
            if count is None:
                return deny("MISSING_RATE_CONTEXT", "Required rate counter is unavailable.", **details)
            if count >= rule.max_per_minute:
                return deny("RATE_LIMIT", "Command frequency limit reached.", **details)
    return Decision(status="allow", code="ALLOWED", reason="All authorization checks passed.",
                    correlation_id=command.correlation_id, **details)
