# Architecture and trust boundary

## Responsibilities

- `models.py`: strict input/output contracts, no unknown fields or numeric coercion.
- `engine.py`: deterministic evaluation, no execution or storage.
- `validation.py`: small scalar capability/constraint language, not arbitrary JSON Schema.
- `policies.py`: trusted local JSON configuration and exact scope matching.
- `risk.py`: conservative action/domain risk catalog.

There are no plugins, HTTP server, LLM calls, transport addresses or device secrets.
Policy IDs are unique within a versioned set. Updating a configuration should assign
a new version; the operator owns version management. Versions are not signatures.

## Trusted inputs

Only the command is untrusted user/LLM input. The host must authenticate the actor,
resolve home-scoped roles and build context from a registered capability catalog.
Do not promote arbitrary IoT advertisements to authorized capabilities. Device
labels and prompts are not executable policies. Context and policies must not come
from the request body. A fabricated context can fool the library: it is not an
authentication system or a sandbox for compromised host code.

The engine revalidates models, including nested mutable data, and reads snapshots.
The caller must avoid concurrent mutation while taking those snapshots. No models
are retained or modified by the engine. Requests and catalogs need size limits at
the API boundary; this in-process library is not an untrusted JSON transport parser.

## Evaluation

Validate inputs; check home, freshness and security mode; resolve device/action;
validate exact capability parameters; classify risk; apply explicit denies; block
sensitive actions; require allow policies; enforce all their constraints and rates.
No policy can override a capability violation, restricted mode or sensitive-action block.

Deny rules can be conditional on parameters. Their scope must match before their
parameter conditions are considered. Allow constraints are cumulative across scoped
rules: this intentionally favors refusal over alternative permissive grants.

## Future Bus integration (not implemented here)

1. Keep the existing BusMessage wire contract. A Bus-owned adapter maps logical
   home/device/action/parameters into Guard contracts, with explicit tested ID mappings.
   Guard does not import the Bus; only the Bus depends on Guard.
2. Build authenticated context from the registry, not message trust labels. Keep
   simulation and physical-device policy sets isolated.
3. Replace the Bus's duplicated policy/risk decision with this evaluator. Preserve
   Core's early shape validation; it is not final authorization. Existing implicit
   low-risk permissions must become explicit rules or be denied.
4. Serialize evaluation, rate reservation and execution admission. On stale device
   state/configuration, re-evaluate. Freshness bounds alone do not solve races.
5. Persist a redacted decision record before dispatch. Audit failure, Guard exception
   or any non-allow result blocks dispatch. Record execution outcome separately using
   the correlation ID. Do not log secrets or entire model prompts.
6. Only the trusted execution coordinator can admit an approved command. Never accept
   a client-supplied `allow` result or rely on a forgeable `command.approved` label.
   Authenticate boundaries and bind admission to the exact command, with expiry and
   replay prevention when authorization crosses processes.

Keep existing Bus bypass defenses until stronger admission checks have tests. Migration
must be a separate change, with regression tests for manual controls and AI proposals.

## V1 limits

No confirmation workflow, persistent counters, automatic Fortress transitions,
schedule rules, multi-command atomicity, text moderation, replay store or authentication.
Restricted mode is an explicit caller-owned switch; it is not full Fortress Mode.
Single-command decisions do not guarantee a batch executes atomically. Hardware may fail
after approval; physical effects cannot generally be rolled back.

There is no persistent audit in this package: reuse the Bus audit instead of creating
a competing journal. Until that integration exists, this package alone does not protect
the currently running simulator or real hardware. Automated tests are not a production
security certification. A compromised host process can bypass a Python library.
