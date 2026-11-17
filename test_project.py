"""Small checks for the decisions that matter; run with the controller venv."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import config as C
from collector import Collector
from plot_results import mean_attack


class CollectorTests(unittest.TestCase):
    def test_valid_report_and_timeout(self):
        c = Collector()
        self.assertTrue(c.accept(b'{"node":"h1","tx":8,"rx":0}', ('10.0.0.1', 123)))
        self.assertEqual(c.snapshot()['nodes']['h1']['status'], 'UP')
        c.nodes['h1']['seen'] -= 10
        self.assertEqual(c.snapshot()['nodes']['h1']['status'], 'DOWN')

    def test_bad_data_and_wrong_source(self):
        c = Collector()
        for data in (b'null', b'[]', b'{', b'\xff', b'{"node":[],"tx":0,"rx":0}',
                     b'{"node":"h1","tx":NaN,"rx":0}', b'{"node":"h1","tx":-1,"rx":0}'):
            self.assertFalse(c.accept(data, ('10.0.0.1', 1)))
        self.assertFalse(c.accept(b'{"node":"h1","tx":8,"rx":0}', ('10.0.0.2', 1)))


class ControllerTests(unittest.TestCase):
    def setUp(self):
        import controller
        from os_ken.ofproto import ofproto_v1_3 as ofp, ofproto_v1_3_parser as parser
        self.tmp = tempfile.TemporaryDirectory()
        self.patches = [patch.object(C, 'STATE', Path(self.tmp.name)), patch.object(controller.hub, 'spawn')]
        for p in self.patches:
            p.start()
        self.ctrl = controller.Monitor()
        self.ctrl.enabled = True
        self.dp = SimpleNamespace(id=3, ofproto=ofp, ofproto_parser=parser)
        self.messages = []
        def send(message):
            message.serialize()  # Check actual OpenFlow match/instruction encoding.
            self.messages.append(message)
        self.dp.send_msg = send
        self.ctrl.switches[3] = self.dp

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def sample(self, ingress=9, flow=9, tx=9, age=0):
        now = time.time()-age
        C.save('telemetry.json', {'updated': now, 'nodes': {'h3': {'status': 'UP', 'seen': now, 'tx': tx}}})
        self.ctrl.rates[(3, 'port', 1)] = (ingress, now)
        self.ctrl.rates[(3, 'flow', 1)] = (flow, now)
        self.evaluate()

    def evaluate(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.ctrl.evaluate()

    def test_two_new_samples_and_exemptions(self):
        self.sample()
        self.evaluate()  # Same counters must not count as a second confirmation.
        self.assertNotIn('h3', self.ctrl.blocked)
        self.sample()
        self.assertIn('h3', self.ctrl.blocked)
        self.assertEqual([m.priority for m in self.messages], [100, 150, 200])
        self.assertEqual(self.messages[-1].match['ipv4_dst'], C.SERVER)
        self.assertEqual(self.messages[-1].match['udp_dst'], C.UDP_PORT)

    def test_missing_corroboration_and_staleness(self):
        for kwargs in ({'flow': 0}, {'tx': 0}, {'age': 10}, {'ingress': 6}):
            self.sample(**kwargs)
            self.sample(**kwargs)
            self.assertNotIn('h3', self.ctrl.blocked)

    def test_off_mode(self):
        self.ctrl.enabled = False
        self.sample()
        self.sample()
        self.assertFalse(self.messages)

    def test_release_requires_hold_and_low_traffic(self):
        self.sample()
        self.sample()
        self.sample(1, 1, 1)
        self.assertIn('h3', self.ctrl.blocked)
        self.ctrl.blocked['h3'] -= C.HOLD+1
        self.sample(9, 9, 9)
        self.assertIn('h3', self.ctrl.blocked)
        self.sample(1, 1, 1)
        self.assertNotIn('h3', self.ctrl.blocked)
        self.assertTrue(all(m.command == self.dp.ofproto.OFPFC_DELETE_STRICT for m in self.messages[-3:]))

    def test_probe_disconnect(self):
        self.ctrl.state_change(SimpleNamespace(datapath=SimpleNamespace(id=None), state='dead'))

    def test_normal_forwarding_rules(self):
        self.ctrl.connected(SimpleNamespace(msg=SimpleNamespace(datapath=self.dp)))
        self.assertEqual([m.match['in_port'] for m in self.messages], [1, 2, 3])
        self.assertTrue(all(m.priority == 1 for m in self.messages))
        self.assertTrue(all(m.instructions[0].actions[0].port == self.dp.ofproto.OFPP_NORMAL for m in self.messages))

    def test_counter_reset(self):
        key = (3, 'flow', 1, 1)
        self.assertIsNone(self.ctrl.measure(key, 100, 10))
        self.assertIsNone(self.ctrl.measure(key, 200, 1))

    def test_flow_multipart_sum(self):
        def stat(priority, count):
            return SimpleNamespace(match={'in_port': 1}, priority=priority,
                byte_count=count, duration_sec=10, duration_nsec=0)
        now = time.monotonic()
        for priority in (1, 100):
            self.ctrl.previous[(3, 'flow', 1, priority)] = (0, now-2, 8)
        first = SimpleNamespace(datapath=self.dp, xid=7, flags=1, body=[stat(1, 1000000)])
        self.ctrl.flow_stats(SimpleNamespace(msg=first))
        self.assertNotIn((3, 'flow', 1), self.ctrl.rates)
        second = SimpleNamespace(datapath=self.dp, xid=7, flags=0, body=[stat(100, 1000000)])
        self.ctrl.flow_stats(SimpleNamespace(msg=second))
        self.assertAlmostEqual(self.ctrl.rates[(3, 'flow', 1)][0], 8, delta=.2)


class PlotTests(unittest.TestCase):
    def test_complete_and_incomplete_windows(self):
        rows = [(i, i+1, 4) for i in range(40)]
        self.assertEqual(mean_attack(rows), 4)
        with self.assertRaises(ValueError):
            mean_attack(rows[:15]+rows[16:])


if __name__ == '__main__':
    unittest.main()
