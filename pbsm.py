# pbsm.py

import time
import threading
import numpy as np
import pandas as pd
from collections import defaultdict
import os
import signal
import sys

from config import *
from odl_client import ODLClient
from lstm_model import LSTMPredictor
from migration import MigrationDecision
from utils import setup_logger, init_metrics_file

class ControllerAgent:
    """Represents a controller instance in the PBSM system."""
    def __init__(self, ctrl_info):
        self.id = ctrl_info['id']
        self.name = ctrl_info['name']
        self.of_port = ctrl_info['of_port']
        self.rest_port = ctrl_info.get('rest_port', 8181)
        self.odl_client = ODLClient(rest_port=self.rest_port)
        self.predictor = LSTMPredictor(self.id, MODEL_DIR)
        self.switches = []            # list of switch IDs currently attached
        self.capacity_mu = None       # will be set based on number of switches
        self.current_utilization = 0.0
        self.alpha = []   # time series
        self.beta = []
        self.sigma = []
        self.delta = []
        self.phi = []

    def add_switch(self, sw_id):
        if sw_id not in self.switches:
            self.switches.append(sw_id)

    def remove_switch(self, sw_id):
        if sw_id in self.switches:
            self.switches.remove(sw_id)

    def update_capacity(self):
        """Recompute μ based on number of switches (simplified)."""
        # Use Eq (2-5): μ = P / g(V,E). Here V = number of switches in domain.
        V = len(self.switches)
        if V == 0:
            self.capacity_mu = float('inf')
        else:
            # P from config (you may need to calibrate)
            P = 2**30   # operations per second
            g = V * V   # O(V^2)
            self.capacity_mu = P / g

    def record_observation(self, alpha, beta, sigma, delta, phi):
        """Append overhead components and update utilization."""
        self.alpha.append(alpha)
        self.beta.append(beta)
        self.sigma.append(sigma)
        self.delta.append(delta)
        self.phi.append(phi)

        # Compute utilization according to architecture (simplified: assume D-LV)
        # In a real system, you'd set architecture type per controller.
        gamma = 3.0
        O = (alpha + beta + sigma) + delta + phi * gamma
        if self.capacity_mu is not None and self.capacity_mu > 0:
            self.current_utilization = O / self.capacity_mu
        else:
            self.current_utilization = 0.0

        # Feed to predictor
        self.predictor.add_observation([alpha, beta, sigma, delta, phi])

class PBSMController:
    def __init__(self):
        self.logger = setup_logger('PBSM', LOG_FILE)
        self.controllers = {}   # id -> ControllerAgent
        for c in CONTROLLERS:
            self.controllers[c['id']] = ControllerAgent(c)

        # Switches: we'll build from ODL inventory
        self.switches = {}   # id -> {'name': switch_id, 'controller_id': current controller, 'flow_arrivals': []}

        self.migration_decision = None
        self.running = True
        self.lock = threading.Lock()

        # Metrics
        self.metrics_fields = ['timestamp', 'controller_id', 'utilization', 'response_time', 'migration_events']
        init_metrics_file(METRICS_FILE, self.metrics_fields)

        # Start polling thread
        self.poll_thread = threading.Thread(target=self.poll_loop)
        self.poll_thread.daemon = True

    def start(self):
        self.logger.info("Starting PBSM Controller")
        self.poll_thread.start()
        signal.signal(signal.SIGINT, self.stop)
        signal.signal(signal.SIGTERM, self.stop)
        self.poll_thread.join()

    def stop(self, signum=None, frame=None):
        self.logger.info("Stopping PBSM Controller")
        self.running = False
        sys.exit(0)

    def poll_loop(self):
        """Periodic polling of ODL statistics and decision making."""
        step = 0
        while self.running:
            try:
                self.poll_odl_statistics()
                step += 1

                # Train predictors periodically (e.g., every 50 steps)
                if step % 50 == 0:
                    self.train_predictors()

                # Run migration decision every N steps (e.g., every 5)
                if step % 5 == 0:
                    self.run_migration_cycle(step)

                # Log metrics
                self.log_metrics(step)

                time.sleep(POLL_INTERVAL)
            except Exception as e:
                self.logger.error(f"Error in poll loop: {e}")

    def poll_odl_statistics(self):
        """Fetch statistics from all ODL controllers and update switch/controller state."""
        for ctrl_agent in self.controllers.values():
            try:
                # Get list of switches from this controller
                sw_ids = ctrl_agent.odl_client.get_switches()
                for sw_id in sw_ids:
                    if sw_id not in self.switches:
                        self.switches[sw_id] = {
                            'name': sw_id,
                            'controller_id': ctrl_agent.id,
                            'flow_arrivals': []
                        }
                    # Ensure switch is recorded under this controller (might be multi-homed)
                    ctrl_agent.add_switch(sw_id)

                # For each switch, get packet-in rate (approximated)
                # In ODL, we need to derive packet-in counts. This may require custom monitoring.
                # For demonstration, we'll simulate packet-in rate based on flow stats.
                # Real implementation would need to capture OpenFlow messages.
                alpha = 0.0
                beta = 0.0
                sigma = 0.0
                delta = 0.0
                phi = 0.0

                # Placeholder: in a real system, you'd compute these from counters.
                # We'll simulate with random values for testing.
                # Replace this with actual collection from ODL.
                import random
                alpha = random.uniform(100, 200)
                beta = random.uniform(50, 150)
                sigma = random.uniform(0, 20)
                delta = random.uniform(0, 10)
                phi = random.uniform(0, 5)

                ctrl_agent.record_observation(alpha, beta, sigma, delta, phi)

                # Update per-switch flow arrivals (for victim selection)
                for sw_id in ctrl_agent.switches:
                    # Simulate flow rate per switch
                    flow_rate = random.uniform(0, 10)
                    self.switches[sw_id]['flow_arrivals'].append(flow_rate)

            except Exception as e:
                self.logger.error(f"Error polling controller {ctrl_agent.id}: {e}")

    def train_predictors(self):
        """Train LSTM models for all controllers that have enough data."""
        for ctrl_agent in self.controllers.values():
            try:
                ctrl_agent.predictor.train(HISTORY_WINDOW, PREDICTION_HORIZON)
            except Exception as e:
                self.logger.error(f"Training failed for controller {ctrl_agent.id}: {e}")

    def run_migration_cycle(self, step):
        """Execute migration decision and execution."""
        # First, obtain predictions for all controllers
        predictions = {}
        for ctrl_agent in self.controllers.values():
            if len(ctrl_agent.alpha) < HISTORY_WINDOW:
                continue
            last_seq = np.array([
                ctrl_agent.alpha[-HISTORY_WINDOW:],
                ctrl_agent.beta[-HISTORY_WINDOW:],
                ctrl_agent.sigma[-HISTORY_WINDOW:],
                ctrl_agent.delta[-HISTORY_WINDOW:],
                ctrl_agent.phi[-HISTORY_WINDOW:]
            ]).T   # shape (HISTORY_WINDOW, 5)
            pred = ctrl_agent.predictor.predict(last_seq, PREDICTION_HORIZON)
            if pred is None:
                continue
            # Compute predicted utilization for each future step
            pred_util = []
            for w in range(PREDICTION_HORIZON):
                alpha_p, beta_p, sigma_p, delta_p, phi_p = pred[w]
                gamma = 3.0
                O_p = (alpha_p + beta_p + sigma_p) + delta_p + phi_p * gamma
                util_p = O_p / ctrl_agent.capacity_mu if ctrl_agent.capacity_mu else 0
                pred_util.append(util_p)
            # Find first overload step
            overload_step = None
            T_dyn = MigrationDecision.compute_dynamic_threshold(None, pred_util)   # static method? better to instantiate.
            # We'll create a MigrationDecision object once.
            if self.migration_decision is None:
                # We need controllers and switches dicts. We'll pass them.
                self.migration_decision = MigrationDecision(self.controllers, self.switches)
            for w, u in enumerate(pred_util):
                if u > T_dyn:
                    overload_step = w
                    break
            predictions[ctrl_agent.id] = (overload_step, pred_util)

        # Run migration decisions
        migration_plane = self.migration_decision.run_migration_cycle(predictions)

        # Execute migrations
        for victim_sw, from_id, to_id in migration_plane:
            self.logger.info(f"Migrating switch {victim_sw} from controller {from_id} to {to_id}")
            success = self.execute_migration(victim_sw, from_id, to_id)
            if success:
                # Update local state
                with self.lock:
                    # Remove switch from source controller
                    self.controllers[from_id].remove_switch(victim_sw)
                    self.controllers[from_id].update_capacity()
                    # Add to target
                    self.controllers[to_id].add_switch(victim_sw)
                    self.controllers[to_id].update_capacity()
                    # Update switch mapping
                    self.switches[victim_sw]['controller_id'] = to_id
                    # Update oscillation count
                    self.migration_decision.update_oscillation(victim_sw, from_id, to_id)
                self.log_metrics(step, migration_event=f"{victim_sw}:{from_id}->{to_id}")

    def execute_migration(self, switch_name, from_ctrl_id, to_ctrl_id):
        """Perform the actual switch migration via OVS or ODL role change."""
        try:
            # Option 1: Use OVS command to change controller
            import subprocess
            target_controller = self.controllers[to_ctrl_id]
            target_ip = "127.0.0.1"   # assuming same host
            target_port = target_controller.of_port
            cmd = f"ovs-vsctl set-controller {switch_name} tcp:{target_ip}:{target_port}"
            subprocess.run(cmd, shell=True, check=True)
            self.logger.debug(f"Executed OVS command: {cmd}")
            return True
        except Exception as e:
            self.logger.error(f"Migration failed for {switch_name}: {e}")
            return False

    def log_metrics(self, step, migration_event=None):
        """Append metrics to CSV."""
        import csv
        timestamp = time.time()
        with open(METRICS_FILE, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=self.metrics_fields)
            for ctrl in self.controllers.values():
                writer.writerow({
                    'timestamp': timestamp,
                    'controller_id': ctrl.id,
                    'utilization': ctrl.current_utilization,
                    'response_time': 0.0,   # compute if needed
                    'migration_events': migration_event if migration_event else ''
                })

if __name__ == "__main__":
    pbsm = PBSMController()
    pbsm.start()