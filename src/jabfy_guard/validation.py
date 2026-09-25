"""Bounded scalar parameter validation: no coercion, remote schemas or scripts."""

from .models import Parameter, Scalar


def matches_parameter(value: Scalar, rule: Parameter) -> bool:
    types = {"boolean": (bool,), "integer": (int,), "number": (int, float,), "string": (str,)}
    if type(value) not in types[rule.type]:
        return False
    if rule.choices is not None and not any(
        type(value) is type(choice) and value == choice for choice in rule.choices
    ):
        return False
    if rule.minimum is not None and value < rule.minimum:
        return False
    if rule.maximum is not None and value > rule.maximum:
        return False
    return True


def valid_parameters(params: dict[str, Scalar], rules: dict[str, Parameter], *, exact: bool) -> bool:
    if exact and params.keys() - rules.keys():
        return False
    return all(
        (not rule.required if name not in params else matches_parameter(params[name], rule))
        for name, rule in rules.items()
    )
