import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from routing_dashboard.adapters import read_usage


class AdaptersTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def write(self, name, data):
        path = self.root / name
        path.write_text(json.dumps(data) if isinstance(data, dict) else "\n".join(json.dumps(e) for e in data), encoding="utf-8")
        return str(path)

    @staticmethod
    def counts(n):
        return {"input_tokens": n, "cached_input_tokens": n // 2, "cache_write_input_tokens": 0, "output_tokens": n // 10, "reasoning_output_tokens": 1, "total_tokens": n + n // 10}

    def codex(self, n, total=None, at="2026-10-20T10:00:02Z"):
        return {"type": "event_msg", "timestamp": at, "payload": {"type": "token_count", "info": {"total_token_usage": self.counts(total if total is not None else n), "last_token_usage": self.counts(n)}}}

    def base(self, identity="s", start="2026-10-20T10:00:00Z", parent=None):
        return [{"type": "session_meta", "payload": {"id": identity, "timestamp": start, "source": {"subagent": {"thread_spawn": {"parent_thread_id": parent}}}}}, {"type": "turn_context", "timestamp": start, "payload": {"turn_id": identity + "t", "model": "m", "effort": "low"}}]

    def test_codex_baseline_delta_duplicate_reset(self):
        events = self.base() + [self.codex(100, 1000), self.codex(100, 1000), self.codex(50, 1050, "2026-10-20T10:00:03Z"), self.codex(20, 20, "2026-10-20T10:00:04Z")]
        path = self.write("c.jsonl", events)
        rows, warnings = read_usage("codex", [path, path])
        self.assertEqual([r["input_tokens"] for r in rows], [100, 50, 20])
        self.assertEqual(rows[0]["model"], "m")
        self.assertTrue(warnings)

    def test_codex_inherited_parent_turn(self):
        parent = self.write("parent.jsonl", self.base("p") + [self.codex(100)])
        events = self.base("child", "2026-10-20T10:00:04Z", "p")
        events += [{"type": "turn_context", "timestamp": "2026-10-20T10:00:05Z", "payload": {"turn_id": "pt", "model": "parent"}}, self.codex(100, at="2026-10-20T10:00:05Z")]
        events += [{"type": "turn_context", "timestamp": "2026-10-20T10:00:06Z", "payload": {"turn_id": "ct", "model": "child"}}, self.codex(30, 130, "2026-10-20T10:00:07Z")]
        child = self.write("child.jsonl", events)
        rows, _ = read_usage("codex", [parent, child])
        self.assertEqual(sum(r["input_tokens"] for r in rows), 130)
        self.assertEqual(rows[-1]["parent_session_id"], "p")

    def test_codex_first_metadata_owns_fork_with_reserialized_parent_history(self):
        parent_events = self.base("p") + [self.codex(100)]
        parent = self.write("parent.jsonl", parent_events)
        child = self.base("c", "2026-10-20T10:00:04Z", "p")[:1]
        # Replay metadata/context with a fresh outer timestamp, as actual forks do.
        child += [dict(parent_events[0], timestamp="2026-10-20T10:00:04Z"),
                  dict(parent_events[1], timestamp="2026-10-20T10:00:04Z"),
                  self.codex(100, 100, "2026-10-20T10:00:04Z")]
        child += [{"type": "event_msg", "timestamp": "2026-10-20T10:00:05Z", "payload": {"type": "thread_settings_applied", "thread_id": "c"}},
                  {"type": "turn_context", "timestamp": "2026-10-20T10:00:06Z", "payload": {"turn_id": "ct", "model": "child", "effort": "high"}},
                  self.codex(30, 130, "2026-10-20T10:00:07Z")]
        child_path = self.write("fork.jsonl", child)
        for paths in ([child_path], [parent, child_path]):
            rows, _ = read_usage("codex", paths)
            child_rows = [r for r in rows if r["session_id"] == "c"]
            self.assertEqual(len(child_rows), 1)
            self.assertEqual(child_rows[0]["parent_session_id"], "p")
            self.assertEqual(child_rows[0]["model"], "child")
            self.assertEqual(child_rows[0]["input_tokens"], 30)
        rows, _ = read_usage("codex", [parent, child_path])
        self.assertEqual(sum(r["input_tokens"] for r in rows), 130)

    def test_codex_fork_without_local_marker_skips_ambiguous_usage(self):
        replay = self.base("c", "2026-10-20T10:00:04Z", "p")[:1]
        replay += [dict(self.base("p")[0], timestamp="2026-10-20T10:00:05Z"),
                   dict(self.base("p")[1], timestamp="2026-10-20T10:00:05Z"),
                   self.codex(100, at="2026-10-20T10:00:06Z")]
        rows, warnings = read_usage("codex", [self.write("unknown-fork.jsonl", replay)])
        self.assertEqual(rows, [])
        self.assertTrue(any("foreign metadata scope" in note for note in warnings))

    def test_codex_unknown_baseline_and_partial_line(self):
        event = self.codex(10)
        del event["payload"]["info"]["last_token_usage"]
        p = self.write("partial.jsonl", self.base() + [event])
        with open(p, "a") as f: f.write('\n{"unfinished":')
        rows, warnings = read_usage("codex", [p])
        self.assertIsNone(rows[0]["input_tokens"])
        self.assertTrue(any("incomplete" in w for w in warnings))

    def claude(self, output, **kw):
        usage = {"input_tokens": 10, "cache_read_input_tokens": 20, "cache_creation_input_tokens": 5, "output_tokens": output}
        usage.update(kw)
        return {"type": "assistant", "sessionId": "claude-s", "timestamp": "2026-10-20T10:00:00Z", "message": {"id": "msg1", "model": "claude", "usage": usage, "content": [{"text": "NEVER_EXPORT_PROMPT"}]}}

    def test_claude_streaming_dedup_and_inclusive_input(self):
        p = self.write("a.jsonl", [self.claude(2), self.claude(8), self.claude(4)])
        rows, _ = read_usage("claude", [p])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["input_tokens"], 35)
        self.assertEqual(rows[0]["output_tokens"], 8)
        self.assertEqual(rows[0]["total_tokens"], 43)
        self.assertIsNone(rows[0]["reasoning_tokens"])
        self.assertNotIn("NEVER_EXPORT_PROMPT", json.dumps(rows))

    def test_claude_missing_cache_unknown_and_tool_ignored(self):
        e = self.claude(4)
        del e["message"]["usage"]["cache_read_input_tokens"]
        p = self.write("agent-agent1.jsonl", [{"type": "user", "message": {"usage": {"input_tokens": 999}}}, e])
        rows, _ = read_usage("claude-code", [p])
        self.assertEqual(rows[0]["agent_id"], "agent1")
        self.assertIsNone(rows[0]["input_tokens"])
        self.assertIsNone(rows[0]["total_tokens"])

    def opencode(self, v2=False):
        return {"id": "m", "sessionID": "os", "type" if v2 else "role": "assistant", "time": {"created": 1792490401000}, "modelID": "model", "providerID": "provider", "tokens": {"input": 10, "output": 5, "reasoning": 2, "cache": {"read": 20, "write": 3}}, "cost": 0.12}

    def test_opencode_export_v1_and_v2_semantics(self):
        p = self.write("o.json", {"info": {"id": "os", "parentID": "parent"}, "messages": [{"info": self.opencode()}]})
        rows, _ = read_usage("opencode", [p])
        self.assertEqual(rows[0]["input_tokens"], 33)
        self.assertEqual(rows[0]["output_tokens"], 5)
        self.assertEqual(rows[0]["total_tokens"], 38)
        self.assertEqual(rows[0]["parent_session_id"], "parent")
        p = self.write("v2.jsonl", [self.opencode(True)])
        rows, _ = read_usage("opencode", [p])
        self.assertEqual(rows[0]["output_tokens"], 7)
        self.assertEqual(rows[0]["total_tokens"], 40)

    def test_opencode_reported_total_preserved(self):
        e = self.opencode();e["tokens"]["total"] = 123
        rows, _ = read_usage("opencode", [self.write("total.jsonl", [e, e])])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["total_tokens"], 123)

    def test_opencode_inherited_exclusion_and_missing_fields(self):
        e = self.opencode()
        p = self.write("inherited.json", {"info": {"id": "os", "time": {"created": 1792490402000}}, "messages": [{"info": e}]})
        rows, warnings = read_usage("opencode", [p])
        self.assertEqual(rows, [])
        self.assertTrue(any("pre-session" in warning for warning in warnings))
        del e["tokens"]["cache"]["write"]
        rows, _ = read_usage("opencode", [self.write("unknown.jsonl", [e])])
        self.assertIsNone(rows[0]["input_tokens"])
        self.assertIsNone(rows[0]["total_tokens"])
        self.assertEqual(rows[0]["output_tokens"], 5)

    def test_filter_excludes_other_sessions(self):
        p = self.write("claude.jsonl", [self.claude(2)])
        self.assertEqual(read_usage("claude", [p], session_ids=["other"])[0], [])
        p = self.write("codex.jsonl", self.base() + [self.codex(10)])
        self.assertEqual(read_usage("codex", [p], session_ids=[])[0], [])

    def test_codex_malformed_metadata_is_warning(self):
        p = self.write("bad.jsonl", [{"type": "session_meta", "payload": []}])
        rows, warnings = read_usage("codex", [p])
        self.assertEqual(rows, [])
        self.assertTrue(warnings)

    def test_sqlite_unknown_schema_warns(self):
        p = self.root / "unknown.db"
        c = sqlite3.connect(p);c.execute("create table message(x text)");c.commit();c.close()
        rows, warnings = read_usage("opencode", [str(p)])
        self.assertEqual(rows, [])
        self.assertTrue(any("unsupported" in warning for warning in warnings))

    def test_opencode_sqlite_read_only_and_both_tables(self):
        p = self.root / "o.db"
        c = sqlite3.connect(p)
        c.execute("create table session(id text,parent_id text,time_created integer)")
        c.execute("insert into session values ('os','parent',0)")
        c.execute("create table message(id text,session_id text,data text)")
        e = self.opencode();del e["id"];del e["sessionID"]
        c.execute("insert into message values (?,?,?)", ("m", "os", json.dumps(e)))
        c.execute("create table session_message(id text,session_id text,type text,data text)")
        e = self.opencode(True);del e["id"];del e["sessionID"];del e["type"]
        c.execute("insert into session_message values (?,?,?,?)", ("m2", "os", "assistant", json.dumps(e)))
        c.commit();c.close()
        original = p.read_bytes()
        rows, _ = read_usage("opencode", [str(p)])
        self.assertEqual(len(rows), 2)
        self.assertEqual(p.read_bytes(), original)
        rows, _ = read_usage("opencode", [str(p)], session_ids=["not-this-session"])
        self.assertEqual(rows, [])
        rows, _ = read_usage("opencode", [str(p)], session_ids=["os"])
        self.assertEqual(len(rows), 2)

    def test_empty_missing_and_unknown_host(self):
        self.assertEqual(read_usage("claude", []), ([], []))
        rows, warnings = read_usage("claude", [str(self.root / "missing")])
        self.assertEqual(rows, [])
        self.assertTrue(warnings)
        with self.assertRaises(ValueError): read_usage("invented", [])


if __name__ == "__main__": unittest.main()
