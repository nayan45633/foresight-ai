"""Foresight AI - Sliding Temporal Window Generation Engine.

Partitions continuous flow telemetry into sliding time windows (e.g. 60s, 300s, 900s)
and computes behavioral features without temporal leakage.
"""

from bisect import bisect_left, bisect_right
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from app.ml.contracts import FlowRecord, TemporalWindowFeatures
from app.telemetry.feature_extractor import NetworkFeatureExtractor


class SlidingWindowGenerator:
    """Slices chronological flows into sliding windows and extracts feature vectors."""

    def __init__(
        self,
        window_size_seconds: int = 60,
        stride_seconds: int = 30,
        target_entity: str = "GLOBAL_PERIMETER",
    ):
        self.window_size_seconds = window_size_seconds
        self.stride_seconds = stride_seconds
        self.target_entity = target_entity

    def generate_windows_from_flows(
        self,
        flows: List[FlowRecord],
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[TemporalWindowFeatures]:
        """Generates consecutive sliding windows from a collection of flows."""
        if not flows:
            return []

        # Sort flows chronologically to guarantee temporal validity
        sorted_flows = sorted(flows, key=lambda f: f.timestamp)
        timestamps = [f.timestamp for f in sorted_flows]

        first_ts = start_time or sorted_flows[0].timestamp
        last_ts = end_time or sorted_flows[-1].timestamp

        window_duration = timedelta(seconds=self.window_size_seconds)
        stride_duration = timedelta(seconds=self.stride_seconds)

        windows: List[TemporalWindowFeatures] = []
        current_window_start = first_ts

        # Generate windows until we cover up to last_ts
        while current_window_start <= last_ts:
            current_window_end = current_window_start + window_duration

            # Strict temporal filtering: [start, end) via fast bisect
            left_idx = bisect_left(timestamps, current_window_start)
            right_idx = bisect_left(timestamps, current_window_end)
            window_flows = sorted_flows[left_idx:right_idx]

            window_features = NetworkFeatureExtractor.extract_features(
                flows=window_flows,
                window_start=current_window_start,
                window_end=current_window_end,
                duration_seconds=self.window_size_seconds,
                target_entity=self.target_entity,
            )
            window_features.stride_seconds = self.stride_seconds
            windows.append(window_features)

            current_window_start += stride_duration

        return windows
