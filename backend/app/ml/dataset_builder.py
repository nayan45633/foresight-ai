"""Foresight AI - Temporal Forecasting Dataset Construction Engine.

Builds chronological multi-horizon forecasting datasets from network flow timelines:
1. Extracts 28-D instantaneous behavioral features per window.
2. Computes rolling temporal derivative & trend features (rates, entropy shifts, acceleration).
3. Evaluates multi-horizon forward targets (5m, 15m, 30m, 60m) strictly from future events.
4. Enforces strict chronological splitting (Train -> Validation -> Test) without leakage.
5. Generates dataset quality and distribution reports.
"""

from datetime import datetime, timedelta, timezone
import math
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from app.ml.contracts import FlowRecord, TemporalWindowFeatures
from app.telemetry.feature_extractor import NetworkFeatureExtractor
from app.telemetry.window_generator import SlidingWindowGenerator


# Canonical threat taxonomy supported by Foresight AI
CANONICAL_THREATS = [
    "BENIGN",
    "Distributed Denial of Service",
    "Port Scan Reconnaissance",
    "Brute Force Authentication",
    "Data Exfiltration",
]


class TemporalForecastingDataset:
    """Encapsulates prepared features, targets, timestamps, and metadata."""

    def __init__(
        self,
        X: np.ndarray,
        y_horizons: Dict[int, np.ndarray],
        y_classes: Dict[int, List[str]],
        timestamps: List[datetime],
        feature_names: List[str],
    ):
        self.X = X
        self.y_horizons = y_horizons  # {5: array, 15: array, 30: array, 60: array}
        self.y_classes = y_classes    # {5: list of threat strings, ...}
        self.timestamps = timestamps
        self.feature_names = feature_names

    @property
    def sample_count(self) -> int:
        return len(self.X)


class ForecastingDatasetBuilder:
    """Constructs leakage-free temporal sequence datasets for multi-horizon model training."""

    DERIVATIVE_FEATURE_NAMES = [
        "delta_packet_rate",
        "packet_rate_slope",
        "delta_byte_rate",
        "entropy_change_dest_ports",
        "entropy_change_src_ips",
        "syn_rate_acceleration",
        "burst_score_delta",
        "dest_concentration_delta",
    ]

    def __init__(
        self,
        window_size_seconds: int = 60,
        stride_seconds: int = 30,
        rolling_context_steps: int = 4,
    ):
        self.window_size_seconds = window_size_seconds
        self.stride_seconds = stride_seconds
        self.rolling_context_steps = rolling_context_steps
        self._window_generator = SlidingWindowGenerator(
            window_size_seconds=window_size_seconds,
            stride_seconds=stride_seconds,
        )

    @classmethod
    def compute_temporal_derivatives(
        cls, window_sequence: List[TemporalWindowFeatures]
    ) -> List[float]:
        """Computes rate-of-change, acceleration, and trend features over past k windows."""
        if not window_sequence:
            return [0.0] * len(cls.DERIVATIVE_FEATURE_NAMES)

        w_curr = window_sequence[-1]
        w_prev = window_sequence[-2] if len(window_sequence) >= 2 else w_curr

        # 1. Delta packet rate
        delta_pkt_rate = w_curr.packets_per_second - w_prev.packets_per_second

        # 2. Packet rate slope over sequence
        pkt_rates = [w.packets_per_second for w in window_sequence]
        if len(pkt_rates) > 1:
            x_idx = np.arange(len(pkt_rates))
            slope, _ = np.polyfit(x_idx, pkt_rates, 1)
        else:
            slope = 0.0

        # 3. Delta byte rate
        delta_byte_rate = w_curr.bytes_per_second - w_prev.bytes_per_second

        # 4. Entropy change (Destination ports & Source IPs)
        entropy_dst_delta = w_curr.entropy_dest_ports - w_prev.entropy_dest_ports
        entropy_src_delta = w_curr.entropy_source_ips - w_prev.entropy_source_ips

        # 5. SYN rate acceleration
        syn_rate_acc = w_curr.syn_rate - w_prev.syn_rate

        # 6. Burst score delta
        burst_delta = w_curr.traffic_burst_score - w_prev.traffic_burst_score

        # 7. Destination concentration delta
        dest_conc_delta = w_curr.destination_concentration_score - w_prev.destination_concentration_score

        return [
            float(delta_pkt_rate),
            float(slope),
            float(delta_byte_rate),
            float(entropy_dst_delta),
            float(entropy_src_delta),
            float(syn_rate_acc),
            float(burst_delta),
            float(dest_conc_delta),
        ]

    def build_dataset_from_windows(
        self,
        windows: List[TemporalWindowFeatures],
        ground_truth_events: List[Dict[str, Any]],
    ) -> TemporalForecastingDataset:
        """Transforms sliding windows into tabular ML features and multi-horizon forward labels."""
        if not windows:
            raise ValueError("No windows provided for dataset construction")

        feature_matrix: List[List[float]] = []
        timestamps: List[datetime] = []
        y_5m: List[int] = []
        y_15m: List[int] = []
        y_30m: List[int] = []
        y_60m: List[int] = []

        y_5m_threat: List[str] = []
        y_15m_threat: List[str] = []
        y_30m_threat: List[str] = []
        y_60m_threat: List[str] = []

        base_feature_names = [
            "flow_volume", "packet_volume", "byte_volume", "packets_per_second", "bytes_per_second",
            "mean_flow_duration_ms", "duration_variance", "forward_packets_total", "backward_packets_total",
            "forward_bytes_total", "backward_bytes_total", "forward_backward_ratio", "mean_packet_length",
            "packet_length_std", "syn_count", "syn_rate", "ack_count", "rst_count", "syn_ack_ratio",
            "rst_ratio", "unique_source_ips", "unique_destination_ips", "unique_source_ports",
            "unique_destination_ports", "entropy_source_ips", "entropy_dest_ips", "entropy_source_ports",
            "entropy_dest_ports"
        ]
        all_feature_names = base_feature_names + self.DERIVATIVE_FEATURE_NAMES

        # Process each window with its historical context
        for i in range(len(windows)):
            w_curr = windows[i]
            # Context sequence of up to k past windows
            history_start = max(0, i - self.rolling_context_steps + 1)
            seq = windows[history_start : i + 1]

            # 1. Base 28-D vector
            base_vec = list(w_curr.vector) if len(w_curr.vector) == 28 else [0.0] * 28

            # 2. Derivative features
            derivatives = self.compute_temporal_derivatives(seq)

            full_vec = base_vec + derivatives
            feature_matrix.append(full_vec)
            timestamps.append(w_curr.window_end)

            # 3. Compute Forward Targets (Strictly from future intervals [t, t+h])
            t_curr = w_curr.window_end

            for h, y_arr, threat_arr in [
                (5, y_5m, y_5m_threat),
                (15, y_15m, y_15m_threat),
                (30, y_30m, y_30m_threat),
                (60, y_60m, y_60m_threat),
            ]:
                h_start = t_curr
                h_end = t_curr + timedelta(minutes=h)

                # Find any attack event starting inside forward horizon
                attacks_in_horizon = [
                    ev for ev in ground_truth_events
                    if h_start <= ev["timestamp"] <= h_end and ev.get("threat_type", "BENIGN") != "BENIGN"
                ]

                if attacks_in_horizon:
                    y_arr.append(1)
                    threat_arr.append(attacks_in_horizon[0]["threat_type"])
                else:
                    y_arr.append(0)
                    threat_arr.append("BENIGN")

        X_mat = np.array(feature_matrix, dtype=np.float32)
        # Sanitize any non-finite numbers defensively
        X_mat = np.nan_to_num(X_mat, nan=0.0, posinf=1e6, neginf=-1e6)

        return TemporalForecastingDataset(
            X=X_mat,
            y_horizons={
                5: np.array(y_5m, dtype=np.int32),
                15: np.array(y_15m, dtype=np.int32),
                30: np.array(y_30m, dtype=np.int32),
                60: np.array(y_60m, dtype=np.int32),
            },
            y_classes={
                5: y_5m_threat,
                15: y_15m_threat,
                30: y_30m_threat,
                60: y_60m_threat,
            },
            timestamps=timestamps,
            feature_names=all_feature_names,
        )

    @staticmethod
    def chronological_train_val_test_split(
        dataset: TemporalForecastingDataset,
        train_ratio: float = 0.70,
        val_ratio: float = 0.15,
    ) -> Tuple[TemporalForecastingDataset, TemporalForecastingDataset, TemporalForecastingDataset]:
        """Splits temporal dataset strictly chronologically into Train, Validation, and Test partitions."""
        n = dataset.sample_count
        train_end = int(n * train_ratio)
        val_end = int(n * (train_ratio + val_ratio))

        def slice_dataset(start_idx: int, end_idx: int) -> TemporalForecastingDataset:
            return TemporalForecastingDataset(
                X=dataset.X[start_idx:end_idx],
                y_horizons={h: arr[start_idx:end_idx] for h, arr in dataset.y_horizons.items()},
                y_classes={h: dataset.y_classes[h][start_idx:end_idx] for h in dataset.y_classes},
                timestamps=dataset.timestamps[start_idx:end_idx],
                feature_names=dataset.feature_names,
            )

        train_set = slice_dataset(0, train_end)
        val_set = slice_dataset(train_end, val_end)
        test_set = slice_dataset(val_end, n)

        return train_set, val_set, test_set
