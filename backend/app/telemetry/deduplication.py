"""Foresight AI - Deterministic Telemetry Deduplication Engine."""

import hashlib
from typing import List, Set, Tuple
from app.ml.contracts import FlowRecord


class TelemetryDeduplicator:
    """Provides memory-efficient deterministic deduplication of incoming flow streams."""

    def __init__(self, cache_size_limit: int = 100000):
        self._seen_hashes: Set[str] = set()
        self._cache_size_limit = cache_size_limit

    @staticmethod
    def compute_flow_hash(flow: FlowRecord) -> str:
        """Computes a deterministic cryptographic hash representing the flow identity."""
        # Normalize endpoint order for bidirectional consistency
        ip_a, port_a = flow.source_ip, flow.source_port
        ip_b, port_b = flow.destination_ip, flow.destination_port
        
        if (ip_a, port_a) > (ip_b, port_b):
            ip_a, port_a, ip_b, port_b = ip_b, port_b, ip_a, port_a

        # Round timestamp to 1-second granularity to catch identical replay events
        ts_sec = int(flow.timestamp.timestamp())
        
        fingerprint = (
            f"{ip_a}:{port_a}-{ip_b}:{port_b}-"
            f"{flow.protocol.value}-{ts_sec}-"
            f"{flow.packet_count}-{flow.byte_count}-{flow.tcp_flags}"
        )
        return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()

    def filter_duplicates(self, flows: List[FlowRecord]) -> Tuple[List[FlowRecord], int]:
        """Filters out duplicate flow records in a batch and maintains internal cache."""
        unique_flows: List[FlowRecord] = []
        duplicate_count = 0

        # Enforce cache boundary
        if len(self._seen_hashes) > self._cache_size_limit:
            self._seen_hashes.clear()

        batch_seen: Set[str] = set()

        for flow in flows:
            h = self.compute_flow_hash(flow)
            if not flow.id:
                flow.id = f"flow-{h[:16]}"
                
            if h in self._seen_hashes or h in batch_seen:
                duplicate_count += 1
            else:
                batch_seen.add(h)
                self._seen_hashes.add(h)
                unique_flows.append(flow)

        return unique_flows, duplicate_count

    def clear(self) -> None:
        """Clears in-memory deduplication state."""
        self._seen_hashes.clear()
