"""Explicit inputs only: no global transcript crawling, server, or network calls."""
from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .adapters import read_usage
from .report import read_ledger, write_report, moment, passing_verification


def parser():
    root = argparse.ArgumentParser(description='Routing Harness local usage dashboard (Python 3.10+).')
    sub = root.add_subparsers(dest='command', required=True)
    report = sub.add_parser('report', help='Read explicit telemetry sources and generate HTML/CSV/JSON.')
    report.add_argument('--manifest', type=Path, help='JSON with sources and optional bindings; paths relative to manifest.')
    for host in ('codex', 'claude', 'opencode'):
        report.add_argument('--' + host, action='append', default=[], metavar='PATH', help='Explicit log/export/database file; repeatable.')
    report.add_argument('--ledger', type=Path, help='Append-only skill events.jsonl.')
    report.add_argument('--session', action='append', default=[], metavar='HOST:ID', help='Restrict usage to selected sessions; repeat for child sessions.')
    report.add_argument('--since', help='Include request timestamps at or after this timezone-aware ISO timestamp.')
    report.add_argument('--until', help='Include request timestamps before this timezone-aware ISO timestamp.')
    report.add_argument('--output', type=Path, required=True)
    report.add_argument('--watch', type=float, metavar='SECONDS', help='Manually run refresh loop, minimum 10 seconds; Ctrl+C exits.')
    report.add_argument('--sample', action='store_true', help='Mark every export as illustrative sample data.')
    record = sub.add_parser('record', help='Append one workflow event; does not prove worker correctness.')
    record.add_argument('--ledger', type=Path, required=True)
    record.add_argument('--event', type=Path, required=True, help='JSON object with event_type and task_id.')
    return root


def record_event(ledger, event_path):
    event = json.loads(event_path.read_text(encoding='utf-8-sig'))
    if not isinstance(event, dict) or not event.get('task_id') or not event.get('event_type'):
        raise ValueError('Event must be an object with task_id and event_type.')
    if event['event_type'] in ('dispatch', 'consultation', 'verification', 'assignment_end', 'accept') and not event.get('assignment_id'):
        raise ValueError('Assignment events require assignment_id.')
    event.setdefault('schema_version', 1)
    event.setdefault('event_id', str(uuid.uuid4()))
    event.setdefault('timestamp', datetime.now(timezone.utc).isoformat())
    existing, warnings = read_ledger(ledger) if ledger.exists() else ([], [])
    if warnings:
        raise ValueError('Repair invalid ledger data before appending: ' + '; '.join(warnings))
    if event['event_id'] in {e['event_id'] for e in existing}:
        raise ValueError('Duplicate event_id; nothing appended.')
    if event['event_type'] == 'consultation' and event.get('role') == 'advisor' and not event.get('trigger'):
        raise ValueError('Advisor consultations require a trigger.')
    if event['event_type'] == 'accept' or (event['event_type'] == 'assignment_end' and event.get('outcome') == 'accepted'):
        if not passing_verification(event, existing):
            raise ValueError('Accepted assignment requires a recorded passing lead verification.')
    ledger.parent.mkdir(parents=True, exist_ok=True)
    # Detect truncated last writes instead of concatenating valid JSON onto them.
    if ledger.exists() and ledger.stat().st_size:
        with ledger.open('rb') as handle:
            handle.seek(-1, 2)
            if handle.read(1) not in (b'\n', b'\r'):
                raise ValueError('Ledger must end with a newline before append.')
    with ledger.open('a', encoding='utf-8', newline='\n') as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + '\n')
    return event


def load_inputs(args):
    sources, bindings = [], []
    if args.manifest:
        manifest = json.loads(args.manifest.read_text(encoding='utf-8-sig'))
        if not isinstance(manifest, dict):
            raise ValueError('Manifest must be an object.')
        for src in manifest.get('sources', []):
            if src.get('host') not in ('codex', 'claude', 'opencode'):
                raise ValueError('Source host must be codex, claude, or opencode.')
            paths = src.get('paths', [])
            if not isinstance(paths, list) or not all(isinstance(p, str) for p in paths):
                raise ValueError('Source paths must be a list of file paths.')
            sources.append({'host': src['host'], 'paths': [str((args.manifest.parent / p).resolve()) for p in paths]})
        bindings = manifest.get('bindings', [])
        if not isinstance(bindings, list) or not all(isinstance(b, dict) for b in bindings):
            raise ValueError('bindings must be an array of objects.')
    for host in ('codex', 'claude', 'opencode'):
        paths = getattr(args, host)
        if paths:
            sources.append({'host': host, 'paths': [str(Path(p).resolve()) for p in paths]})
    if not sources and args.ledger is None:
        raise ValueError('Provide explicit telemetry files or --ledger. No session data is auto-discovered.')
    # A typo must not turn into a recursive scan of all private conversations.
    for source in sources:
        for filename in source['paths']:
            if not Path(filename).is_file():
                raise ValueError(f'Source must be an existing file: {filename}')
            if args.output.resolve() == Path(filename).resolve() or args.output.resolve() in Path(filename).resolve().parents:
                raise ValueError('Put report output outside the telemetry source directory.')
    return sources, bindings


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == 'record':
            event = record_event(args.ledger, args.event)
            print('Recorded ' + event['event_id'])
            return 0
        if args.watch is not None and args.watch < 10:
            raise ValueError('--watch must be at least 10 seconds.')
        sources, bindings = load_inputs(args)
        since, until = moment(args.since), moment(args.until)
        if (args.since and since is None) or (args.until and until is None):
            raise ValueError('--since/--until require ISO timestamps with a timezone.')
        if since and until and since >= until:
            raise ValueError('--since must be before --until.')
        session_ids = {}
        for selector in args.session:
            host, separator, sid = selector.partition(':')
            if not separator or host not in ('codex', 'claude', 'opencode') or not sid:
                raise ValueError('--session must be HOST:ID (host codex, claude, or opencode).')
            session_ids.setdefault(host, []).append(sid)
        while True:
            records, warnings = [], []
            # Deduplicate identical input paths across CLI and manifest sources.
            by_host = {}
            for source in sources:
                by_host.setdefault(source['host'], set()).update(source['paths'])
            for host, paths in by_host.items():
                rows, notices = read_usage(host, sorted(paths), session_ids=session_ids.get(host))
                records.extend(rows)
                warnings.extend(notices)
            if since or until:
                missing_time = sum(moment(r.get('timestamp')) is None for r in records)
                if missing_time:
                    warnings.append(f'{missing_time} records excluded by time scope because timestamps are unavailable.')
                records = [r for r in records if (stamp := moment(r.get('timestamp'))) is not None
                           and (since is None or stamp >= since) and (until is None or stamp < until)]
            events, notices = read_ledger(args.ledger)
            warnings.extend(notices)
            report = write_report(args.output, records, events, warnings, bindings, args.sample)
            print(f'{args.output.resolve() / "index.html"} — {len(report["requests"])} requests; {len(report["warnings"])} warnings', flush=True)
            if args.watch is None:
                return 0
            time.sleep(args.watch)
    except KeyboardInterrupt:
        print('\nWatch stopped; no background process remains.')
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 2
