"""Foresight AI - Real PCAP & PCAPNG Packet Parser Engine.

Streams and inspects genuine network packet files, extracting transport metadata
and reconstructing bidirectional flows via Scapy.
"""

from datetime import datetime, timezone
import os
from typing import Callable, List, Optional, Tuple
from scapy.layers.inet import ICMP, IP, TCP, UDP
from scapy.layers.inet6 import IPv6
from scapy.utils import PcapReader
from app.core.logging import logger
from app.ml.contracts import FlowRecord, ProtocolEnum
from app.telemetry.flow_reconstructor import BidirectionalFlowReconstructor


class PcapParsingStats:
    def __init__(self):
        self.packets_read = 0
        self.packets_ipv4 = 0
        self.packets_ipv6 = 0
        self.packets_tcp = 0
        self.packets_udp = 0
        self.packets_icmp = 0
        self.packets_unsupported = 0
        self.flows_generated = 0
        self.errors = 0


class PcapStreamParser:
    """Streams and parses packets from PCAP/PCAPNG files."""

    def __init__(
        self,
        idle_timeout_seconds: float = 30.0,
        active_timeout_seconds: float = 120.0,
    ):
        self.idle_timeout_seconds = idle_timeout_seconds
        self.active_timeout_seconds = active_timeout_seconds

    @staticmethod
    def _extract_tcp_flags(tcp_layer: TCP) -> str:
        """Decodes raw Scapy TCP flag bits into canonical string."""
        flags: List[str] = []
        f = tcp_layer.flags
        if f & 0x02:  # SYN
            flags.append("SYN")
        if f & 0x10:  # ACK
            flags.append("ACK")
        if f & 0x04:  # RST
            flags.append("RST")
        if f & 0x01:  # FIN
            flags.append("FIN")
        if f & 0x08:  # PSH
            flags.append("PSH")
        if f & 0x20:  # URG
            flags.append("URG")
        return ",".join(flags)

    def parse_pcap_file(
        self,
        file_path: str,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> Tuple[List[FlowRecord], PcapParsingStats]:
        """Parses a PCAP/PCAPNG file, streaming packets through the flow reconstructor."""
        stats = PcapParsingStats()
        reconstructor = BidirectionalFlowReconstructor(
            idle_timeout_seconds=self.idle_timeout_seconds,
            active_timeout_seconds=self.active_timeout_seconds,
        )
        all_flows: List[FlowRecord] = []

        if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
            logger.warning(f"PCAP file is empty or missing: {file_path}")
            return [], stats

        pcap_reader = None
        try:
            pcap_reader = PcapReader(file_path)
            for packet in pcap_reader:
                stats.packets_read += 1
                
                if progress_callback and stats.packets_read % 1000 == 0:
                    progress_callback(stats.packets_read, stats.flows_generated)

                # Extract packet timestamp
                try:
                    pkt_time_float = float(packet.time)
                    pkt_time = datetime.fromtimestamp(pkt_time_float, tz=timezone.utc)
                except Exception:
                    pkt_time = datetime.now(timezone.utc)

                # Layer 3 (IPv4 / IPv6)
                src_ip = None
                dst_ip = None
                if packet.haslayer(IP):
                    stats.packets_ipv4 += 1
                    ip_layer = packet[IP]
                    src_ip = ip_layer.src
                    dst_ip = ip_layer.dst
                elif packet.haslayer(IPv6):
                    stats.packets_ipv6 += 1
                    ip_layer = packet[IPv6]
                    src_ip = ip_layer.src
                    dst_ip = ip_layer.dst
                else:
                    stats.packets_unsupported += 1
                    continue

                # Layer 4 (TCP / UDP / ICMP)
                protocol = ProtocolEnum.OTHER
                src_port = 0
                dst_port = 0
                tcp_flags = None
                pkt_len = len(packet)

                if packet.haslayer(TCP):
                    stats.packets_tcp += 1
                    protocol = ProtocolEnum.TCP
                    tcp_layer = packet[TCP]
                    src_port = tcp_layer.sport
                    dst_port = tcp_layer.dport
                    tcp_flags = self._extract_tcp_flags(tcp_layer)

                elif packet.haslayer(UDP):
                    stats.packets_udp += 1
                    protocol = ProtocolEnum.UDP
                    udp_layer = packet[UDP]
                    src_port = udp_layer.sport
                    dst_port = udp_layer.dport

                elif packet.haslayer(ICMP):
                    stats.packets_icmp += 1
                    protocol = ProtocolEnum.ICMP
                    icmp_layer = packet[ICMP]
                    src_port = getattr(icmp_layer, "type", 0)
                    dst_port = getattr(icmp_layer, "code", 0)

                else:
                    stats.packets_unsupported += 1
                    continue

                # Stream packet into flow reconstructor
                evicted = reconstructor.process_packet(
                    timestamp=pkt_time,
                    src_ip=src_ip,
                    dst_ip=dst_ip,
                    src_port=src_port,
                    dst_port=dst_port,
                    protocol=protocol,
                    packet_len=pkt_len,
                    tcp_flags=tcp_flags,
                )
                if evicted:
                    all_flows.extend(evicted)
                    stats.flows_generated += len(evicted)

            # Flush any remaining active flows at EOF
            remaining = reconstructor.flush_all()
            all_flows.extend(remaining)
            stats.flows_generated += len(remaining)

        except Exception as e:
            stats.errors += 1
            logger.error(f"Error while parsing PCAP file {file_path}: {str(e)}", exc_info=True)
            raise e
        finally:
            if pcap_reader is not None:
                try:
                    pcap_reader.close()
                except Exception:
                    pass

        return all_flows, stats
