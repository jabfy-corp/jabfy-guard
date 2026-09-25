from pathlib import Path

import pytest
from pydantic import ValidationError

from jabfy_guard import Parameter, load_policies
from jabfy_guard.validation import matches_parameter, valid_parameters


@pytest.mark.parametrize("data", [
    {"type": "integer", "minimum": 5, "maximum": 2},
    {"type": "string", "minimum": 1},
    {"type": "integer", "choices": [True]},
    {"type": "integer", "choices": []},
    {"type": "integer", "choices": [2], "maximum": 1},
    {"type": "number", "maximum": float("inf")},
    {"type": "object"},
    {"type": "string", "$ref": "https://example.com/schema"},
])
def test_invalid_parameter_definitions(data):
    with pytest.raises(ValidationError):
        Parameter.model_validate(data)


@pytest.mark.parametrize("kind,value,expected", [
    ("boolean", True, True), ("boolean", 1, False),
    ("integer", 1, True), ("integer", 1.0, False),
    ("number", 1, True), ("number", 1.5, True), ("number", True, False),
    ("string", "on", True), ("string", 1, False),
])
def test_exact_types(kind, value, expected):
    assert matches_parameter(value, Parameter(type=kind)) is expected


def test_enum_and_optional_parameter():
    rule = Parameter(type="string", choices=["on", "off"], required=False)
    assert valid_parameters({}, {"state": rule}, exact=True)
    assert matches_parameter("on", rule)
    assert not matches_parameter("unlock", rule)


def test_example_loads():
    policy = load_policies(Path(__file__).parents[1] / "examples" / "policies.json")
    assert policy.version == "home-demo-v1"


@pytest.mark.parametrize("content", ['{', '{"version":"v1","rules":[],"typo":true}',
                                     '{"version":"v1","rules":[],"rules":[]}',
                                     '{"version":"v1","rules":[],"extra":NaN}',
                                     '{"version":"v1","rules":[{}]}'])
def test_bad_policy_file_does_not_fall_back(tmp_path, content):
    path = tmp_path / "bad.json"
    path.write_text(content)
    with pytest.raises(ValueError):
        load_policies(path)


def test_missing_policy_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_policies(tmp_path / "missing.json")
