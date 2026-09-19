'use client';

import React, { useEffect, useState } from 'react';
import { 
  Activity, 
  Radio, 
  ShieldCheck, 
  AlertTriangle, 
  RefreshCw, 
  Server, 
  Hash, 
  Filter,
  CheckCircle2,
  Database
} from 'lucide-react';
import { FlowRecord, TelemetryQualityReport, TelemetryStats } from '@/types/telemetry';
import { PcapUploadCard } from './PcapUploadCard';

export const TelemetryDashboard: React.FC = () => {
  const [stats, setStats] = useState<TelemetryStats | null>(null);
  const [quality, setQuality] = useState<TelemetryQualityReport | null>(null);
  const [flows, setFlows] = useState<FlowRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [filterProtocol, setFilterProtocol] = useState<string>('ALL');

  const fetchTelemetryData = async () => {
    try {
      const [statsRes, qualityRes, flowsRes] = await Promise.all([
        fetch('http://localhost:8000/api/v1/telemetry/statistics').then((r) => (r.ok ? r.json() : null)),
        fetch('http://localhost:8000/api/v1/telemetry/quality').then((r) => (r.ok ? r.json() : null)),
        fetch('http://localhost:8000/api/v1/telemetry/recent?limit=25').then((r) => (r.ok ? r.json() : [])),
      ]);

      if (statsRes) setStats(statsRes);
      if (qualityRes) setQuality(qualityRes);
      if (flowsRes) setFlows(flowsRes);
    } catch (err) {
      console.error('Failed to fetch telemetry data', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTelemetryData();
    if (!autoRefresh) return;
    const interval = setInterval(fetchTelemetryData, 3000);
    return () => clearInterval(interval);
  }, [autoRefresh]);

  const filteredFlows = filterProtocol === 'ALL'
    ? flows
    : flows.filter((f) => f.protocol === filterProtocol);

  return (
    <div className="space-y-6">
      {/* Top Telemetry Header & Stream Controller */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 glass-panel p-5 sm:p-6 rounded-2xl border border-glass-border">
        <div>
          <div className="flex items-center gap-2.5">
            <Radio className="w-5 h-5 text-cyan-400 animate-pulse" />
            <h2 className="text-base sm:text-lg font-bold text-white tracking-tight">
              Network Telemetry Ingestion Engine
            </h2>
          </div>
          <p className="text-xs text-slate-400 font-normal mt-0.5">
            Canonical FlowRecord Pipeline • Bidirectional Flow Reconstruction • Validation Health
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={`px-3.5 py-1.5 rounded-xl text-xs font-mono border transition-all duration-200 flex items-center gap-2 active:scale-[0.98] ${
              autoRefresh
                ? 'bg-cyan-950/60 border-cyan-800/80 text-cyan-300 shadow-sm'
                : 'bg-slate-900/80 border-white/[0.06] text-slate-400'
            }`}
          >
            <span className={`w-2 h-2 rounded-full ${autoRefresh ? 'bg-cyan-400 shadow-status-glow animate-pulse' : 'bg-slate-600'}`} />
            <span>Live Stream: {autoRefresh ? 'ACTIVE (3s)' : 'PAUSED'}</span>
          </button>

          <button
            onClick={fetchTelemetryData}
            className="p-2 rounded-xl glass-button text-slate-300 hover:text-cyan-300 transition-all flex items-center justify-center shrink-0"
            title="Manual Refresh"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-cyan-400' : ''}`} />
          </button>
        </div>
      </div>

      {/* Metrics Row: Rates & Volumes */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="glass-card p-5 rounded-2xl border border-white/[0.06]">
          <span className="text-xs text-slate-400 block mb-1">Total Flows (1h)</span>
          <p className="text-2xl font-bold font-mono text-white mt-1">
            {stats ? stats.total_flows_last_hour.toLocaleString() : '0'}
          </p>
          <span className="text-[11px] text-slate-500 font-mono mt-1 block">
            Active Sources: {stats?.active_sources || 0}
          </span>
        </div>

        <div className="glass-card p-5 rounded-2xl border border-white/[0.06]">
          <span className="text-xs text-slate-400 block mb-1">Mean Packet Rate</span>
          <p className="text-2xl font-bold font-mono text-cyan-400 mt-1">
            {stats ? `${stats.mean_packet_rate.toFixed(1)} pkt/s` : '0.0 pkt/s'}
          </p>
          <span className="text-[11px] text-slate-500 font-mono mt-1 block">
            Byte Rate: {stats ? `${(stats.mean_byte_rate / 1024).toFixed(1)} KB/s` : '0.0 KB/s'}
          </span>
        </div>

        <div className="glass-card p-5 rounded-2xl border border-white/[0.06]">
          <span className="text-xs text-slate-400 block mb-1">Entity Diversity</span>
          <p className="text-2xl font-bold font-mono text-white mt-1">
            {stats ? `${stats.unique_sources_count} SRC / ${stats.unique_destinations_count} DST` : '0 / 0'}
          </p>
          <span className="text-[11px] text-slate-500 block mt-1">
            Unique Endpoint Cardinality
          </span>
        </div>

        <div className="glass-card p-5 rounded-2xl border border-white/[0.06]">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400">Data Quality Score</span>
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
          </div>
          <p className="text-2xl font-bold font-mono text-emerald-400 mt-1">
            {quality ? `${quality.acceptance_rate_percentage.toFixed(1)}%` : '100.0%'}
          </p>
          <span className="text-[11px] text-slate-500 font-mono mt-1 block">
            {quality?.rejected_records_count || 0} rejected • {quality?.duplicate_records_count || 0} duplicate
          </span>
        </div>
      </div>

      {/* PCAP Upload Section & Protocol Distribution */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div className="lg:col-span-7">
          <PcapUploadCard onUploadSuccess={fetchTelemetryData} />
        </div>

        <div className="lg:col-span-5 space-y-4">
          <div className="glass-panel p-6 rounded-2xl border border-glass-border">
            <h3 className="text-sm font-semibold text-slate-100 mb-4 flex items-center gap-2">
              <Activity className="w-4 h-4 text-cyan-400" /> Protocol Breakdown
            </h3>
            {stats && Object.keys(stats.protocol_breakdown).length > 0 ? (
              <div className="space-y-3 font-mono text-xs">
                {Object.entries(stats.protocol_breakdown).map(([proto, count]) => {
                  const total = stats.total_flows_last_hour || 1;
                  const pct = ((count / total) * 100).toFixed(1);
                  return (
                    <div key={proto} className="space-y-1.5">
                      <div className="flex justify-between text-slate-300">
                        <span className="font-semibold">{proto}</span>
                        <span className="text-slate-400">{count} flows ({pct}%)</span>
                      </div>
                      <div className="w-full h-1.5 bg-slate-900/80 rounded-full overflow-hidden border border-white/[0.04]">
                        <div
                          className="h-full bg-cyan-400 rounded-full transition-all"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="text-center py-6 text-slate-500 font-mono text-xs">
                Awaiting telemetry protocol stream
              </div>
            )}
          </div>

          {/* Quality Rejections Breakdown */}
          {quality && quality.rejection_reasons.length > 0 && (
            <div className="glass-panel p-5 rounded-2xl border border-glass-border">
              <h4 className="text-xs font-semibold text-slate-300 mb-2 flex items-center gap-1.5">
                <AlertTriangle className="w-3.5 h-3.5 text-amber-400" /> Sanitization Rejections
              </h4>
              <div className="space-y-1.5">
                {quality.rejection_reasons.map((rej) => (
                  <div key={rej.reason_code} className="flex justify-between items-center text-xs font-mono bg-slate-950/60 p-2.5 rounded-lg border border-white/[0.04]">
                    <span className="text-amber-400 font-medium">{rej.reason_code}</span>
                    <span className="text-slate-400">{rej.count} records</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Recent Flows Live Table */}
      <div className="glass-panel p-5 sm:p-6 rounded-2xl border border-glass-border">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-white/[0.06] pb-4 mb-4">
          <div className="flex items-center gap-2">
            <Database className="w-4 h-4 text-cyan-400" />
            <h3 className="text-sm font-semibold text-white">
              Live Reconstructed Flow Records
            </h3>
          </div>

          <div className="flex items-center gap-2 text-xs font-mono">
            <Filter className="w-3.5 h-3.5 text-slate-400" />
            <span className="text-slate-400">Filter:</span>
            {['ALL', 'TCP', 'UDP', 'ICMP'].map((proto) => (
              <button
                key={proto}
                onClick={() => setFilterProtocol(proto)}
                className={`px-2.5 py-1 rounded-lg transition-all active:scale-[0.98] ${
                  filterProtocol === proto
                    ? 'bg-slate-800 text-cyan-300 border border-cyan-500/30 shadow-sm'
                    : 'bg-slate-900/60 text-slate-400 hover:text-slate-200 border border-transparent'
                }`}
              >
                {proto}
              </button>
            ))}
          </div>
        </div>

        {filteredFlows.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left font-mono text-xs">
              <thead>
                <tr className="border-b border-white/[0.06] text-slate-400 uppercase text-[10px]">
                  <th className="py-2.5 px-3">Timestamp (UTC)</th>
                  <th className="py-2.5 px-3">Source IP : Port</th>
                  <th className="py-2.5 px-3">Destination IP : Port</th>
                  <th className="py-2.5 px-3">Protocol</th>
                  <th className="py-2.5 px-3">Packets (Fwd/Bwd)</th>
                  <th className="py-2.5 px-3">Bytes</th>
                  <th className="py-2.5 px-3">TCP Flags</th>
                  <th className="py-2.5 px-3">Duration</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.03]">
                {filteredFlows.map((flow, idx) => (
                  <tr key={flow.id || idx} className="hover:bg-slate-800/40 transition-colors text-slate-300">
                    <td className="py-2.5 px-3 text-slate-400">
                      {new Date(flow.timestamp).toISOString().substring(11, 23)}
                    </td>
                    <td className="py-2.5 px-3 font-semibold text-slate-200">
                      {flow.source_ip}:{flow.source_port}
                    </td>
                    <td className="py-2.5 px-3 font-semibold text-slate-200">
                      {flow.destination_ip}:{flow.destination_port}
                    </td>
                    <td className="py-2.5 px-3">
                      <span className="px-2 py-0.5 rounded-full bg-slate-900/80 text-cyan-300 border border-white/[0.06] text-[10px]">
                        {flow.protocol}
                      </span>
                    </td>
                    <td className="py-2.5 px-3">
                      {flow.packet_count} <span className="text-slate-500">({flow.forward_packets || 0}/{flow.backward_packets || 0})</span>
                    </td>
                    <td className="py-2.5 px-3">{flow.byte_count.toLocaleString()} B</td>
                    <td className="py-2.5 px-3 text-amber-400">{flow.tcp_flags || '-'}</td>
                    <td className="py-2.5 px-3 text-slate-400">{flow.flow_duration_ms.toFixed(1)} ms</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-12 text-slate-500 font-mono text-xs">
            <Radio className="w-8 h-8 text-slate-600 mx-auto mb-2" />
            <p className="text-slate-400 font-semibold">Awaiting Telemetry Stream</p>
            <p className="text-slate-600 text-[11px] mt-1">
              Upload a PCAP capture file above or send JSON flows via POST /api/v1/telemetry/flows
            </p>
          </div>
        )}
      </div>
    </div>
  );
};
