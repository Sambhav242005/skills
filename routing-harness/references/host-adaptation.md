# Adapt to the host

The SKILL.md workflow is portable; execution capabilities are not universal. Identify available capabilities from the current tool definitions, visible configuration, or official host documentation. Never infer support merely from the host accepting SKILL.md. Use configured provider/model identifiers, not guessed aliases.

## Operating modes

| Available capabilities | Operation |
| --- | --- |
| Subagents with per-agent model and reasoning controls | Dispatch role-specific models and effort explicitly. |
| Named agent profiles with fixed settings | Choose an existing profile matching the desired role/settings; record its name and observed configuration. Do not silently edit profiles. |
| Subagents that inherit a fixed model or effort | Delegate bounded work with the inherited settings and label the fixed/inherited fields. Do not promise model switching or effort changes. |
| No subagents | Run sequentially with the lead. Keep the routing plan, contracts, checks, and escalation reassessment. Separate-agent router/advisor calls remain zero. |
| No workspace access | Keep a chat ledger and report durability limits. Request only the source material needed for the actual task. |
| No token or cache telemetry | Report consultation counts and outcomes from the ledger; token/cache fields are unavailable. |

Describe the selected mode once at activation and when capabilities materially change. The lead remains responsible for acceptance in every mode. If the task requires unavailable independent review or execution, report the specific unmet requirement instead of pretending a sequential simulation satisfies it.

## Model and reasoning choices

Preserve the user's model preferences. Otherwise choose a fast model for routing and bounded work, a capable model for complex implementation, and a capable high-effort model for advice. Use the host's exposed catalog and availability; relative capability should be a working hypothesis evaluated through first-pass acceptance and repair usage.

The creator's optional Codex profile is Sol Low as lead, Luna Low as router, Luna or Sol workers at Low/Medium/High, and Sol High as advisor. These are preferences, not requirements for the universal skill. They apply only when the host exposes the actual configured models and settings. In Codex the known IDs are `gpt-6.1-sol` and `gpt-6-luna`; do not copy those identifiers into another provider without checking its catalog.

Reasoning settings are model/provider-specific. Where supported, map policy labels to the host's low, medium, and high equivalents. For a model with no effort controls, keep the fixed setting visible. More verbose prompting does not establish a different reasoning setting.

## Host invocation

Use the host's actual skill and delegation mechanism. `$routing-harness` is an invocation example for hosts that support that syntax; otherwise explicitly request the skill by name using the host's supported mechanism. Skills cannot create model access, additional concurrency slots, or new tools.

Subagents inherit the host's permissions and user authorization. Keep the task's existing scope and confirmation requirements. Do not install dependencies, change account settings, or acquire new provider access merely to make the preferred routing profile work.
