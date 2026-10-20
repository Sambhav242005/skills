import json
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from routing_dashboard.cli import record_event, main


class CliTests(unittest.TestCase):
    def test_accept_requires_actual_recorded_pass_after_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger, event = root / 'ledger.jsonl', root / 'event.json'
            def put(data):
                event.write_text(json.dumps(data), encoding='utf-8')
                return record_event(ledger, event)
            put(dict(event_type='verification', task_id='t', assignment_id='a', passed=False))
            with self.assertRaises(ValueError):
                put(dict(event_type='assignment_end', task_id='t', assignment_id='a', outcome='accepted'))
            put(dict(event_type='verification', task_id='t', assignment_id='a', passed=True))
            accepted = put(dict(event_type='assignment_end', task_id='t', assignment_id='a', outcome='accepted'))
            self.assertEqual(accepted['outcome'], 'accepted')
            with self.assertRaises(ValueError):
                put(dict(event_type='accept', task_id='other-task', assignment_id='a'))

    def test_duplicate_and_advisor_trigger(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger, event = root / 'ledger.jsonl', root / 'event.json'
            data = dict(event_type='task_start', task_id='t', event_id='unique')
            event.write_text(json.dumps(data), encoding='utf-8')
            record_event(ledger, event)
            with self.assertRaises(ValueError):
                record_event(ledger, event)
            event.write_text(json.dumps(dict(event_type='consultation', task_id='t', role='advisor')), encoding='utf-8')
            with self.assertRaises(ValueError):
                record_event(ledger, event)

    def test_ledger_only_report_has_zero_advisor_and_no_fabricated_tokens(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = root / 'events.jsonl'
            ledger.write_text(json.dumps(dict(event_id='1', event_type='task_start', task_id='t', objective='example')) + '\n', encoding='utf-8')
            status = main(['report', '--ledger', str(ledger), '--output', str(root / 'report')])
            self.assertEqual(status, 0)
            report = json.loads((root / 'report/report.json').read_text(encoding='utf-8'))
            self.assertEqual(report['tasks'][0]['advisor_calls'], 0)
            self.assertIsNone(report['tasks'][0]['total_tokens'])
            self.assertEqual(report['requests'], [])

    def test_bad_time_and_missing_source_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(main(['report', '--codex', str(root / 'missing'), '--output', str(root / 'report')]), 2)

    def test_watch_is_foreground_and_interruptible(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = root / 'events.jsonl'
            ledger.write_text('', encoding='utf-8')
            with patch('routing_dashboard.cli.time.sleep', side_effect=KeyboardInterrupt):
                self.assertEqual(main(['report', '--ledger', str(ledger), '--output', str(root / 'report'), '--watch', '10']), 0)
            self.assertTrue((root / 'report/index.html').exists())


if __name__ == '__main__':
    unittest.main()
