# migration.py

import numpy as np
from collections import defaultdict
from config import ZETA, T_U_STATIC, K_SLOPE

class MigrationDecision:
    def __init__(self, controllers, switches):
        self.controllers = controllers   # dict id -> controller object
        self.switches = switches         # dict id -> switch object
        self.oscillation_counts = defaultdict(int)   # (switch_id, from_ctrl, to_ctrl) -> count
        self.total_migration_cycles = 0

    def update_oscillation(self, switch_id, from_ctrl, to_ctrl):
        key = (switch_id, from_ctrl, to_ctrl)
        self.oscillation_counts[key] += 1

    def get_oscillation_ratio(self, switch_id, from_ctrl, to_ctrl):
        key = (switch_id, from_ctrl, to_ctrl)
        count = self.oscillation_counts[key]
        return count / max(1, self.total_migration_cycles)

    def compute_dynamic_threshold(self, predicted_util_series):
        """Eq (2-28): T_U_dyn = T_U - k * slope."""
        if len(predicted_util_series) < 2:
            return T_U_STATIC
        slope = np.mean(np.diff(predicted_util_series))
        return T_U_STATIC - K_SLOPE * slope

    def select_victim_switch(self, controller, predicted_util_at_overload, predicted_util_series):
        """
        Choose a switch to migrate from this controller.
        Returns (switch_id, delta_U) or (None, None) if none suitable.
        """
        # We need per-switch contribution to utilization. Approximate by flow rate.
        # In real system, we could measure packet-in rate per switch.
        candidates = []
        for sw_id in controller.switches:
            sw = self.switches[sw_id]
            # Use recent flow arrival rate as proxy for load
            recent_flows = np.mean(sw.flow_arrivals[-10:]) if sw.flow_arrivals else 0
            # Estimate ΔU = (recent_flows * some factor) / controller.capacity_mu
            # Factor = average path length (gamma). We'll use 3.
            gamma = 3.0
            delta_u = (recent_flows * gamma) / controller.capacity_mu
            # Check if removing this switch brings predicted util below dynamic threshold
            T_dyn = self.compute_dynamic_threshold(predicted_util_series)
            if predicted_util_at_overload - delta_u <= T_dyn:
                candidates.append((sw_id, delta_u))

        if not candidates:
            # No single switch solves overload – choose smallest load (Algorithm 2.2 step 13)
            sw_flows = [(sw_id, np.mean(self.switches[sw_id].flow_arrivals[-10:] or [0])) for sw_id in controller.switches]
            if not sw_flows:
                return None, None
            sw_flows.sort(key=lambda x: x[1])
            victim = sw_flows[0][0]
            delta_u = (sw_flows[0][1] * gamma) / controller.capacity_mu
        else:
            # Choose switch with largest delta_u
            candidates.sort(key=lambda x: -x[1])
            victim, delta_u = candidates[0]

        return victim, delta_u

    def select_target_controller(self, source_ctrl, delta_u):
        """Choose controller with lowest current utilization that can accept the load."""
        sorted_ctrls = sorted(self.controllers.values(), key=lambda c: c.current_utilization)
        for ctrl in sorted_ctrls:
            if ctrl.id == source_ctrl.id:
                continue
            if ctrl.current_utilization + delta_u <= T_U_STATIC:   # admission control
                return ctrl.id
        return None

    def evaluate_migration(self, controller, predicted_util_at_overload, predicted_util_series):
        """Implements main logic of Algorithm 2.2 for one controller."""
        victim_id, delta_u = self.select_victim_switch(controller, predicted_util_at_overload, predicted_util_series)
        if victim_id is None:
            return None, None

        target_id = self.select_target_controller(controller, delta_u)
        if target_id is None:
            return None, None

        # Oscillation check
        osc_ratio = self.get_oscillation_ratio(victim_id, controller.id, target_id)
        if osc_ratio > ZETA:
            return None, None

        return victim_id, target_id

    def run_migration_cycle(self, predictions):
        """
        predictions: dict controller_id -> (first_overload_step, predicted_util_series)
        returns list of (victim_sw, from_ctrl, to_ctrl)
        """
        self.total_migration_cycles += 1
        migration_plane = []
        for ctrl_id, (overload_step, util_series) in predictions.items():
            if overload_step is None:
                continue
            ctrl = self.controllers[ctrl_id]
            victim, target = self.evaluate_migration(ctrl, util_series[overload_step], util_series)
            if victim is not None:
                migration_plane.append((victim, ctrl_id, target))
        return migration_plane