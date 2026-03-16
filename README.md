# PBSM
This repository implements the PBSM framework as described in the PhD chapter. It integrates with Mininet and OpenDaylight to perform real-time controller utilization prediction and proactive switch migration.

## Prerequisites
- Ubuntu 20.04+ (or any Linux with Mininet support)
- OpenDaylight (e.g., Neon, Sulfur) with OpenFlow plugin and RESTCONF enabled.
- Python 3.8+ with packages listed in `requirements.txt`
- Mininet installed (`sudo apt install mininet`)

- ## Setup
1. **Clone the repository**: https://github.com/firas1987/PBSM
   cd PBSM
   pip install -r requirements.txt
   
2. **Configure OpenDaylight**:
- Start five ODL instances on ports 6653/8181 and 6654/8182 and so on
- Enable required features: install odl-restconf odl-openflowplugin-flow-services odl-mdsal-apidocs
  
3. **Configure the system**:
Edit `config.py` to set controller IPs, ports, and other parameters.

4. **Start Mininet topology** (in a separate terminal): sudo python mininet_topology.py
This will create the network and drop you into the Mininet CLI.

5. **Run the PBSM controller** (in another terminal): sudo -E python pbsm.py

(sudo is needed for OVS commands)

## How It Works

- The PBSM controller polls ODL REST APIs to collect statistics (packet-in rates, etc.).
- It maintains per-controller time series of overhead components (α, β, σ, δ, φ).
- LSTM models predict future utilization. When overload is predicted, the migration decision algorithm selects a switch and a target controller.
- Migration is executed via OVS commands (changing the controller of the switch).

## Files

- `config.py` – all configuration parameters.
- `odl_client.py` – REST client for OpenDaylight.
- `lstm_model.py` – LSTM prediction engine.
- `migration.py` – migration decision logic
- `mininet_topology.py` – creates Mininet topology with 5 controllers.
- `pbsm.py` – main application that orchestrates everything.
- `utils.py` – logging and helper functions.
- `requirements.txt` – Python dependencies.

## Output

- Logs are written to `pbsm.log`.
- Metrics (utilization, migrations) are saved to `metrics.csv` for analysis.
