---
name: routing-harness
description: Coordinate an explicitly requested AI-agent workflow with adaptive worker models and reasoning, conditional advisor review, evidence-based acceptance, and transparent usage reporting across compatible SKILL.md hosts. Use only when invoked or explicitly requested; ordinary coding chats do not activate this workflow.
---

# Routing harness

This is an opt-in orchestration skill, not an execution engine. Use the host's supported tools and adapt to its exposed capabilities. Do not build a harness application, install a service, or change global model settings as part of using this skill.

## Activate and establish the task

- Activate for the current user objective when explicitly requested by name or through the host's skill invocation syntax (for example, `$routing-harness` where supported). Do not carry activation into unrelated objectives without a user instruction.
- Use one task ID per activated objective and separate assignment IDs for workers, router consultations, and advisor consultations. Explicitly count tasks that use no advisor.
- Keep the current user-selected lead. State its actual settings if exposed; otherwise label them unverified. A skill cannot change the main chat's model or reasoning. Preserve any user-specified model preferences; otherwise map roles to the models actually available in the host.
- Before delegating, identify whether the host supports subagents, per-agent models, reasoning controls, independent review, workspace writes, and usage telemetry. Read [references/host-adaptation.md](references/host-adaptation.md) when a capability is absent or the host is unfamiliar. Use supported mechanisms only; do not invent tools, config keys, or model IDs.
- Honor the host's concurrency limit. Reserve capacity by running router and advisor consultations sequentially with worker waves when necessary.

## Route work

Use a fast available model at a supported low reasoning setting as the router for a nontrivial task's intake, when a separate router is supported. Consult it again only after material scope changes or a failure that needs a new allocation. Handle trivial work directly without spawning a router or worker. Do not consult the router on every tool action.

Give the router a concise objective, relevant evidence, known uncertainty, failure history, and the following table. Ask for worker model, effort, boundaries, acceptance checks, advisor need, and a short justification. Its decision is a recommendation; the lead applies the quality floors below and records overrides.

| Work | Initial worker choice |
| --- | --- |
| Exact file, symbol, or call-site search | Fast worker, low reasoning |
| Bounded tracing across known files | Fast worker, medium reasoning |
| Small, specified edit with reliable acceptance checks | Fast worker, high reasoning |
| Ambiguous requirements, interacting changes, complex implementation | Capable worker, medium reasoning |
| Difficult diagnosis or substantial uncertainty | Capable worker, high reasoning |

Workers may use any appropriate available model and a supported reasoning setting. Low, medium, and high are policy labels: map them to host-supported values, recording the mapping. If effort is fixed or not exposed, record that instead of claiming to change it. The table is an initial policy to evaluate, not a measured guarantee. The router may increase reasoning or choose a more capable model when the evidence warrants it. Higher effort alone does not resolve missing requirements or context.

- Do not assign ambiguous implementation to the fast worker merely to save tokens. Have it gather evidence first, or use a more capable worker.
- Where supported, use the requested model and effort explicitly; otherwise disclose the fixed/inherited or sequential fallback. Where the host requires a fresh-context spawn for overrides, use that mechanism and supply the contract; do not claim an inherited-context spawn has different settings unless the host supports it.
- Start another agent when its model or effort must change; do not assume a follow-up changes existing settings.
- Native tool acknowledgements confirm a requested dispatch, not observed execution. Verify observed model and effort from telemetry when available. If observed settings conflict, stop further work on that assignment, record it, and reroute. If telemetry is unavailable, label verification unavailable.

## Worker contracts and acceptance

For every assignment provide:

1. Objective and expected observable behavior.
2. Relevant files, source evidence, constraints, and known uncertainty.
3. Permitted files or a clear read-only boundary.
4. Acceptance checks appropriate to the work.
5. Stop conditions: missing context, conflicting requirements, failed checks, or work outside the boundary.

Require a concise return containing evidence with file references, changed files, actual checks and outcomes, remaining uncertainty, and blockers. Workers must distinguish checks run from checks suggested.

- Prefer parallel independent exploration. Do not give workers overlapping write ownership. Keep final integration with the lead.
- The lead inspects evidence and changes and runs or independently verifies meaningful acceptance checks. Do not add tests that merely mirror implementation or test trivial reversible edits unnecessarily.
- For searches, verify definitions/call sites in source. For behavior tracing, verify the execution path. For edits, use relevant behavioral tests, type checks, builds, or direct observations.
- Failed checks block acceptance. A router recommendation or worker's success statement cannot override a failed check. Diagnose flaky or invalid checks explicitly rather than hiding failures.
- After a fast-worker failure, classify the cause with evidence. Allow one corrected attempt with that worker only when missing context caused the failure. Implementation errors or excessive complexity escalate to a more capable worker. Repeating the same failure twice requires advisor review; if independent advice is unavailable, record that limitation and perform an explicit lead reassessment without counting a separate advisor call.
- A worker failure is not automatically an advisor call: a clear, isolated error can go directly to a more capable worker. Record retry and repair links so their usage can be evaluated together.

## Advisor

Use a capable available model with a supported high reasoning setting as the advisor. It may be the same model as the lead with different supported settings. It provides advice and findings; the lead owns implementation and verification. A lead self-review is not an independent advisor consultation.

Consult for an unresolved complex plan, the same failure twice, or final review of substantial changes. Skip routine and trivial changes. There is no call cap. Every consultation, including follow-ups to the same agent, needs a trigger and outcome in the record.

Send the objective, relevant decision or diff, evidence, checks, failed attempts, and the exact question. Do not routinely send the entire conversation. Reuse the advisor for related consultations with unchanged settings when its context remains appropriate. Record whether advice changed the plan/code, found a concrete issue, or produced no actionable advice.

## Context and cache

Keep common instructions stable and handoffs concise. Reuse a suitable existing agent for related follow-ups with unchanged settings. Use full-history forks when the assignment needs that history, not solely to pursue cache hits.

Caching is managed by the host and model provider. Do not claim that copying context transfers a cache, that a fork guarantees a hit, or that different models/providers share caches. Different reasoning settings may also affect cache eligibility. Verify reuse through reported cached input tokens. Do not add speculative cache configuration or inflate prompts to seek hits.

## Records and reporting

Read [references/accounting.md](references/accounting.md) when recording or reporting usage. Maintain a compact append-only task ledger in the user's workspace, normally `work/routing-harness/events.jsonl` when workspace writes are available and authorized by the task. Otherwise keep the ledger in chat and disclose that it is not durable. This is data created during the task, not a background collector. Never overwrite prior task history.

Record task start/end, routing decisions, each consultation/assignment, overrides, verification, retries, repairs, acceptance, and failures. Use native returned thread IDs when available; keep agent paths and thread IDs distinct. Preserve records across compaction and resume from them.

At checkpoints and completion show a compact matrix with model/effort, consultations or assignments, measured tokens, cache-hit percentage, advisor triggers/outcomes, verification status, and repair attribution. Include zero-call rows. Mark unavailable metrics explicitly; do not invent a token dashboard or claim a collector is installed.

Finish with the outcome, verification evidence, outstanding limitations, advisor and router counts, and the usage matrix. Evaluate routing based on total usage including repairs and first-pass acceptance, not the worker's initial token count alone. Do not silently rewrite this policy from a small sample; propose evidence-backed adjustments.
