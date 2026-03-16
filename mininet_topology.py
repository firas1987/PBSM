# mininet_topology.py

from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info
import networkx as nx
import os
from config import CONTROLLERS, TOPOLOGY_FILE, HOSTS_PER_SWITCH

def create_topology_from_graphml(graphml_file):
    """Load graph from GraphML and return Mininet topology."""
    G = nx.read_graphml(graphml_file)
    # Convert node labels to strings (Mininet requires string names)
    mapping = {node: str(node) for node in G.nodes()}
    G = nx.relabel_nodes(G, mapping)
    return G

def create_grid_topology(rows=5, cols=5):
    """Create a simple grid graph for testing."""
    G = nx.grid_2d_graph(rows, cols)
    G = nx.convert_node_labels_to_integers(G)
    # Convert to string labels
    mapping = {node: str(node) for node in G.nodes()}
    G = nx.relabel_nodes(G, mapping)
    return G

def start_network():
    """Build and start Mininet network with two controllers."""
    # Load topology
    if os.path.exists(TOPOLOGY_FILE):
        G = create_topology_from_graphml(TOPOLOGY_FILE)
    else:
        print(f"Topology file {TOPOLOGY_FILE} not found, using grid.")
        G = create_grid_topology(5, 5)

    net = Mininet(controller=RemoteController, switch=OVSSwitch, autoSetMacs=True)

    # Add controllers
    ctrls = []
    for c in CONTROLLERS:
        ctrl = net.addController(c['name'], ip='127.0.0.1', port=c['of_port'])
        ctrls.append(ctrl)

    # Add switches
    switches = {}
    for node in G.nodes():
        sw = net.addSwitch(f"s{node}", dpid=str(int(node)+1).zfill(16))   # simple DPID
        switches[node] = sw

    # Add links between switches
    for u, v in G.edges():
        net.addLink(switches[str(u)], switches[str(v)])

    # Add hosts
    for node in G.nodes():
        sw = switches[node]
        for i in range(HOSTS_PER_SWITCH):
            host = net.addHost(f"h{node}_{i}")
            net.addLink(host, sw)

    net.build()
    for ctrl in ctrls:
        ctrl.start()
    for sw in switches.values():
        sw.start(ctrls)   # connect to both controllers

    return net, switches, G

if __name__ == '__main__':
    setLogLevel('info')
    net, switches, G = start_network()
    CLI(net)
    net.stop()