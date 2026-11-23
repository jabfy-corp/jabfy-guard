"""Strict data contracts. Context and policies are supplied by trusted server code."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, model_validator

Scalar = str | bool | int | FiniteFloat
ParameterValue = Scalar | dict[str, Scalar]
Risk = Literal["low", "medium", "high", "critical"]


class Model(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)


class Parameter(Model):
    type: Literal["boolean", "integer", "number", "string", "object"]
    properties: dict[str, "Parameter"] = Field(default_factory=dict)
    required: bool = True
    minimum: FiniteFloat | None = None
    maximum: FiniteFloat | None = None
    choices: list[Scalar] | None = None

    @model_validator(mode="after")
    def valid_constraints(self):
        if self.type != "object" and self.properties:
            raise ValueError("Properties require an object parameter")
        if self.type == "object" and (self.choices is not None or any(
            child.type == "object" for child in self.properties.values()
        )):
            raise ValueError("Objects support scalar properties only, without choices")
        if self.type not in {"integer", "number"} and (
            self.minimum is not None or self.maximum is not None
        ):
            raise ValueError("Bounds require a numeric parameter")
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("Minimum exceeds maximum")
        if self.choices is not None:
            if not self.choices:
                raise ValueError("Choices must not be empty")
            from .validation import matches_parameter

            unconstrained = self.model_copy(update={"choices": None})
            if any(not matches_parameter(value, unconstrained) for value in self.choices):
                raise ValueError("Choices must satisfy the parameter type and bounds")
        return self


class Capability(Model):
    parameters: dict[str, Parameter] = Field(default_factory=dict)


class Device(Model):
    domain: str = Field(min_length=1)
    actions: dict[str, Capability]


class Command(Model):
    correlation_id: str = Field(min_length=1, max_length=200)
    home_id: str = Field(min_length=1)
    device_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    params: dict[str, ParameterValue] = Field(default_factory=dict)


class Context(Model):
    # Server-owned context only; never accept this flag from a command/request.
    simulation: bool = False
    home_id: str = Field(min_length=1)
    actor_id: str = Field(min_length=1)
    roles: list[str] = Field(min_length=1)
    mode: Literal["normal", "restricted"]
    observed_at: FiniteFloat = Field(ge=0)
    max_age_seconds: FiniteFloat = Field(default=30.0, gt=0)
    devices: dict[str, Device]
    # Trusted counts in the preceding 60 seconds, keyed by policy ID, for this actor/home.
    recent_counts: dict[str, int] = Field(default_factory=dict)

    @model_validator(mode="after")
    def valid_counts(self):
        if any(value < 0 for value in self.recent_counts.values()):
            raise ValueError("Counts cannot be negative")
        return self


class Policy(Model):
    allow_sensitive_simulation: bool = False
    id: str = Field(min_length=1)
    effect: Literal["allow", "deny"]
    home_id: str = Field(min_length=1)
    roles: list[str] = Field(min_length=1)
    devices: list[str] = Field(min_length=1)
    actions: list[str] = Field(min_length=1)
    # Additional safety constraints; device constraints are always checked separately.
    parameters: dict[str, Parameter] = Field(default_factory=dict)
    max_per_minute: int | None = Field(default=None, gt=0)


class PolicySet(Model):
    version: str = Field(min_length=1)
    rules: list[Policy]

    @model_validator(mode="after")
    def unique_ids(self):
        if len({rule.id for rule in self.rules}) != len(self.rules):
            raise ValueError("Policy IDs must be unique")
        return self


class Decision(Model):
    status: Literal["allow", "deny"]
    code: str
    reason: str
    correlation_id: str | None = None
    risk: Risk | None = None
    policy_version: str | None = None
    policy_ids: list[str] = Field(default_factory=list)

    @property
    def allowed(self) -> bool:
        return self.status == "allow"
