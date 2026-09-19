"""Foresight AI - Bidirectional Flow Reconstruction & State Timeout Engine."""

from datetime import datetime, timezone
import hashlib
from typing import Dict, List, Optional, Tuple
from app.ml.contracts import FlowDirectionEnum, FlowRecord, ProtocolEnum


class FlowState:
    """Internal mutable tracking state for an active bidirectional network flow."""

    def __init__(
        self,
        key: str,
        first_packet_time: datetime,
        src_ip: str,
        dst_ip: str,
        src_port: int,
        dst_port: int,
        protocol: ProtocolEnum,
        is_initiator: bool = True,
    ):
        self.key = key
        self.initiator_ip = src_ip
        self.initiator_port = src_port
        self.responder_ip = dst_ip
        self.responder_port = dst_port
        self.protocol = protocol
        
        self.first_seen = first_packet_time
        self.last_seen = first_packet_time
        
        self.forward_packets = 0
        self.backward_packets = 0
        self.forward_bytes = 0
        self.backward_bytes = 0
        
        self.observed_flags: set[str] = set()
        self.connection_state = "ESTABLISHED"

    def update(
        self,
        timestamp: datetime,
        src_ip: str,
        src_port: int,
        packet_len: int,
        tcp_flags: Optional[str] = None
    ) -> None:
        """Updates flow state with a new observed packet."""
        if timestamp < self.first_seen:
            self.first_seen = timestamp
        if timestamp > self.last_seen:
            self.last_seen = timestamp

        # Determine if packet is in forward or backward direction
        if src_ip == self.initiator_ip and src_port == self.initiator_port:
            self.forward_packets += 1
            self.forward_bytes += packet_len
        else:
            self.backward_packets += 1
            self.backward_bytes += packet_len

        if tcp_flags:
            for flag in tcp_flags.replace(",", " ").split():
                if flag.strip():
                    self.observed_flags.add(flag.strip().upper())

        # Update state heuristic based on flags
        if "RST" in self.observed_flags:
            self.connection_state = "RESET"
        elif "FIN" in self.observed_flags:
            self.connection_state = "CLOSED"

    def to_flow_record(self) -> FlowRecord:
        """Converts completed / expired flow state into a canonical FlowRecord contract."""
        duration_sec = max(0.0, (self.last_seen - self.first_seen).total_seconds())
        duration_ms = duration_sec * 1000.0
        total_packets = self.forward_packets + self.backward_packets
        total_bytes = self.forward_bytes + self.backward_bytes
        
        rate_div = duration_sec if duration_sec > 0 else 0.001
        pkt_rate = float(total_packets) / rate_div
        byte_rate = float(total_bytes) / rate_div

        flags_str = ",".join(sorted(self.observed_flags))

        flow_hash = hashlib.sha256(
            f"{self.key}-{int(self.first_seen.timestamp())}".encode("utf-8")
        ).hexdigest()[:16]

        return FlowRecord(
            id=f"flow-{flow_hash}",
            timestamp=self.first_seen,
            end_timestamp=self.last_seen,
            source_ip=self.initiator_ip,
            destination_ip=self.responder_ip,
            source_port=self.initiator_port,
            destination_port=self.responder_port,
            protocol=self.protocol,
            flow_duration_ms=duration_ms,
            packet_count=total_packets,
            byte_count=total_bytes,
            packet_rate=pkt_rate,
            byte_rate=byte_rate,
            forward_packets=self.forward_packets,
            backward_packets=self.backward_packets,
            forward_bytes=self.forward_bytes,
            backward_bytes=self.backward_bytes,
            tcp_flags=flags_str,
            connection_state=self.connection_state,
            direction=FlowDirectionEnum.INGRESS,
            metadata={"bidirectional": True, "flags_count": len(self.observed_flags)},
        )


class BidirectionalFlowReconstructor:
    """Reconstructs bidirectional network flows from raw packet streams and manages timeouts."""

    def __init__(
        self,
        idle_timeout_seconds: float = 30.0,
        active_timeout_seconds: float = 120.0,
    ):
        self.idle_timeout_seconds = idle_timeout_seconds
        self.active_timeout_seconds = active_timeout_seconds
        self._active_flows: Dict[str, FlowState] = {}

    @staticmethod
    def compute_canonical_key(
        src_ip: str, dst_ip: str, src_port: int, dst_port: int, protocol: ProtocolEnum
    ) -> str:
        """Generates symmetric 5-tuple key: (A, B) and (B, A) result in the exact same key."""
        ep_a = (src_ip, src_port)
        ep_b = (dst_ip, dst_port)
        if ep_a > ep_b:
            ep_a, ep_b = ep_b, ep_a
        return f"{ep_a[0]}:{ep_a[1]}<->{ep_b[0]}:{ep_b[1]}/{protocol.value}"

    def process_packet(
        self,
        timestamp: datetime,
        src_ip: str,
        dst_ip: str,
        src_port: int,
        dst_port: int,
        protocol: ProtocolEnum,
        packet_len: int,
        tcp_flags: Optional[str] = None
    ) -> List[FlowRecord]:
        """Processes a single packet, updating active flow state or evicting timed-out flows."""
        expired_flows: List[FlowRecord] = []
        key = self.compute_canonical_key(src_ip, dst_ip, src_port, dst_port, protocol)

        if key in self._active_flows:
            flow = self._active_flows[key]
            # Check for active timeout
            if (timestamp - flow.first_seen).total_seconds() > self.active_timeout_seconds:
                expired_flows.append(flow.to_flow_record())
                # Start new flow state
                self._active_flows[key] = FlowState(
                    key=key,
                    first_packet_time=timestamp,
                    src_ip=src_ip,
                    dst_ip=dst_ip,
                    src_port=src_port,
                    dst_port=dst_port,
                    protocol=protocol,
                )
                self._active_flows[key].update(timestamp, src_ip, src_port, packet_len, tcp_flags)
            else:
                flow.update(timestamp, src_ip, src_port, packet_len, tcp_flags)
        else:
            flow = FlowState(
                key=key,
                first_packet_time=timestamp,
                src_ip=src_ip,
                dst_ip=dst_ip,
                src_port=src_port,
                dst_port=dst_port,
                protocol=protocol,
            )
            flow.update(timestamp, src_ip, src_port, packet_len, tcp_flags)
            self._active_flows[key] = flow

        return expired_flows

    def evict_timed_out_flows(self, current_time: datetime) -> List[FlowRecord]:
        """Evicts flows that have been idle past `idle_timeout_seconds`."""
        expired: List[FlowRecord] = []
        keys_to_remove: List[str] = []

        for key, flow in self._active_flows.items():
            idle_duration = (current_time - flow.last_seen).total_seconds()
            if idle_duration >= self.idle_timeout_seconds:
                expired.append(flow.to_flow_record())
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del self._active_flows[key]

        return expired

    def flush_all(self) -> List[FlowRecord]:
        """Flushes all remaining active flows into FlowRecords (e.g. at EOF of a PCAP file)."""
        all_flows = [flow.to_flow_record() for flow in self._active_flows.values()]
        self._active_flows.clear()
        return all_flows

    @property
    def active_flows_count(self) -> int:
        return len(self._active_flows)
