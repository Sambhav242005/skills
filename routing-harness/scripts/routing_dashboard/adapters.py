"""Read-only usage adapters. No transcript text is retained in returned records.

Formats are observed storage/export formats, not stable cross-host APIs. Unknown
fields stay None. Source changes must produce warnings rather than guessed totals.
"""
from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

TOKEN_KEYS = (
    "input_tokens", "cached_input_tokens", "cache_write_input_tokens",
    "output_tokens", "reasoning_tokens", "total_tokens",
)


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value if math.isfinite(value) and value >= 0 else None


def sum_known(*values):
    return sum(values) if all(v is not None for v in values) else None


def timestamp(value):
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value / 1000, timezone.utc).isoformat().replace("+00:00", "Z")
        if isinstance(value, str):
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                return None
            return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    except (ValueError, OverflowError, OSError):
        pass
    return None


def before(left, right):
    if not left or not right:
        return False
    return datetime.fromisoformat(left.replace("Z", "+00:00")) < datetime.fromisoformat(right.replace("Z", "+00:00"))


def row(host, source, **values):
    result = dict.fromkeys((
        "host", "session_id", "parent_session_id", "agent_id", "request_id",
        "timestamp", "model", "effort", *TOKEN_KEYS, "cost_usd", "source", "measurement",
    ))
    result.update(host=host, source=str(source), warnings=[])
    result.update(values)
    return result


def load_json(path, warnings):
    """Accept a JSON document or JSONL, including a partially written final line."""
    try:
        raw = Path(path).read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as error:
        warnings.append(f"Cannot read {path}: {type(error).__name__}")
        return []
    if not raw.strip():
        return []
    try:
        document = json.loads(raw)
        return document if isinstance(document, list) else [document]
    except json.JSONDecodeError:
        events = []
        for index, line in enumerate(raw.splitlines(), 1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
                if isinstance(item, dict):
                    events.append(item)
            except json.JSONDecodeError:
                warnings.append(f"{path}: invalid/incomplete JSON at line {index}; line skipped.")
        return events


def _codex(paths, warnings):
    logs = []
    turns = {}
    fields = dict(zip(TOKEN_KEYS, (
        "input_tokens", "cached_input_tokens", "cache_write_input_tokens",
        "output_tokens", "reasoning_output_tokens", "total_tokens",
    )))
    for path in paths:
        events = load_json(path, warnings)
        metas = [e for e in events if isinstance(e, dict) and e.get("type") == "session_meta"]
        if not metas:
            if events:
                warnings.append(f"{path}: no Codex session_meta; usage skipped.")
            continue
        # A fork begins with its own metadata and then can replay the parent's
        # metadata/history. The final metadata block is not the file owner.
        meta = metas[0].get("payload", {})
        if not isinstance(meta, dict):
            warnings.append(f"{path}: malformed Codex session metadata; skipped.")
            continue
        session = meta.get("id")
        if not isinstance(session, str) or not session:
            warnings.append(f"{path}: missing Codex session ID; usage skipped.")
            continue
        source = meta.get("source", {})
        subagent = source.get("subagent") if isinstance(source, dict) else None
        spawn = subagent.get("thread_spawn") if isinstance(subagent, dict) else None
        if not isinstance(spawn, dict):
            spawn = {}
        start = timestamp(meta.get("timestamp") or metas[0].get("timestamp"))
        parent = spawn.get("parent_thread_id") or meta.get("forked_from_id")
        logs.append((path, events, session, start, parent, spawn.get("agent_path")))
        owned_turns = turns.setdefault(session, set())
        scope_is_local = True
        for event in events:
            if not isinstance(event, dict) or not isinstance(event.get("payload"), dict):
                continue
            payload = event["payload"]
            if event.get("type") == "session_meta":
                scope_is_local = payload.get("id") == session
            elif event.get("type") == "event_msg" and payload.get("type") == "thread_settings_applied":
                if payload.get("thread_id") == session:
                    scope_is_local = True
            elif event.get("type") == "turn_context" and scope_is_local:
                turn = payload.get("turn_id")
                if isinstance(turn, str) and not before(timestamp(event.get("timestamp")), start):
                    owned_turns.add(turn)
    records, seen = [], set()
    for path, events, session, start, parent, agent in logs:
        previous = None
        context = {}
        context_time = None
        scope_is_local = True
        context_is_local = True
        uncertain_warned = False
        for event in events:
            if not isinstance(event, dict):
                continue
            payload = event.get("payload", {})
            if not isinstance(payload, dict):
                continue
            if event.get("type") == "session_meta":
                scope_is_local = payload.get("id") == session
                context, context_time = {}, None
                context_is_local = scope_is_local
                if scope_is_local:
                    previous = None
                continue
            if event.get("type") == "event_msg" and payload.get("type") == "thread_settings_applied":
                if payload.get("thread_id") == session:
                    if not scope_is_local:
                        previous = None
                        context, context_time = {}, None
                    scope_is_local = True
                    context_is_local = True
                continue
            if event.get("type") == "turn_context":
                context, context_time = payload, timestamp(event.get("timestamp"))
                context_is_local = scope_is_local
                continue
            if event.get("type") != "event_msg" or payload.get("type") != "token_count":
                continue
            info = payload.get("info")
            if not isinstance(info, dict):
                continue
            total, last = info.get("total_token_usage"), info.get("last_token_usage")
            if not isinstance(total, dict): total = None
            if not isinstance(last, dict): last = None
            if total is None and last is None:
                continue
            at = timestamp(event.get("timestamp"))
            turn = context.get("turn_id")
            fingerprint = json.dumps([session, at, turn, total, last], sort_keys=True)
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            inherited = not scope_is_local or not context_is_local or before(at, start) or before(context_time, start) or (
                parent and turn and turn in turns.get(parent, set())
            )
            if inherited:
                # Replayed parent counters are not a reliable child baseline.
                # Wait for a local marker and use its first last_usage instead.
                if not scope_is_local and not uncertain_warned:
                    warnings.append(f"{path}: copied/foreign metadata scope excluded; local ownership requires a session or thread-settings marker.")
                    uncertain_warned = True
                continue
            notes = []
            comparable = [(number(previous.get(f)), number(total.get(f))) for f in fields.values()] if previous is not None and total is not None else []
            comparable = [(a, b) for a, b in comparable if a is not None and b is not None]
            if comparable and all(a == b for a, b in comparable):
                continue
            reset = any(b < a for a, b in comparable)
            use_last = not comparable or reset
            record = row("codex", path, session_id=session, parent_session_id=parent, agent_id=agent,
                         request_id=hashlib.sha256(fingerprint.encode()).hexdigest()[:24], timestamp=at,
                         model=context.get("model"), effort=context.get("effort") or context.get("reasoning_effort"),
                         measurement="last_usage" if use_last else "cumulative_delta")
            for key, source_key in fields.items():
                if use_last:
                    record[key] = number(last.get(source_key)) if last else None
                else:
                    a, b = number(previous.get(source_key)), number(total.get(source_key))
                    record[key] = b - a if a is not None and b is not None else None
            if use_last:
                notes.append("Counter baseline/reset: only identifiable last-request usage is included; earlier usage may be unmeasured.")
            if not at or not start:
                notes.append("Missing timestamp; inherited-history or time-window filtering is incomplete.")
            if not context:
                notes.append("Missing turn context; model/effort unverified.")
            record["warnings"] = notes
            records.append(record)
            if total is not None:
                previous = total
    return records


def _claude(paths, warnings):
    records = {}
    for path in paths:
        for index, event in enumerate(load_json(path, warnings)):
            if not isinstance(event, dict) or event.get("type") != "assistant":
                continue
            message = event.get("message")
            if not isinstance(message, dict) or message.get("model") == "<synthetic>":
                continue
            usage = message.get("usage")
            if not isinstance(usage, dict):
                continue
            session = event.get("sessionId") or event.get("session_id")
            identity = message.get("id")
            agent = event.get("agentId") or event.get("agent_id")
            if not agent and Path(path).stem.startswith("agent-"):
                agent = Path(path).stem[6:]
            record = row("claude", path, session_id=session, agent_id=agent,
                         parent_session_id=event.get("parentSessionId") or event.get("parent_session_id"),
                         request_id=identity, timestamp=timestamp(event.get("timestamp")),
                         model=message.get("model"), effort=event.get("effort") or message.get("effort"),
                         measurement="message_usage")
            record["cached_input_tokens"] = number(usage.get("cache_read_input_tokens"))
            record["cache_write_input_tokens"] = number(usage.get("cache_creation_input_tokens"))
            record["input_tokens"] = sum_known(number(usage.get("input_tokens")), record["cached_input_tokens"], record["cache_write_input_tokens"])
            record["output_tokens"] = number(usage.get("output_tokens"))
            details = usage.get("output_tokens_details") or {}
            record["reasoning_tokens"] = number(details.get("reasoning_tokens")) if isinstance(details, dict) else None
            record["total_tokens"] = sum_known(record["input_tokens"], record["output_tokens"])
            if not isinstance(identity, str) or not isinstance(session, str) or not identity or not session:
                warnings.append(f"{path}: assistant usage missing message/session ID; unsafe duplicate attribution skipped.")
                continue
            key = (session, identity)
            if key in records:
                # Streaming chunks/tool blocks share message IDs. Retain maxima,
                # not a sum, to preserve final usage if a partial snapshot repeats.
                old = records[key]
                for field in TOKEN_KEYS:
                    candidates = [v for v in (old[field], record[field]) if v is not None]
                    record[field] = max(candidates) if candidates else None
                if old["timestamp"] and not record["timestamp"]:
                    record["timestamp"] = old["timestamp"]
            records[key] = record
    return list(records.values())


def _opencode_sqlite(path, warnings, session_ids=None):
    """Only reads known message/session columns; does not touch credentials/parts."""
    try:
        connection = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)
        connection.execute("PRAGMA query_only=ON")
        tables = {r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        result = []
        for message_table, session_table, v2 in (("message", "session", False), ("session_message", "session_v2", True)):
            if message_table not in tables:
                continue
            if session_table not in tables:
                session_table = "session"
            columns = {r[1] for r in connection.execute(f"PRAGMA table_info({message_table})")}
            if not {"id", "session_id", "data"}.issubset(columns):
                warnings.append(f"{path}: unsupported {message_table} schema; skipped.")
                continue
            sessions = {}
            if session_table in tables:
                session_columns = {r[1] for r in connection.execute(f"PRAGMA table_info({session_table})")}
                if {"id", "parent_id", "time_created"}.issubset(session_columns):
                    sessions = {r[0]: {"id": r[0], "parentID": r[1], "time": {"created": r[2]}}
                                for r in connection.execute(f"SELECT id,parent_id,time_created FROM {session_table}")}
            query = f"SELECT id,session_id,data{',type' if v2 and 'type' in columns else ''} FROM {message_table}"
            parameters = []
            if session_ids is not None:
                if not session_ids:
                    continue
                query += " WHERE session_id IN (" + ",".join("?" for _ in session_ids) + ")"
                parameters = session_ids
            for dbrow in connection.execute(query, parameters):
                try:
                    info = json.loads(dbrow[2])
                    if not isinstance(info, dict):
                        continue
                    info.setdefault("id", dbrow[0])
                    info.setdefault("sessionID", dbrow[1])
                    if v2 and len(dbrow) > 3:
                        info.setdefault("type", dbrow[3])
                    result.append((info, sessions.get(dbrow[1], {})))
                except (json.JSONDecodeError, TypeError):
                    warnings.append(f"{path}: malformed message metadata skipped.")
        return result
    except (sqlite3.Error, OSError) as error:
        warnings.append(f"Cannot read OpenCode database {path}: {type(error).__name__}")
        return []
    finally:
        if 'connection' in locals():
            connection.close()


def _opencode_json(path, warnings):
    result = []
    for event in load_json(path, warnings):
        if not isinstance(event, dict):
            continue
        if isinstance(event.get("messages"), list):
            session = event.get("info") or event.get("session") or {}
            for wrapper in event["messages"]:
                if isinstance(wrapper, dict):
                    info = wrapper.get("info", wrapper)
                    if isinstance(info, dict):
                        info = dict(info)
                        info.setdefault("sessionID", session.get("id"))
                        result.append((info, session))
        else:
            info = event.get("info", event)
            if isinstance(info, dict):
                result.append((info, {}))
    return result


def _opencode(paths, warnings, session_ids=None):
    records = {}
    for path in paths:
        messages = _opencode_sqlite(path, warnings, session_ids) if Path(path).suffix.lower() in {".db", ".sqlite", ".sqlite3"} else _opencode_json(path, warnings)
        for info, session in messages:
            is_v2 = info.get("type") == "assistant"
            if not is_v2 and info.get("role") != "assistant":
                continue
            usage = info.get("tokens")
            if not isinstance(usage, dict):
                continue
            identity, session_id = info.get("id"), info.get("sessionID") or info.get("session_id")
            if not isinstance(identity, str) or not isinstance(session_id, str) or not identity or not session_id:
                warnings.append(f"{path}: OpenCode assistant usage missing message/session ID; skipped.")
                continue
            when = info.get("time") if isinstance(info.get("time"), dict) else {}
            at = timestamp(when.get("completed") or when.get("streamed") or when.get("created"))
            created = timestamp(when.get("created"))
            session_start = timestamp((session.get("time") or {}).get("created"))
            if before(created, session_start):
                warnings.append(f"{path}: copied pre-session OpenCode usage excluded.")
                continue
            cache = usage.get("cache") if isinstance(usage.get("cache"), dict) else {}
            model = info.get("model")
            if isinstance(model, dict):
                provider = model.get("providerID") or model.get("provider")
                model_id = model.get("modelID") or model.get("id")
                model = f"{provider}/{model_id}" if provider and model_id else model_id
            elif not model:
                model_id, provider = info.get("modelID"), info.get("providerID")
                model = f"{provider}/{model_id}" if provider and model_id else model_id
            record = row("opencode", path, session_id=session_id, parent_session_id=session.get("parentID") or session.get("parent_id"),
                         agent_id=info.get("agent"), request_id=identity, timestamp=at,
                         model=model, effort=info.get("variant") or info.get("reasoningEffort"),
                         cost_usd=number(info.get("cost")), measurement="message_usage_v2" if is_v2 else "message_usage_v1")
            record["cached_input_tokens"] = number(cache.get("read"))
            record["cache_write_input_tokens"] = number(cache.get("write"))
            record["input_tokens"] = sum_known(number(usage.get("input")), record["cached_input_tokens"], record["cache_write_input_tokens"])
            record["reasoning_tokens"] = number(usage.get("reasoning"))
            # v2 TokenUsage.Info stores visible output and reasoning separately.
            # Legacy role=assistant keeps provider output (reasoning included).
            record["output_tokens"] = sum_known(number(usage.get("output")), record["reasoning_tokens"]) if is_v2 else number(usage.get("output"))
            record["total_tokens"] = number(usage.get("total"))
            normalized_total = sum_known(record["input_tokens"], record["output_tokens"])
            if record["total_tokens"] is None:
                record["total_tokens"] = normalized_total
            elif normalized_total is not None and record["total_tokens"] != normalized_total:
                record["warnings"].append("Reported total differs from normalized component sum; source total retained.")
            if not session_start:
                record["warnings"].append("Session creation time unavailable; copied-history filtering cannot be verified.")
            key = (session_id, identity)
            if key in records:
                old = records[key]
                for field in (*TOKEN_KEYS, "cost_usd"):
                    candidates = [v for v in (old[field], record[field]) if v is not None]
                    record[field] = max(candidates) if candidates else None
            records[key] = record
    return list(records.values())


def read_usage(host: str, paths: list[str], session_ids: list[str] | None = None) -> tuple[list[dict], list[str]]:
    """Read explicit files only. Runtime uses no network and writes no input files."""
    host = {"claude-code": "claude", "claude_code": "claude"}.get(host, host)
    if host not in {"codex", "claude", "opencode"}:
        raise ValueError("host must be codex, claude, or opencode")
    warnings = []
    unique = list(dict.fromkeys(str(Path(p).resolve()) for p in paths))
    parser = {"codex": _codex, "claude": _claude, "opencode": _opencode}[host]
    records = parser(unique, warnings, session_ids) if host == "opencode" else parser(unique, warnings)
    if session_ids is not None:
        records = [record for record in records if record["session_id"] in session_ids]
    for record in records:
        missing = [key for key in TOKEN_KEYS if record[key] is None]
        if missing:
            record["warnings"].append("Unavailable fields: " + ", ".join(missing))
        if record["cached_input_tokens"] is not None and record["input_tokens"] is not None and record["cached_input_tokens"] > record["input_tokens"]:
            record["warnings"].append("Cache/input counters inconsistent; source semantics require review.")
        warnings.extend(f"{record['host']} {record['session_id']} {record['request_id']}: {note}" for note in record["warnings"])
    if not records and unique:
        warnings.append(f"No recognizable {host} usage records in the selected inputs.")
    return sorted(records, key=lambda r: (r["timestamp"] or "", r["session_id"] or "", r["request_id"] or "")), list(dict.fromkeys(warnings))
