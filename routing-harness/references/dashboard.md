# Local dashboard

The optional dashboard requires Python 3.10 or newer, with no third-party packages. Run it locally from a terminal or the agent's execution tool. Core skill routing still works without Python, terminal access, or files. No telemetry is uploaded and no server or service is installed.

## Generate a report

Locate the installed skill's `scripts/dashboard.py`. Use its absolute path when running from another directory. The following commands assume the current directory is the skill folder; replace the input paths with actual selected files.

```sh
python scripts/dashboard.py report --codex /path/to/selected-session.jsonl --ledger /path/to/work/routing-harness/events.jsonl --output /path/to/work/routing-report
python scripts/dashboard.py report --claude /path/to/selected-transcript.jsonl --output /path/to/work/routing-report
python scripts/dashboard.py report --opencode /path/to/session-export.json --output /path/to/work/routing-report
```

On Windows quote paths containing spaces. If the command is `python3` on your machine, use that instead. The program does not install Python automatically.

Open the resulting `index.html` in your browser. It is self-contained and works offline; use the filter box and clickable column headings. Alongside it are `tasks.csv`, `agents.csv`, `requests.csv`, and `report.json`. A manually started `--watch 10` regenerates the files every ten seconds until Ctrl+C; reload the browser file to view the latest snapshot. No daemon is left running.

Use repeated `--codex`, `--claude`, or `--opencode` arguments to include explicit child transcripts or multiple hosts. No directory scan or automatic discovery occurs. Parsing reads input records but the generated report contains usage metadata, not prompts, answers, or tool output. Ledger summaries and task names can still be private: review exports before sharing.

Use `--since 2026-10-20T10:00:00Z --until 2026-10-20T11:00:00Z` for a task-specific time window. Missing timestamps are excluded with a warning under a time filter. Without time filters an explicitly selected transcript reports all of its observed requests, with out-of-task usage left unattributed.

## Supported sources

- **Codex:** native rollout JSONL containing session metadata, turn context, and token_count events. Cached input is a subset of input; reasoning is a subset of output. Initial inherited baselines are excluded and unknown boundaries are warned about. Model and effort come from observed turn context when available.
- **Claude Code:** assistant JSONL transcript usage records with message identity. Repeated/streamed observations of a message are deduplicated rather than summed. Cache reads and cache creation are separate from native uncached input, so the adapter normalizes inclusive input. Child transcripts may need explicit agent IDs to distinguish them from the parent.
- **OpenCode:** explicit session exports in supported message formats, or a read-only SQLite database in supported schemas. Use your installed CLI's export command as documented by `opencode --help`; command names differ between releases. SQLite is opened read-only. No database migration or query that changes data is executed. Legacy and v2 token semantics differ; unknown fields remain unavailable.

For a database or multi-session export, restrict scope with `--session opencode:ACTUAL_SESSION_ID`; repeat for each desired child. Without this flag an explicitly supplied database reports metadata for all sessions in that database. Never silently select a user's entire database for a task-specific report. Session filters select exact IDs; they do not automatically discover children.

Host formats can change. Supported-format fixtures are tested, and local host samples are used where available; this is not a promise of every release/provider combination. Review the report's warning section and coverage. Unexpected shapes must not be treated as zero usage.

## Attribute tasks, roles, and settings

Without a ledger or binding the usage is **unattributed**; a model name alone does not identify a router, worker, or advisor. Consultation counts come from the task ledger, not an estimate based on token requests. A consultation may contain many requests.

Create a JSON manifest to combine sources and bind explicit sessions. Paths inside it are relative to the manifest. Times are timezone-aware and windows are start-inclusive/end-exclusive. If multiple bindings match, the usage stays unattributed with a warning.

```json
{
  "sources": [{"host": "codex", "paths": ["selected-session.jsonl"]}],
  "bindings": [{
    "host": "codex",
    "session_id": "ACTUAL_THREAD_ID",
    "task_id": "feature-01",
    "role": "lead",
    "requested_model": "ACTUAL_MODEL_ID",
    "requested_effort": "low",
    "start": "2026-10-20T10:00:00Z",
    "end": "2026-10-20T11:00:00Z"
  }]
}
```

```sh
python scripts/dashboard.py report --manifest /path/to/manifest.json --ledger /path/to/events.jsonl --output /path/to/work/routing-report
```

For worker bindings also include `assignment_id`; for explicitly attributed repairs include `repair_of`. Set `agent_id` when the transcript uses one. A parent-only binding must not claim a child's usage. Identical model/effort across a reused agent is permitted, but separate assignment windows must not overlap. Incomplete timestamps and ambiguous boundaries remain unattributed.

## Record workflow events

Use ordinary file tools to append the event records described in [accounting.md](accounting.md), or use the helper with a JSON event file:

```sh
python scripts/dashboard.py record --ledger /path/to/events.jsonl --event /path/to/event.json
```

The helper supplies an event ID and UTC timestamp when omitted and refuses duplicate IDs. Only the lead should write the ledger. A worker assignment may be accepted only after a passing lead verification has been recorded. This is an audit gate, not an independent test runner; the lead must actually perform the recorded check.

Minimum task event: `{"event_type":"task_start","task_id":"feature-01","objective":"Fix the selected behavior","host":"codex","session_id":"ACTUAL_THREAD_ID"}`. Consultation event: `{"event_type":"consultation","task_id":"feature-01","assignment_id":"advisor-01","role":"advisor","trigger":"same failure twice","outcome":"identified a missing condition"}`. Finish with a task_end event and completed, interrupted, or failed status.

The dashboard includes tasks with zero recorded advisor calls. A zero means no call recorded in this ledger, not proof that no unlogged consultation occurred. First-pass acceptance and repair rates are ledger-derived. Requested and observed model/effort are separate. Missing evidence produces warnings instead of a verified badge.

## Interpreting totals

Metrics with missing records show unavailable plus a known subtotal and coverage. Do not treat a partial subtotal as a complete bill. Cache-hit percentage is weighted by input tokens. Cache writes and reasoning are displayed separately and not added twice. OpenCode's source-reported dollar cost, where available, is metadata rather than a subscription invoice. Account allowance snapshots remain separate from task tokens. No dollar, credit, quota, or savings estimates are invented.

The report generated during an active response may not yet include that response's final usage. Regenerate after completion for a later snapshot. Keep raw logs and generated reports outside the skill package. Do not publish personal telemetry as marketplace demo material.

## Format references

- [Claude SDK cost tracking](https://code.claude.com/docs/en/agent-sdk/cost-tracking): repeated assistant message identities and separate cache fields.
- [OpenCode token-usage schema](https://github.com/anomalyco/opencode/blob/dev/packages/schema/src/token-usage.ts): v2 component and total semantics.
- [OpenCode legacy session implementation](https://github.com/anomalyco/opencode/blob/v1.2.27/packages/opencode/src/session/index.ts): legacy usage normalization.
- Codex rollout fields are an observed local format, not a guaranteed public contract; fixture tests and real forked-session checks cover the supported shape.
