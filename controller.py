"""Monitor host ingress and flow counters; quarantine corroborated heavy senders."""
import os
import time
from os_ken.base import app_manager
from os_ken.controller import ofp_event
from os_ken.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, DEAD_DISPATCHER, set_ev_cls
from os_ken.ofproto import ofproto_v1_3
from os_ken.lib import hub
import config as C


class Monitor(app_manager.OSKenApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.enabled = os.environ.get('MITIGATION', '1') == '1'
        self.switches, self.previous, self.rates, self.parts = {}, {}, {}, {}
        self.hot, self.samples, self.blocked, self.alerts = {}, {}, {}, {}
        hub.spawn(self.monitor)

    def alert(self, key, message):
        if self.alerts.get(key) != message:
            print(time.strftime('%H:%M:%S'), key, message, flush=True)
        self.alerts[key] = message

    def rule(self, dp, priority, match, allow, delete=False):
        p, ofp = dp.ofproto_parser, dp.ofproto
        actions = [p.OFPActionOutput(ofp.OFPP_NORMAL)] if allow else []
        instructions = [p.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]
        dp.send_msg(p.OFPFlowMod(datapath=dp, priority=priority, match=match,
            command=ofp.OFPFC_DELETE_STRICT if delete else ofp.OFPFC_ADD,
            out_port=ofp.OFPP_ANY, out_group=ofp.OFPG_ANY, instructions=[] if delete else instructions))

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def connected(self, event):
        dp = event.msg.datapath
        # Every physical ingress gets a counter; OVS performs normal MAC learning.
        for port in (1, 2, 3):
            self.rule(dp, 1, dp.ofproto_parser.OFPMatch(in_port=port), True)
        for host in self.blocked:
            if C.HOSTS[host][0] == dp.id:
                self.policy(host, dp)

    @set_ev_cls(ofp_event.EventOFPStateChange, [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def state_change(self, event):
        dp = event.datapath
        if dp.id is None:
            return  # Readiness probes can close before the features handshake.
        if event.state == MAIN_DISPATCHER:
            self.switches[dp.id] = dp
            self.alert('s' + str(dp.id), 'CONNECTED')
        else:
            self.switches.pop(dp.id, None)
            for cache in (self.previous, self.rates, self.parts):
                for key in list(cache):
                    if key[0] == dp.id:
                        del cache[key]
            for host, (switch, port) in C.HOSTS.items():
                if switch == dp.id:
                    self.hot[host] = 0
            self.alert('s' + str(dp.id), 'DISCONNECTED')

    def measure(self, key, count, duration=None):
        now = time.monotonic()
        old = self.previous.get(key)
        self.previous[key] = (count, now, duration)
        if old and count >= old[0] and (duration is None or duration > old[2]):
            return (count-old[0])*8/max(now-old[1], 0.001)/1e6
        return None

    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def port_stats(self, event):
        dp = event.msg.datapath
        for stat in event.msg.body:
            rate = self.measure((dp.id, 'port', stat.port_no), stat.rx_bytes)
            key = (dp.id, 'port', stat.port_no)
            if rate is not None:
                self.rates[key] = (rate, time.time())
            else:
                self.rates.pop(key, None)

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def flow_stats(self, event):
        dp, msg = event.msg.datapath, event.msg
        key = (dp.id, msg.xid)
        body = self.parts.setdefault(key, [])
        body.extend(msg.body)
        if msg.flags & dp.ofproto.OFPMPF_REPLY_MORE:
            return
        del self.parts[key]
        totals = {}
        seen = set()
        for stat in body:
            port = stat.match.get('in_port')
            if port is None:
                continue
            key = (dp.id, 'flow', port, stat.priority)
            seen.add(key)
            seconds = stat.duration_sec + stat.duration_nsec / 1e9
            rate = self.measure(key, stat.byte_count, seconds)
            if rate is not None:
                totals[port] = totals.get(port, 0) + rate
        for key in list(self.previous):
            if key[:2] == (dp.id, 'flow') and key not in seen:
                del self.previous[key]
        for port in (1, 2, 3):
            self.rates[(dp.id, 'flow', port)] = (totals.get(port, 0), time.time())

    def policy(self, host, dp, delete=False):
        port = C.HOSTS[host][1]
        p = dp.ofproto_parser
        self.rule(dp, 100, p.OFPMatch(in_port=port), False, delete)
        self.rule(dp, 150, p.OFPMatch(in_port=port, eth_type=0x0806), True, delete)
        self.rule(dp, 200, p.OFPMatch(in_port=port, eth_type=0x0800,
                  ip_proto=17, ipv4_dst=C.SERVER, udp_dst=C.UDP_PORT), True, delete)

    def evaluate(self):
        now = time.time()
        telemetry = C.read('telemetry.json')
        nodes = telemetry.get('nodes', {}) if now-telemetry.get('updated', 0) < C.TIMEOUT else {}
        hosts = {}
        for host, (switch, port) in C.HOSTS.items():
            ingress, pt = self.rates.get((switch, 'port', port), (0, 0))
            flow, ft = self.rates.get((switch, 'flow', port), (0, 0))
            report = nodes.get(host, {})
            app_ok = report.get('status') == 'UP' and now-report.get('seen', 0) < C.TIMEOUT
            net_ok = switch in self.switches and now-min(pt, ft) < C.TIMEOUT
            level = 'UNKNOWN' if not net_ok else 'OK'
            if net_ok and ingress >= C.WARNING:
                level = 'WARNING'
            confirmed = net_ok and app_ok and min(ingress, flow, report.get('tx', 0)) >= C.CRITICAL
            if confirmed:
                level = 'CRITICAL'
            self.alert(host, level)
            previous = self.samples.get(host, (0, 0))
            fresh = net_ok and pt != previous[0] and ft != previous[1]
            if not net_ok:
                self.hot[host] = 0
            if fresh:
                self.samples[host] = (pt, ft)
                self.hot[host] = self.hot.get(host, 0)+1 if confirmed else 0
                if self.enabled and host not in self.blocked and self.hot[host] >= 2:
                    self.policy(host, self.switches[switch])
                    self.blocked[host] = now
                    self.alert(host + ' action', 'QUARANTINE')
                if host in self.blocked and now-self.blocked[host] >= C.HOLD and app_ok and ingress < C.WARNING and report['tx'] < C.WARNING:
                    self.policy(host, self.switches[switch], delete=True)
                    del self.blocked[host]
                    self.alert(host + ' action', 'RELEASE')
            hosts[host] = {'ingress': ingress if net_ok else None, 'flow': flow if net_ok else None,
                           'util': ingress/C.CAPACITY*100 if net_ok else None,
                           'level': level, 'blocked': host in self.blocked}
        C.save('network.json', {'updated': now, 'mitigation': self.enabled, 'hosts': hosts})

    def monitor(self):
        while True:
            for dp in list(self.switches.values()):
                p = dp.ofproto_parser
                dp.send_msg(p.OFPPortStatsRequest(dp, 0, dp.ofproto.OFPP_ANY))
                dp.send_msg(p.OFPFlowStatsRequest(dp))
            hub.sleep(C.POLL)
            self.evaluate()
