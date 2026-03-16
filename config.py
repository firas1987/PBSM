# config.py

# OpenDaylight REST API settings
ODL_HOST = "localhost"
ODL_REST_PORT = 8181
ODL_USER = "admin"
ODL_PASS = "admin"

# Controller instances (list of (name, openflow_port, rest_port?))
# For simplicity, we assume two ODL controllers running on different OpenFlow ports.
# They must have REST APIs on the same host/port (but could be different hosts).
CONTROLLERS = [
    {"id": 1, "name": "ODL1", "of_port": 6653, "rest_port": 8181},   # first controller
    {"id": 2, "name": "ODL2", "of_port": 6654, "rest_port": 8182},    # second controller
    {"id": 3, "name": "ODL3", "of_port": 6655, "rest_port": 8183},    # third controller
    {"id": 4, "name": "ODL4", "of_port": 6656, "rest_port": 8184},   # forth controller
    {"id": 5, "name": "ODL5", "of_port": 6657, "rest_port": 8185}    # fifth controller
]

# Mininet topology
TOPOLOGY = "LambdaNet"   # or "grid"
TOPOLOGY_FILE = "LambdaNet.graphml"   # if using GraphML

# Hosts per switch
HOSTS_PER_SWITCH = 5

# Prediction model parameters
HISTORY_WINDOW = 50      # number of past time steps used as input
PREDICTION_HORIZON = 10  # steps ahead to predict
LSTM_EPOCHS = 100
LSTM_LEARNING_RATE = 0.001
LSTM_HIDDEN_UNITS = 50
LSTM_DROPOUT = 0.2

# Utilization threshold (static)
T_U_STATIC = 0.8

# Slope sensitivity for dynamic threshold
K_SLOPE = 2.0

# Oscillation threshold
ZETA = 0.6

# Polling interval (seconds)
POLL_INTERVAL = 1

# Path for saving/loading LSTM models
MODEL_DIR = "./models"

# Logging
LOG_FILE = "pbsm.log"
METRICS_FILE = "metrics.csv"