#!/usr/bin/env python

import angr
import membership
import probe


class QueryRunner:
    def __init__(self, file):
        self.file = file
        self.project = angr.Project(file, auto_load_libs=False)
        self.mode = None
        self.set_membership_hooks()

    def run_membership_query(self, inputs, alphabet):
        self.set_membership_hooks()
        entry_state = self.project.factory.entry_state(add_options={angr.options.LAZY_SOLVES})
        entry_state.register_plugin('monitor', membership.MonitorStatePlugin(inputs, alphabet))
        sm = self.project.factory.simulation_manager(entry_state)
        # sm.use_technique(angr.exploration_techniques.DFS())

        cond = lambda sm: any(map(lambda state: state.monitor.is_done_membership(), sm.active + sm.deadended))
        while len(sm.active) > 0 and not cond(sm):
            sm.run(until=cond(sm), n=18)

            print('Active states [before]: %d' % len(sm.active))

            sm.prune()

            print('Active states [after]: %d' % len(sm.active))

        if cond(sm):

            print('Membership is true - probing....')

            # Wait for all states to reach the end of the membership word
            sm.run(until=lambda sm: all(map(lambda state: state.monitor.is_done_membership(), sm.active)))
            print(' -> Active states [before]: %d' % len(sm.active))
            sm.prune()
            print(' -> Active states [after]: %d' % len(sm.active))
            for s in sm.active:
                s.options.remove(angr.options.LAZY_SOLVES)

            # Wait for all states to probe
            sm.run(until=lambda sm: all(map(lambda state: state.monitor.done_probing, sm.active)))

            new_symbols = []

            for s in sm.active:
                if s.monitor.done_probing:
                    if s.monitor.probed_symbol is not None:
                        new_symbols.append(s.monitor.probed_symbol)

            for s in sm.deadended:
                if s.monitor.done_probing:
                    if s.monitor.probed_symbol is not None:
                        new_symbols.append(s.monitor.probed_symbol)
                elif s.monitor.probing_pending:
                    s.monitor.collect_pending_probe()
                    if s.monitor.probed_symbol is not None:
                        new_symbols.append(s.monitor.probed_symbol)
            # print(new_symbols)
            return True, new_symbols

        return False, None

    def run_probe_query(self, prefix, alphabet):
        self.set_probe_hooks()
        entry_state = self.project.factory.entry_state()
        entry_state.register_plugin('probe', probe.ProbeStatePlugin(prefix, alphabet))
        sm = self.project.factory.simulation_manager(entry_state)
        sm.run(until=lambda simgr: all(map(lambda state: state.probe.is_done_prefix(), simgr.active)))
        sm.run(until=lambda simgr: all(map(lambda state: state.probe.done_probing, simgr.active)))

        new_symbols = []

        for s in sm.active:
            if s.probe.done_probing:
                if s.probe.probed_symbol is not None:
                    new_symbols.append(s.probe.probed_symbol)

        for s in sm.deadended:
            if s.probe.done_probing:
                if s.probe.probed_symbol is not None:
                    new_symbols.append(s.probe.probed_symbol)
            elif s.probe.probing_pending:
                s.probe.collect_pending_probe()
                if s.probe.probed_symbol is not None:
                    new_symbols.append(s.probe.probed_symbol)

        return new_symbols

    def set_membership_hooks(self):
        if self.mode == 'membership':
            return
        self.project.hook_symbol('smtp_write', membership.MonitorHook(mode='send'))
        self.project.hook_symbol('smtp_read_aux', membership.MonitorHook(mode='read'))
        self.mode = 'membership'

    def set_probe_hooks(self):
        if self.mode == 'probe':
            return
        self.project.hook_symbol('smtp_write', probe.ProbeHook(mode='send'))
        self.project.hook_symbol('smtp_read_aux', probe.ProbeHook(mode='read'))
        self.mode = 'probe'



