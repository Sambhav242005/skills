# Task records and honest accounting

This skill does not install a collector, dashboard, custom agent profiles, or background process. Use host-supported delegation and settings controls where available; otherwise record the declared fallback mode. Scripts drafted outside the skill are not part of its installation.

## Record shape

Append JSON objects, one per line, with `schema_version: 1`, a unique `event_id`, UTC `timestamp`, `task_id`, `event_type`, and event-specific fields. Use stable task and assignment identifiers. When workspace writing is unavailable, keep the same facts in a chat ledger and disclose the persistence limitation. Otherwise write records with ordinary file tools; do not create a tracking application unless separately requested.

Relevant event types:

- `task_start`: objective, lead thread ID, requested and observed lead settings.
- `route`: router consultation ID if used, recommended model/effort, reason, selected settings, and override reason if applicable. A deterministic lead decision has no router consultation ID and does not increment router calls.
- `dispatch`: assignment ID, actual returned agent/thread identifiers, role, requested settings, verification status, contract summary, and retry/repair links.
- `consultation`: router/advisor assignment ID, trigger, concise question, outcome. Count each initial prompt and follow-up consultation once, not each internal model request or tool call. A single consultation may have many model requests.
- `verification`: observed settings, source, checks actually executed, outcomes, evidence references, and uncertainty.
- `assignment_end`: accepted, failed, interrupted, or abandoned; whether a later capable-worker assignment repaired it. Record an accepted outcome only after lead verification.
- `usage_snapshot`: source, measured time range, task/assignment attribution, available raw usage counters, and unavailable fields.
- `task_end`: outcome, verification, counts, and remaining limitations. Incomplete objectives stay active or interrupted rather than appearing completed.

Only the lead owns the ledger. Workers return facts to the lead to avoid concurrent writes and inconsistent attribution. Record substantial changes or corrections as new events rather than erasing failures. Keep secrets and raw private transcripts out of the ledger; store concise evidence and local file references.

## Measurement boundaries

Use telemetry exposed by the host or explicitly inspect local session logs for this task and its linked agents. Do not read unrelated conversation content. Resolve logs by thread ID and parent linkage; do not infer identity solely from the newest file or a nickname. If logs are unavailable or their structure is not understood, report unavailable rather than implementing a parser as part of this skill.

Host formats differ: prefer documented host/provider usage fields and do not assume another host uses Codex counters. As an optional Codex-specific example, local JSONL logs may expose `session_meta` identity/parent linkage, `turn_context` model and effort, and `event_msg` / `token_count` usage. These are observed formats, not a stable public interface. Report requested and observed settings separately and identify the source and snapshot time.

For trustworthy manual accounting:

- Read token events within the task/assignment window, preserving attribution by actual thread and model/effort. Separate usage on either side of setting changes.
- Take cumulative counter differences over known boundaries. Do not sum repeated cumulative totals or cumulative totals plus per-request totals.
- Exclude inherited/copied parent events and initial cumulative baselines in child logs. If a boundary is unknown, use identifiable local request usage only and label the result partial. Do not treat all inherited usage as new worker spending.
- Deduplicate repeated usage events. Handle resets as a new counter segment only when local usage can be established. Leave malformed/partial trailing lines and unknown counters uncounted with a warning.
- Missing telemetry is `unavailable`, never zero. Zero is valid only when observed or established from the consultation ledger.
- Cached input is included in input; do not add it to input again. Cache writes are reported separately and their inclusion must follow the source semantics. Reasoning output is ordinarily a subset of output; do not add it again. Prefer reported total tokens rather than deriving totals from ambiguous fields.
- Cache-hit percentage is cached input divided by input for the same measured range. Aggregate using summed token counts, not the average of percentages. With missing inputs or a zero denominator, show unavailable.
- Mark live reports provisional: usage for the current response can arrive after the report is written. A snapshot is not a complete final invoice.
- Keep unattributed usage separate. Attribute repair tokens only to explicitly recorded repair assignments or bounded repair windows; do not label all subsequent lead or capable-worker work as repair.

## Presentation

Use this matrix, adding rows for each observed model/effort combination:

| Role / model / effort | Consultations or assignments | Input | Cached input | Cache hit | Output | Reasoning subset | Total | Settings verified |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |

Include lead, router, advisor, workers, repairs, and unattributed usage as applicable. Avoid double counting repair rows in grand totals if they are also included under workers; label them as subsets.

Across completed tasks report tasks with any advisor consultation divided by all recorded tasks, calls per task including zero, first-pass worker acceptance, retries, escalations, and measured advisor/router token shares. For partial coverage, state the denominator and coverage instead of presenting a complete rate. Treat interrupted tasks separately from completed tasks.

Subscription allowance snapshots, if tools expose them, are account-wide and can include unrelated activity. Keep them separate from task tokens. Do not convert API prices into subscription quota, calculate fabricated per-task quota percentages, or promise cost savings without measured comparisons.
