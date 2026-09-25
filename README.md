# jabfy-guard

Small, deterministic Python library for authorizing home commands. The AI proposes;
Guard evaluates; the Bus executes. **This repository does not yet change the Core,
Bus or simulator.** An `allow` decision is data, not an execution token.

## Install and test

Python 3.11+:

```sh
python -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m pytest -q
```

Pydantic is the only runtime dependency. No model server, network, Docker or device
is needed. Run this example from the repository root:

```python
from jabfy_guard import evaluate, load_policies

policies = load_policies("examples/policies.json")
command = {
    "correlation_id": "request-1",
    "home_id": "home-demo",
    "device_id": "living-room-light",
    "action": "set_brightness",
    "params": {"brightness": 50},
}
# Construct this on the server, NEVER from an LLM or browser-supplied identity.
context = {
    "home_id": "home-demo",
    "actor_id": "alice",
    "roles": ["resident"],
    "mode": "normal",
    "observed_at": 100.0,
    "devices": {
        "living-room-light": {
            "domain": "light",
            "actions": {
                "set_brightness": {
                    "parameters": {
                        "brightness": {"type": "integer", "minimum": 0, "maximum": 100}
                    }
                }
            },
        }
    },
    "recent_counts": {"resident-living-room-light": 0},
}
decision = evaluate(command, context, policies, now=101.0)
assert decision.allowed
print(decision.model_dump())
```

`now` and `observed_at` are server-supplied Unix seconds. Context older than
`max_age_seconds` (default 30), or dated in the future, is rejected.

## Rules

- No matching allow policy means deny, including low-risk commands.
- An explicit matching deny wins regardless of rule order.
- Home, role, device and action must match exact values; `*` is not a wildcard.
- All scoped allow rules impose their constraints together. A broad rule cannot
  bypass a narrower bound or rate limit. Rule order is not meaningful.
- Device parameters are an exact allowlist. Unknown/missing parameters are rejected.
- Policy parameters add bounds/choices to device constraints. An optional absent
  parameter satisfies its constraint; a required absent parameter does not.
- Types are strict: `true`, `1`, `1.0` and `"1"` are not interchangeable integers.
  Only finite scalar values are supported, not nested parameter objects or scripts.
- Invalid configuration raises on loading: stop startup, do not substitute permissive
  defaults. Invalid evaluation inputs return a denial.
- Unknown domain/action is critical risk. High/critical actions are blocked in V1,
  even with an allow rule. This includes thermostat changes and locks. There is no
  human-confirmation bypass yet.
- Restricted mode blocks all commands, including reads. Administrative recovery
  must use a separate, authenticated control path, not a device command.

Rate counters are counts over the preceding 60 seconds, per actor/home/policy ID.
Missing required counters cause a denial. Guard checks but does not maintain them.
The caller must serialize checking and reservation across concurrent commands;
otherwise concurrent evaluations can exceed the limit. Count every admitted command
against every applicable allow rule, not just the first one.

The API accepts validated models or dictionaries. Results include a stable reason
code, correlation ID, policy version, applicable policy IDs and risk where known.
An early rejection may precede risk classification. See [architecture](docs/architecture.md)
for integration obligations and limitations.
