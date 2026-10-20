"""Join observed telemetry to an explicit ledger without guessing ownership."""
from __future__ import annotations

import csv
import html
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

METRICS = ('input_tokens', 'cached_input_tokens', 'cache_write_input_tokens',
           'output_tokens', 'reasoning_tokens', 'total_tokens', 'cost_usd')


def moment(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        if dt.tzinfo is None:
            return None
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def read_ledger(path):
    events, warnings, seen = [], [], set()
    if path is None:
        return events, ['No ledger: task, role, consultation, and repair attribution are unavailable.']
    p = Path(path)
    if not p.is_file():
        raise ValueError(f'Ledger does not exist: {p}')
    for index, line in enumerate(p.read_text(encoding='utf-8-sig').splitlines(), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
            # Accept both skill events and the earlier draft harness shape.
            if isinstance(item.get('data'), dict):
                item = {**item['data'], **{k: v for k, v in item.items() if k != 'data'}}
            item['event_type'] = item.get('event_type', item.get('type'))
            key = item.get('event_id')
            if not key:
                warnings.append(f'Ledger line {index}: missing event_id; not counted.')
                continue
            if key in seen:
                continue
            if not item.get('event_type'):
                raise ValueError('missing event_type')
            seen.add(key)
            events.append(item)
        except (ValueError, TypeError, AttributeError) as exc:
            warnings.append(f'Ledger line {index}: invalid/incomplete event ({exc}); not counted.')
    return events, warnings


def _host(value):
    return {'claude-code': 'claude', 'claude_code': 'claude'}.get(value, value)


def build_bindings(events, configured):
    bindings = list(configured)
    task_ends = {e.get('task_id'): e.get('timestamp') for e in events
                 if e.get('event_type') in ('task_end', 'task_finish')}
    # An explicit host is required: thread IDs alone do not identify a provider.
    for event_index, e in enumerate(events):
        if e.get('event_type') not in ('task_start', 'dispatch') or not e.get('host'):
            continue
        sid = e.get('session_id', e.get('thread_id'))
        if not sid:
            continue
        end = task_ends.get(e.get('task_id'))
        if e['event_type'] == 'dispatch':
            for later in events[event_index + 1:]:
                same_assignment = later.get('assignment_id') == e.get('assignment_id')
                finished = same_assignment and later.get('event_type') in ('assignment_end', 'accept', 'outcome')
                reused = (later.get('event_type') == 'dispatch' and later.get('host') == e.get('host')
                          and later.get('session_id', later.get('thread_id')) == sid
                          and later.get('agent_id') == e.get('agent_id'))
                if finished or reused:
                    if moment(later.get('timestamp')):
                        end = later['timestamp']
                    break
        bindings.append({
            'host': _host(e['host']), 'session_id': sid,
            'agent_id': e.get('agent_id'), 'task_id': e.get('task_id'),
            'assignment_id': e.get('assignment_id'),
            'role': 'lead' if e['event_type'] == 'task_start' else e.get('role', 'worker'),
            'requested_model': e.get('requested_model', e.get('model')),
            'requested_effort': e.get('requested_effort', e.get('effort')),
            'start': e.get('timestamp'), 'end': end,
            'repair_of': e.get('repair_of'),
        })
    unique = {json.dumps(b, sort_keys=True): b for b in bindings}
    return list(unique.values())


def join_records(records, bindings):
    result, warnings = [], []
    for raw in records:
        row = dict(raw)
        candidates = []
        for b in bindings:
            if _host(b.get('host')) != row.get('host') or b.get('session_id') != row.get('session_id'):
                continue
            # Claude child transcripts may share their parent's session ID.
            # A session-only binding MUST NOT claim an identified child agent.
            if row.get('host') == 'claude' and b.get('agent_id') != row.get('agent_id'):
                continue
            if row.get('host') != 'claude' and b.get('agent_id') is not None and b.get('agent_id') != row.get('agent_id'):
                continue
            stamp, start, end = moment(row.get('timestamp')), moment(b.get('start')), moment(b.get('end'))
            if (b.get('start') and start is None) or (b.get('end') and end is None):
                continue
            if (start or end) and stamp is None:
                continue
            if start and stamp < start:
                continue
            if end and stamp >= end:  # half-open windows avoid adjacent-task duplicates
                continue
            candidates.append(b)
        if len(candidates) == 1:
            b = candidates[0]
            row.update(task_id=b.get('task_id'), assignment_id=b.get('assignment_id'),
                       role=b.get('role', 'unattributed'), repair_of=b.get('repair_of'),
                       requested_model=b.get('requested_model'), requested_effort=b.get('requested_effort'))
        else:
            row.update(task_id=None, assignment_id=None, role='unattributed', repair_of=None,
                       requested_model=None, requested_effort=None)
            if candidates:
                warnings.append(f'Ambiguous assignment for {row.get("host")}/{row.get("session_id")}; usage left unattributed.')
        requested = row.get('requested_model'), row.get('requested_effort')
        actual = row.get('model'), row.get('effort')
        pairs = list(zip(requested, actual))
        if any(want is not None and got is not None and want != got for want, got in pairs):
            row['settings_status'] = 'mismatch'
            warnings.append(f'Observed settings differ for assignment {row.get("assignment_id") or "unattributed"}.')
        elif all(want is not None and got is not None for want, got in pairs):
            row['settings_status'] = 'verified'
        else:
            row['settings_status'] = 'unverified'
        result.append(row)
    return result, warnings


def summarize(records):
    groups = defaultdict(list)
    for row in records:
        groups[(row.get('task_id'), row.get('assignment_id'), row.get('host'), row.get('session_id'),
                row.get('agent_id'), row.get('role'), row.get('model'), row.get('effort'))].append(row)
    rows = []
    for key, values in groups.items():
        item = dict(zip(('task_id', 'assignment_id', 'host', 'session_id', 'agent_id', 'role', 'model', 'effort'), key))
        item['requests'] = len(values)
        for metric in METRICS:
            known = [v[metric] for v in values if v.get(metric) is not None]
            item[metric] = sum(known) if len(known) == len(values) else None
            item[metric + '_known_subtotal'] = sum(known) if known else None
            item[metric + '_coverage'] = f'{len(known)}/{len(values)}'
        inp, cached = item['input_tokens'], item['cached_input_tokens']
        item['cache_hit_percent'] = round(cached / inp * 100, 2) if inp and cached is not None and 0 <= cached <= inp else None
        item['settings_status'] = ', '.join(sorted({v['settings_status'] for v in values}))
        item['requested_model'] = ', '.join(sorted({str(v['requested_model']) for v in values if v.get('requested_model')})) or None
        item['requested_effort'] = ', '.join(sorted({str(v['requested_effort']) for v in values if v.get('requested_effort')})) or None
        item['repair_of'] = ', '.join(sorted({str(v['repair_of']) for v in values if v.get('repair_of')})) or None
        rows.append(item)
    return rows


def task_statistics(events, records):
    starts = {e['task_id']: e for e in events if e.get('event_type') == 'task_start' and e.get('task_id')}
    tasks = []
    for task_id, start in starts.items():
        own = [e for e in events if e.get('task_id') == task_id]
        ending = [e for e in own if e['event_type'] in ('task_end', 'task_finish')]
        status = ending[-1].get('status', ending[-1].get('outcome', 'unknown')) if ending else 'active'
        consultations = [e for e in own if e['event_type'] == 'consultation']
        advisors = [e for e in consultations if e.get('role') == 'advisor']
        routers = [e for e in consultations if e.get('role') == 'router']
        workers = [e for e in own if e['event_type'] == 'dispatch' and e.get('role') == 'worker']
        accepts = [e for index, e in enumerate(own) if e['event_type'] in ('assignment_end', 'accept') and
                   e.get('outcome', 'accepted' if e['event_type'] == 'accept' else None) == 'accepted'
                   and passing_verification(e, own[:index])]
        accepted_ids = {e.get('assignment_id') for e in accepts}
        first_pass = 0
        for worker in workers:
            aid = worker.get('assignment_id')
            failures = [e for e in own if e.get('assignment_id') == aid and (
                (e['event_type'] == 'assignment_end' and e.get('outcome') == 'failed') or
                (e['event_type'] == 'verification' and (e.get('passed') is False or e.get('verdict') == 'fail')))]
            if aid in accepted_ids and not failures and not worker.get('retry_of') and not worker.get('repair_of'):
                first_pass += 1
        usage = [r for r in records if r.get('task_id') == task_id]
        total_known = [r['total_tokens'] for r in usage if r.get('total_tokens') is not None]
        expected = {e.get('assignment_id') for e in own if e['event_type'] in ('dispatch', 'consultation') and e.get('assignment_id')}
        observed_assignments = {r.get('assignment_id') for r in usage if r.get('assignment_id')}
        missing_assignments = expected - observed_assignments
        missing_lead = bool(start.get('host')) and not any(r.get('role') == 'lead' for r in usage)
        complete = bool(usage) and len(total_known) == len(usage) and not missing_assignments and not missing_lead
        advisor_usage = [r for r in usage if r.get('role') == 'advisor']
        repair_usage = [r for r in usage if r.get('repair_of')]
        def role_total(rows):
            return sum(r['total_tokens'] for r in rows) if rows and all(r.get('total_tokens') is not None for r in rows) else None
        adv_total = role_total(advisor_usage)
        if complete and not advisors and not advisor_usage:
            adv_total = 0
        tasks.append({
            'task_id': task_id, 'objective': start.get('objective', ''), 'status': status,
            'router_calls': len(routers), 'advisor_calls': len(advisors),
            'worker_assignments': len(workers), 'lead_overrides': sum(e['event_type'] == 'override' for e in own),
            'retries': sum(bool(e.get('retry_of')) for e in workers) + sum(e['event_type'] == 'retry' for e in own),
            'escalations': sum(e['event_type'] == 'escalation' for e in own),
            'first_pass_accepted': first_pass,
            'first_pass_percent': round(first_pass / len(workers) * 100, 2) if workers else None,
            'total_tokens': sum(total_known) if complete else None,
            'known_total_tokens': sum(total_known) if total_known else None,
            'usage_coverage': f'{len(total_known)}/{len(usage)}',
            'assignment_coverage': f'{len(expected & observed_assignments)}/{len(expected)}',
            'missing_assignments': ', '.join(sorted(str(a) for a in missing_assignments)) or None,
            'missing_lead_usage': missing_lead,
            'advisor_tokens': adv_total,
            'advisor_token_share_percent': round(adv_total / sum(total_known) * 100, 2) if complete and sum(total_known) and adv_total is not None else None,
            'repair_tokens_subset': role_total(repair_usage),
            'advisor_triggers': '; '.join(str(e.get('trigger', 'unrecorded')) for e in advisors),
            'advisor_outcomes': '; '.join(str(e.get('outcome', 'unrecorded')) for e in advisors),
        })
    return tasks


def passing_verification(event, earlier):
    key = event.get('task_id'), event.get('assignment_id')
    if not all(key):
        return False
    checks = [e for e in earlier if e.get('event_type') == 'verification'
              and (e.get('task_id'), e.get('assignment_id')) == key]
    if not checks:
        return False
    check = checks[-1]
    return ((check.get('passed') is True or check.get('verdict') == 'pass')
            and check.get('passed') is not False and check.get('verdict') != 'fail')


def audit_ledger(events):
    warnings = []
    for index, e in enumerate(events):
        aid = e.get('assignment_id')
        if e['event_type'] in ('accept', 'assignment_end') and e.get('outcome', 'accepted' if e['event_type'] == 'accept' else None) == 'accepted':
            if not passing_verification(e, events[:index]):
                warnings.append(f'Acceptance without a passing lead verification: {aid}. Ledger claim is not proof of correctness.')
        if e['event_type'] == 'consultation' and e.get('role') == 'advisor' and not e.get('trigger'):
            warnings.append(f'Advisor consultation missing trigger: {e.get("event_id")}.')
    return warnings


def csv_write(path, rows, default_fields):
    fields = list(dict.fromkeys(k for row in rows for k in row)) or list(default_fields)
    with path.open('w', newline='', encoding='utf-8-sig') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            safe = {}
            for key, value in row.items():
                if isinstance(value, (list, dict)):
                    value = json.dumps(value, ensure_ascii=False)
                # Spreadsheet formula injection is possible even in locally exported text.
                if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@')):
                    value = "'" + value
                safe[key] = value
            writer.writerow(safe)


def table(title, rows, columns, table_id):
    esc = lambda value: html.escape(str(value), quote=True)
    cells = []
    for row in rows:
        rendered = []
        for index, (key, label) in enumerate(columns):
            value = row.get(key)
            text = 'unavailable' if value is None else str(value)
            tag = 'th scope="row"' if index == 0 else 'td'
            close = 'th' if index == 0 else 'td'
            rendered.append(f'<{tag}>{esc(text)}</{close}>')
        cells.append('<tr>' + ''.join(rendered) + '</tr>')
    body = ''.join(cells) or f'<tr><td colspan="{len(columns)}">No records in this view.</td></tr>'
    heads = ''.join(f'<th scope="col"><button type="button" data-sort="{i}">{esc(label)}</button></th>' for i, (_, label) in enumerate(columns))
    return f'<section><h2 id="{table_id}-title">{esc(title)}</h2><div class="table-wrap" tabindex="0" role="region" aria-labelledby="{table_id}-title"><table id="{table_id}"><caption>{esc(title)}</caption><thead><tr>{heads}</tr></thead><tbody>{body}</tbody></table></div></section>'


def write_report(output, records, events, warnings, bindings, sample=False):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    joined, join_warnings = join_records(records, build_bindings(events, bindings))
    warnings = list(dict.fromkeys(warnings + join_warnings + audit_ledger(events)))
    agents = summarize(joined)
    tasks = task_statistics(events, joined)
    completed = [t for t in tasks if t['status'] in ('completed', 'accepted')]
    advisor_tasks = sum(t['advisor_calls'] > 0 for t in completed)
    rate = f'{advisor_tasks}/{len(completed)} completed recorded tasks' if completed else 'unavailable (no completed recorded tasks)'
    snapshot = datetime.now(timezone.utc).isoformat()
    bundle = {'schema_version': 1, 'generated_at': snapshot, 'sample_data': sample,
              'tasks': tasks, 'agents': agents, 'requests': joined, 'warnings': warnings,
              'advisor_task_rate': rate,
              'allowance_snapshots': [e for e in events if e['event_type'] in ('allowance', 'allowance_snapshot')]}
    (output / 'report.json').write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding='utf-8')
    csv_write(output / 'tasks.csv', tasks, ['task_id', 'status', 'advisor_calls'])
    csv_write(output / 'agents.csv', agents, ['host', 'session_id', 'role', 'total_tokens'])
    csv_write(output / 'requests.csv', joined, ['host', 'session_id', 'request_id', 'total_tokens'])
    table_agents = table('Agent usage matrix', agents, [
        ('task_id','Task'),('host','Host'),('role','Role'),('model','Observed model'),('effort','Observed effort'),
        ('requested_model','Requested model'),('requested_effort','Requested effort'),('settings_status','Settings'),
        ('requests','Requests'),('input_tokens','Input incl. cache'),('cached_input_tokens','Cache reads'),
        ('cache_write_input_tokens','Cache writes'),('cache_hit_percent','Cache hit %'),('output_tokens','Output'),
        ('reasoning_tokens','Reasoning subset'),('total_tokens','Total'),('total_tokens_coverage','Total coverage'),
        ('total_tokens_known_subtotal','Known subtotal'),('repair_of','Repair of (subset)')], 'agents')
    task_table = table('Tasks and advisor activity', tasks, [
        ('task_id','Task'),('objective','Objective'),('status','Status'),('router_calls','Router calls'),
        ('advisor_calls','Advisor calls'),('advisor_triggers','Advisor triggers'),('advisor_outcomes','Advice outcomes'),
        ('worker_assignments','Workers'),('lead_overrides','Overrides'),('first_pass_percent','First pass %'),
        ('retries','Retries'),('escalations','Escalations'),('total_tokens','Total tokens'),('usage_coverage','Request coverage'),
        ('assignment_coverage','Assignment coverage'),('missing_assignments','Missing usage assignments'),
        ('advisor_token_share_percent','Advisor share %'),('repair_tokens_subset','Repair tokens (subset)')], 'tasks')
    warning_html = ''.join('<li>' + html.escape(w) + '</li>' for w in warnings) or '<li>No parser or ledger warnings.</li>'
    allowances = bundle['allowance_snapshots']
    allowance_html = html.escape(json.dumps(allowances, indent=2)) if allowances else 'Unavailable. Account allowance is separate from task tokens.'
    template = (Path(__file__).parent / 'dashboard.html').read_text(encoding='utf-8')
    replacements = {
        '{{SNAPSHOT}}': html.escape(snapshot), '{{MODE}}': 'SAMPLE DATA — not measured usage' if sample else 'Local measured telemetry',
        '{{REQUESTS}}': str(len(joined)), '{{TASKS}}': str(len(tasks)), '{{ADVISOR_RATE}}': html.escape(rate),
        '{{TASK_TABLE}}': task_table, '{{AGENT_TABLE}}': table_agents,
        '{{WARNINGS}}': warning_html, '{{ALLOWANCE}}': allowance_html,
    }
    for key, value in replacements.items():
        template = template.replace(key, value)
    (output / 'index.html').write_text(template, encoding='utf-8')
    return bundle
