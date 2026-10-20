import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from routing_dashboard.report import join_records, summarize, task_statistics, write_report, audit_ledger, build_bindings


def observation(**overrides):
    value = dict(host='codex', session_id='s1', agent_id=None, model='model-a', effort='low',
                 request_id='r1', timestamp='2026-10-20T10:00:00Z', input_tokens=100,
                 cached_input_tokens=80, cache_write_input_tokens=0, output_tokens=20,
                 reasoning_tokens=5, total_tokens=120, cost_usd=None)
    value.update(overrides)
    return value


class ReportTests(unittest.TestCase):
    def test_missing_and_weighted_cache_not_zero(self):
        records, _ = join_records([observation(), observation(request_id='r2', input_tokens=900, cached_input_tokens=90)], [])
        group = summarize(records)[0]
        self.assertEqual(group['cache_hit_percent'], 17)
        self.assertEqual(group['total_tokens'], 240)
        records.append(dict(records[0], request_id='r3', total_tokens=None))
        group = summarize(records)[0]
        self.assertIsNone(group['total_tokens'])
        self.assertEqual(group['total_tokens_known_subtotal'], 240)
        self.assertEqual(group['total_tokens_coverage'], '2/3')

    def test_child_not_claimed_by_parent_binding(self):
        bindings = [dict(host='claude', session_id='s1', task_id='t1', role='lead')]
        records, _ = join_records([observation(host='claude', agent_id='child')], bindings)
        self.assertEqual(records[0]['role'], 'unattributed')

    def test_unique_session_hosts_do_not_require_profile_agent_id(self):
        bindings = [dict(host='opencode', session_id='s1', task_id='t1', role='lead')]
        records, _ = join_records([observation(host='opencode', agent_id='build')], bindings)
        self.assertEqual(records[0]['role'], 'lead')

    def test_reused_assignment_windows_and_missing_usage(self):
        events = [dict(event_type='task_start', task_id='t', host='codex', session_id='lead', timestamp='2026-10-20T09:00:00Z'),
                  dict(event_type='dispatch', task_id='t', assignment_id='a1', host='codex', session_id='s1', role='advisor', timestamp='2026-10-20T09:30:00Z'),
                  dict(event_type='assignment_end', task_id='t', assignment_id='a1', timestamp='2026-10-20T10:00:00Z'),
                  dict(event_type='dispatch', task_id='t', assignment_id='a2', host='codex', session_id='s1', role='advisor', timestamp='2026-10-20T10:01:00Z')]
        rows, warnings = join_records([observation(timestamp='2026-10-20T10:10:00Z')], build_bindings(events, []))
        self.assertEqual(rows[0]['assignment_id'], 'a2')
        self.assertFalse(warnings)
        stats = task_statistics(events, rows)[0]
        self.assertIsNone(stats['total_tokens'])
        self.assertEqual(stats['missing_assignments'], 'a1')
        self.assertTrue(stats['missing_lead_usage'])

    def test_ambiguous_or_unknown_time_stays_unattributed(self):
        binding = dict(host='codex', session_id='s1', task_id='t1', role='lead')
        rows, warnings = join_records([observation()], [binding, dict(binding, task_id='t2')])
        self.assertIsNone(rows[0]['task_id'])
        self.assertTrue(warnings)
        rows, _ = join_records([observation(timestamp=None)], [dict(binding, start='2026-10-20T09:00:00Z')])
        self.assertIsNone(rows[0]['task_id'])

    def test_mismatch_and_half_open_windows(self):
        binding = dict(host='codex', session_id='s1', task_id='t1', role='lead',
                       requested_model='model-b', requested_effort='high', end='2026-10-20T11:00:00Z')
        rows, _ = join_records([observation(), observation(timestamp='2026-10-20T11:00:00Z')], [binding])
        self.assertEqual(rows[0]['settings_status'], 'mismatch')
        self.assertIsNone(rows[1]['task_id'])

    def test_zero_advisor_task_and_failed_acceptance(self):
        events = [dict(event_type='task_start', task_id='t1', objective='lookup'),
                  dict(event_type='task_end', task_id='t1', status='completed'),
                  dict(event_type='dispatch', task_id='t1', assignment_id='a1', role='worker'),
                  dict(event_type='verification', task_id='t1', assignment_id='a1', passed=False),
                  dict(event_type='assignment_end', task_id='t1', assignment_id='a1', outcome='accepted')]
        task = task_statistics(events, [])[0]
        self.assertEqual(task['advisor_calls'], 0)
        self.assertEqual(task['first_pass_accepted'], 0)
        self.assertIsNone(task['total_tokens'])
        self.assertTrue(audit_ledger(events))

    def test_unverified_claim_does_not_improve_first_pass_rate(self):
        events = [dict(event_type='task_start', task_id='t'),
                  dict(event_type='dispatch', task_id='t', assignment_id='a', role='worker'),
                  dict(event_type='accept', task_id='t', assignment_id='a')]
        self.assertEqual(task_statistics(events, [])[0]['first_pass_accepted'], 0)
        self.assertTrue(audit_ledger(events))

    def test_repair_is_subset_and_html_csv_safe(self):
        events = [dict(event_type='task_start', task_id='=HYPERLINK("x")', objective='<script>alert(1)</script>'),
                  dict(event_type='task_end', task_id='=HYPERLINK("x")', status='completed')]
        bindings = [dict(host='codex', session_id='s1', task_id=events[0]['task_id'], role='worker', repair_of='a0')]
        with tempfile.TemporaryDirectory() as tmp:
            report = write_report(tmp, [observation()], events, [], bindings)
            self.assertEqual(report['tasks'][0]['repair_tokens_subset'], 120)
            self.assertEqual(report['tasks'][0]['total_tokens'], 120)
            html = (Path(tmp) / 'index.html').read_text(encoding='utf-8')
            self.assertNotIn('<script>alert(1)</script>', html)
            self.assertIn('&lt;script&gt;', html)
            self.assertNotIn('{{TASK_TABLE}}', html)
            with (Path(tmp) / 'tasks.csv').open(encoding='utf-8-sig', newline='') as handle:
                row = next(csv.DictReader(handle))
                self.assertTrue(row['task_id'].startswith("'="))


if __name__ == '__main__':
    unittest.main()
