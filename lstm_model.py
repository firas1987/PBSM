# lstm_model.py

import numpy as np
import tensorflow as tf
from tensorflow.keras.models import Sequential, load_model
from tensorflow.keras.layers import LSTM, Dense, Dropout
from tensorflow.keras.callbacks import EarlyStopping
import os
from config import LSTM_HIDDEN_UNITS, LSTM_DROPOUT, LSTM_LEARNING_RATE, LSTM_EPOCHS

def build_lstm(input_shape, output_dim=5):
    """Build a multi-output LSTM model."""
    model = Sequential()
    model.add(LSTM(LSTM_HIDDEN_UNITS, activation='tanh', return_sequences=True, input_shape=input_shape))
    model.add(Dropout(LSTM_DROPOUT))
    model.add(LSTM(LSTM_HIDDEN_UNITS, activation='tanh'))
    model.add(Dropout(LSTM_DROPOUT))
    model.add(Dense(output_dim))
    model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=LSTM_LEARNING_RATE),
                  loss='mse', metrics=['mae'])
    return model

class LSTMPredictor:
    """Handles training and inference for a single controller."""
    def __init__(self, controller_id, model_dir):
        self.controller_id = controller_id
        self.model_dir = model_dir
        self.model = None
        self.history = []   # list of overhead components per time step (as numpy arrays of 5 values)
        self.load_or_create_model()

    def load_or_create_model(self):
        model_path = os.path.join(self.model_dir, f"controller_{self.controller_id}.h5")
        if os.path.exists(model_path):
            self.model = load_model(model_path)
        else:
            self.model = None   # will be trained when enough data is available

    def save_model(self):
        if self.model is not None:
            os.makedirs(self.model_dir, exist_ok=True)
            model_path = os.path.join(self.model_dir, f"controller_{self.controller_id}.h5")
            self.model.save(model_path)

    def add_observation(self, overhead_vector):
        """Append a new observation (alpha, beta, sigma, delta, phi)."""
        self.history.append(np.array(overhead_vector).flatten())
        # Keep only last N for training? We'll use all.

    def prepare_training_data(self, history_len, pred_horizon):
        """Create sequences of (input, target) for training.
        Input: sequence of history_len overhead vectors.
        Target: sequence of pred_horizon overhead vectors (next steps).
        """
        data = np.array(self.history)  # (T, 5)
        X, y = [], []
        for i in range(len(data) - history_len - pred_horizon + 1):
            X.append(data[i:i+history_len])
            y.append(data[i+history_len:i+history_len+pred_horizon])
        return np.array(X), np.array(y)

    def train(self, history_len, pred_horizon):
        """Train the LSTM model on available data."""
        if len(self.history) < history_len + pred_horizon + 10:
            return   # not enough data
        X, y = self.prepare_training_data(history_len, pred_horizon)
        if self.model is None:
            self.model = build_lstm(input_shape=(history_len, 5), output_dim=5*pred_horizon)
        # We need to reshape y to (samples, pred_horizon * 5) for the Dense layer
        y_reshaped = y.reshape(y.shape[0], -1)
        early_stop = EarlyStopping(monitor='loss', patience=5)
        self.model.fit(X, y_reshaped, epochs=LSTM_EPOCHS, batch_size=32, verbose=0, callbacks=[early_stop])
        self.save_model()

    def predict(self, last_sequence, pred_horizon):
        """Predict next pred_horizon overhead vectors given last_sequence (history_len,5)."""
        if self.model is None:
            return None
        X = last_sequence.reshape(1, last_sequence.shape[0], last_sequence.shape[1])
        y_pred = self.model.predict(X, verbose=0)  # shape (1, pred_horizon*5)
        y_pred = y_pred.reshape(pred_horizon, 5)
        return y_pred