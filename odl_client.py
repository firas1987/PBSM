# odl_client.py

import requests
import time
from config import ODL_HOST, ODL_USER, ODL_PASS

class ODLClient:
    """Simple client for OpenDaylight RESTCONF API."""
    def __init__(self, rest_port=8181):
        self.base_url = f"http://{ODL_HOST}:{rest_port}/restconf"
        self.auth = (ODL_USER, ODL_PASS)
        self.headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}

    def get_operational(self, path):
        """GET from operational datastore."""
        url = f"{self.base_url}/operational/{path}"
        resp = requests.get(url, auth=self.auth, headers=self.headers)
        resp.raise_for_status()
        return resp.json()

    def get_config(self, path):
        """GET from config datastore."""
        url = f"{self.base_url}/config/{path}"
        resp = requests.get(url, auth=self.auth, headers=self.headers)
        resp.raise_for_status()
        return resp.json()

    def post_operation(self, operation, data):
        """POST to an RPC operation."""
        url = f"{self.base_url}/operations/{operation}"
        resp = requests.post(url, auth=self.auth, headers=self.headers, json=data)
        resp.raise_for_status()
        return resp.json()

    def get_switches(self):
        """Retrieve list of OpenFlow switches (nodes)."""
        data = self.get_operational("opendaylight-inventory:nodes/")
        nodes = data.get("nodes", {}).get("node", [])
        switches = []
        for node in nodes:
            if "flow-node-inventory:table" in node:   # it's an OpenFlow switch
                switches.append(node['id'])
        return switches

    def get_switch_stats(self, node_id):
        """Get flow and port statistics for a switch."""
        # Flow statistics
        flows_url = f"opendaylight-inventory:nodes/node/{node_id}/flow-node-inventory:table"
        try:
            flow_data = self.get_operational(flows_url)
        except:
            flow_data = {}
        # Port statistics
        ports_url = f"opendaylight-inventory:nodes/node/{node_id}/node-connector"
        try:
            port_data = self.get_operational(ports_url)
        except:
            port_data = {}
        return {'flows': flow_data, 'ports': port_data}

    def set_controller_role(self, node_id, role="MASTER"):
        """Change the role of the controller for a given switch."""
        # This uses the sal-role:change-role RPC
        data = {
            "input": {
                "node": f"/opendaylight-inventory:nodes/node/{node_id}",
                "controller-role": role
            }
        }
        return self.post_operation("sal-role:change-role", data)