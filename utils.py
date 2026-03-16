# utils.py

import logging
import csv
import os

def setup_logger(name, log_file, level=logging.INFO):
    """Set up a logger that writes to file and console."""
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler = logging.FileHandler(log_file)
    handler.setFormatter(formatter)
    console = logging.StreamHandler()
    console.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)
    logger.addHandler(console)
    return logger

def init_metrics_file(filename, fieldnames):
    """Create CSV file with headers if it doesn't exist."""
    if not os.path.isfile(filename):
        with open(filename, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()