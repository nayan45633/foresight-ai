'use client';

import React, { useEffect, useState } from 'react';
import { 
  Activity, 
  AlertTriangle, 
  ArrowRight, 
  BrainCircuit, 
  CheckCircle2, 
  Clock, 
  Layers, 
  Radio, 
  RefreshCw, 
  Scale, 
  Shield, 
  ShieldAlert, 
  ShieldCheck, 
  Sliders, 
  Sparkles, 
  Target, 
  Timer, 
  TrendingDown, 
  TrendingUp, 
  Workflow, 
  Zap 
} from 'lucide-react';
import { forecastApi, MultiHorizonTimelineResponse, LeadTimeScorecardResponse } from '@/lib/api/forecast';
import { riskApi, RiskStateEvaluation } from '@/lib/api/risk';
import { telemetryApi, TelemetryStatsResponse } from '@/lib/api/telemetry';
import { ForecastCardSkeleton, GlassSkeleton } from '@/components/ui/GlassSkeleton';
import { EmptyState } from '@/components/ui/EmptyState';

interface CommandCenterOverviewProps {
  onNavigateTab: (tabId: string) => void;
}

export function CommandCenterOverview({ onNavigateTab }: CommandCenterOverviewProps) {
  const [riskState, setRiskState] = useState<RiskStateEvaluation | null>(null);
  const [timeline, setTimeline] = useState<MultiHorizonTimelineResponse | null>(null);
  const [scorecard, setScorecard] = useState<LeadTimeScorecardResponse | null>(null);
  const [telemetryStats, setTelemetryStats] = useState<TelemetryStatsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchOverviewData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [riskRes, timelineRes, scoreRes, statsRes] = await Promise.allSettled([
        riskApi.getCurrentState(),
        forecastApi.getTimeline(),
        forecastApi.getLeadTimeScorecard(),
        telemetryApi.getStatistics(),
      ]);

      if (riskRes.status === 'fulfilled') setRiskState(riskRes.value);
      if (timelineRes.status === 'fulfilled') setTimeline(timelineRes.value);
      if (scoreRes.status === 'fulfilled') setScorecard(scoreRes.value);
      if (statsRes.status === 'fulfilled') setTelemetryStats(statsRes.value);

      if (riskRes.status === 'rejected' && timelineRes.status === 'rejected') {
        setError('Unable to retrieve command center telemetry. Forecasting models may be initializing.');
      }
    } catch (err: any) {
      setError(err.message || 'Error loading SOC overview data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOverviewData();
    const interval = setInterval(fetchOverviewData, 30000); // 30s gentle refresh
    return () => clearInterval(interval);
  }, []);

  const getRiskBadge = (state?: string) => {
    switch (state) {
      case 'CRITICAL':
        return { bg: 'bg-rose-500/20 text-rose-300 border-rose-500/40 animate-pulse', label: 'CRITICAL THREAT' };
      case 'ELEVATED':
        return { bg: 'bg-orange-500/20 text-orange-300 border-orange-500/40', label: 'ELEVATED RISK' };
      case 'SUSPICIOUS':
        return { bg: 'bg-amber-500/20 text-amber-300 border-amber-500/40', label: 'SUSPICIOUS ACTIVITY' };
      case 'WATCH':
        return { bg: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40', label: 'WATCH PERIMETER' };
      default:
        return { bg: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40', label: 'NORMAL OPERATIONS' };
    }
  };

  const riskBadge = getRiskBadge(riskState?.current_state);

  return (
    <div className="space-y-8 animate-tab-content">
      {/* 1. Command Center Hero & Real Risk Banner */}
      <div className="glass-panel p-6 sm:p-8 rounded-2xl border border-glass-border relative overflow-hidden">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6 pb-6 border-b border-white/[0.06]">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-cyan-500/10 text-cyan-400 text-xs font-mono mb-3 border border-cyan-500/20">
              <Shield className="w-3.5 h-3.5" /> SOC Command Center Overview
            </div>
            <h2 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
              Defensive Attack Forecasting & Posture
            </h2>
            <p className="mt-2 text-slate-300 text-sm max-w-3xl leading-relaxed">
              Real-time situational intelligence synthesized from telemetry behavior calculus, multi-horizon gradient boosting, and conformal uncertainty quantification.
            </p>
          </div>

          <div className="flex items-center gap-3 shrink-0">
            <button
              onClick={fetchOverviewData}
              disabled={loading}
              className="px-3.5 py-2 rounded-xl glass-button text-xs font-mono text-slate-300 hover:text-white flex items-center gap-2"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-cyan-400' : ''}`} />
              Refresh Feed
            </button>
          </div>
        </div>

        {/* State Indicators Row */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-6">
          {/* Current Risk State */}
          <div className="p-4 rounded-xl glass-card border border-white/[0.06] flex flex-col justify-between">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-mono text-slate-400 uppercase">Current Risk State</span>
              <span className={`text-[10px] px-2.5 py-0.5 rounded-full font-mono font-bold border ${riskBadge.bg}`}>
                {riskBadge.label}
              </span>
            </div>
            <div className="my-2">
              <span className="text-2xl font-bold text-white tracking-tight">
                {riskState ? riskState.current_state : loading ? 'PROBING...' : 'NORMAL'}
              </span>
              <p className="text-[11px] text-slate-400 mt-1">
                Previous: <span className="text-slate-300 font-mono">{riskState?.previous_state || 'NORMAL'}</span>
                {riskState?.is_hysteresis_dampened && ' • Hysteresis Dampened'}
              </p>
            </div>
            <div className="text-[10px] font-mono text-slate-500 pt-2 border-t border-white/[0.04] flex justify-between">
              <span>Duration: {riskState ? `${Math.round(riskState.state_duration_seconds)}s` : '0s'}</span>
              <span>Cycles: {riskState?.cycles_in_state || 1}</span>
            </div>
          </div>

          {/* Active Lookahead Alerts */}
          <div className="p-4 rounded-xl glass-card border border-white/[0.06] flex flex-col justify-between">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-mono text-slate-400 uppercase">Pre-Attack Alerts</span>
              <span className={`text-[10px] px-2.5 py-0.5 rounded-full font-mono font-bold border ${
                timeline?.is_alert_active_any_horizon
                  ? 'bg-rose-500/20 text-rose-300 border-rose-500/40'
                  : 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
              }`}>
                {timeline?.is_alert_active_any_horizon ? 'ALERTS ACTIVE' : 'NO THREATS'}
              </span>
            </div>
            <div className="my-2">
              <span className="text-2xl font-bold font-mono text-cyan-400">
                {timeline?.earliest_warning_horizon_minutes ? `+${timeline.earliest_warning_horizon_minutes}m Horizon` : 'All Clear'}
              </span>
              <p className="text-[11px] text-slate-400 mt-1">
                {timeline?.max_risk_horizon_minutes
                  ? `Max threat probability at +${timeline.max_risk_horizon_minutes}m`
                  : 'All forward lookaheads within nominal range'}
              </p>
            </div>
            <div className="text-[10px] font-mono text-slate-500 pt-2 border-t border-white/[0.04] flex justify-between">
              <span>Anomaly Score: {timeline ? timeline.anomaly_score.toFixed(3) : '0.000'}</span>
              <span>Monotonic: {timeline?.temporal_consistency_valid ? 'YES' : 'WATCH'}</span>
            </div>
          </div>

          {/* Ingestion & Sensor Status */}
          <div className="p-4 rounded-xl glass-card border border-white/[0.06] flex flex-col justify-between">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-mono text-slate-400 uppercase">Telemetry Ingestion</span>
              <span className="text-[10px] px-2.5 py-0.5 rounded-full font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                STREAM ACTIVE
              </span>
            </div>
            <div className="my-2">
              <span className="text-2xl font-bold font-mono text-white">
                {telemetryStats ? telemetryStats.total_flows_last_hour.toLocaleString() : '0'} Flows
              </span>
              <p className="text-[11px] text-slate-400 mt-1">
                Mean rate: <span className="text-cyan-300 font-mono">{telemetryStats ? telemetryStats.mean_packet_rate.toFixed(1) : '0.0'} pkt/s</span>
              </p>
            </div>
            <div className="text-[10px] font-mono text-slate-500 pt-2 border-t border-white/[0.04] flex justify-between">
              <span>Active Sources: {telemetryStats?.active_sources || 1}</span>
              <span>Unique IPs: {telemetryStats?.unique_sources_count || 0}</span>
            </div>
          </div>
        </div>
      </div>

      {/* 2. Multi-Horizon Forecast Lookahead Cards */}
      <div className="glass-panel p-6 rounded-2xl border border-glass-border">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-5">
          <div className="flex items-center gap-2">
            <Timer className="w-4 h-4 text-cyan-400" />
            <h3 className="text-sm font-semibold text-slate-200 font-mono">
              Forward Lookahead Progression (+5m, +15m, +30m, +60m)
            </h3>
          </div>
          <button
            onClick={() => onNavigateTab('FORECASTING')}
            className="text-xs text-cyan-400 hover:text-cyan-300 font-mono flex items-center gap-1 transition-colors"
          >
            Open Full Workspace <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>

        {loading && !timeline ? (
          <ForecastCardSkeleton />
        ) : timeline?.horizons ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {timeline.horizons.map((h) => {
              const isAlert = h.binary_alert_decision;
              const probPct = (h.calibrated_probability * 100).toFixed(1);
              const threshPct = (h.decision_threshold * 100).toFixed(1);

              return (
                <div
                  key={h.horizon_minutes}
                  className={`p-4 rounded-xl transition-all ${
                    isAlert
                      ? 'glass-card border-rose-500/40 bg-rose-950/20 ring-1 ring-rose-500/30'
                      : 'glass-card border-white/[0.07]'
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-mono font-bold text-slate-200 flex items-center gap-1.5">
                      <span className={`w-2 h-2 rounded-full ${isAlert ? 'bg-rose-400 animate-pulse' : 'bg-cyan-400'}`} />
                      +{h.horizon_minutes}m Lookahead
                    </span>
                    <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full border ${
                      isAlert ? 'bg-rose-500/20 text-rose-300 border-rose-500/40 font-bold' : 'bg-slate-900/80 text-slate-400 border-white/[0.06]'
                    }`}>
                      {isAlert ? 'ALERT' : 'NOMINAL'}
                    </span>
                  </div>

                  <div className="text-[11px] font-mono text-slate-400 mb-3">
                    Target: <span className="text-slate-200 font-medium">{new Date(h.target_timestamp).toLocaleTimeString()}</span>
                  </div>

                  <div className="space-y-1.5 mb-3">
                    <div className="flex justify-between text-xs font-mono">
                      <span className="text-slate-400">Threat Probability:</span>
                      <span className={`font-bold ${isAlert ? 'text-rose-400' : 'text-slate-100'}`}>{probPct}%</span>
                    </div>
                    <div className="w-full bg-slate-900 h-1.5 rounded-full overflow-hidden border border-white/[0.04]">
                      <div
                        className={`h-full transition-all duration-500 rounded-full ${isAlert ? 'bg-rose-500' : 'bg-cyan-400'}`}
                        style={{ width: `${Math.min(100, Math.max(0, Number(probPct)))}%` }}
                      />
                    </div>
                  </div>

                  <div className="flex items-center justify-between text-[10px] font-mono text-slate-400 pt-2.5 border-t border-white/[0.06]">
                    <span>Threshold: {threshPct}%</span>
                    <span>Conformal Set: {h.conformal_prediction_set.join(', ')}</span>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <EmptyState
            icon={Timer}
            title="Awaiting Telemetry Stream"
            description="Multi-horizon lookahead estimates will appear as soon as network flow windows are ingested."
            actionLabel="Ingest PCAP File"
            onAction={() => onNavigateTab('TELEMETRY')}
          />
        )}
      </div>

      {/* 3. Quick Action Hubs */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div 
          onClick={() => onNavigateTab('WHATIF')}
          className="glass-card p-5 rounded-2xl border border-glass-border hover:border-cyan-400/40 cursor-pointer transition-all flex items-center justify-between group"
        >
          <div className="flex items-center gap-3.5">
            <div className="p-3 rounded-xl bg-cyan-500/10 border border-cyan-400/30 text-cyan-400 group-hover:scale-105 transition-transform">
              <Sliders className="w-5 h-5" />
            </div>
            <div>
              <h4 className="text-sm font-bold text-white">What-If Lab</h4>
              <p className="text-xs text-slate-400">Perturb features & simulate shifts</p>
            </div>
          </div>
          <ArrowRight className="w-4 h-4 text-slate-500 group-hover:text-cyan-400 group-hover:translate-x-1 transition-all" />
        </div>

        <div 
          onClick={() => onNavigateTab('RISK')}
          className="glass-card p-5 rounded-2xl border border-glass-border hover:border-indigo-400/40 cursor-pointer transition-all flex items-center justify-between group"
        >
          <div className="flex items-center gap-3.5">
            <div className="p-3 rounded-xl bg-indigo-500/10 border border-indigo-400/30 text-indigo-400 group-hover:scale-105 transition-transform">
              <Workflow className="w-5 h-5" />
            </div>
            <div>
              <h4 className="text-sm font-bold text-white">Attack Path & Risk</h4>
              <p className="text-xs text-slate-400">Transition graph & hysteresis</p>
            </div>
          </div>
          <ArrowRight className="w-4 h-4 text-slate-500 group-hover:text-indigo-400 group-hover:translate-x-1 transition-all" />
        </div>

        <div 
          onClick={() => onNavigateTab('EXPLAINABILITY')}
          className="glass-card p-5 rounded-2xl border border-glass-border hover:border-emerald-400/40 cursor-pointer transition-all flex items-center justify-between group"
        >
          <div className="flex items-center gap-3.5">
            <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-400/30 text-emerald-400 group-hover:scale-105 transition-transform">
              <BrainCircuit className="w-5 h-5" />
            </div>
            <div>
              <h4 className="text-sm font-bold text-white">SHAP Attributions</h4>
              <p className="text-xs text-slate-400">Why the model made this forecast</p>
            </div>
          </div>
          <ArrowRight className="w-4 h-4 text-slate-500 group-hover:text-emerald-400 group-hover:translate-x-1 transition-all" />
        </div>
      </div>
    </div>
  );
}
