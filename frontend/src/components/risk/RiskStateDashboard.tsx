'use client';

import React, { useEffect, useState, useCallback, useRef } from 'react';
import { API_BASE_URL } from '@/lib/api/client';
import {
  ShieldAlert,
  ShieldCheck,
  AlertTriangle,
  GitCommit,
  ArrowRight,
  Clock,
  RefreshCw,
  Activity,
  Layers,
  Sparkles,
  Sliders,
  TrendingUp,
  Cpu,
  Info,
  CheckCircle2,
  Workflow,
  History,
  Shield,
  Zap,
} from 'lucide-react';

interface SupportingFeature {
  feature_name: string;
  observed_value: number;
  shap_value: number;
  unit?: string;
  description?: string;
}

interface AttackPathNode {
  stage: string;
  is_current: boolean;
  is_predicted: boolean;
  is_forecasted?: boolean;
  probability?: number | null;
  evidence_strength: string;
  status?: string;
  supporting_features: SupportingFeature[];
  timestamp?: string | null;
}

interface AttackPathEdge {
  source_stage: string;
  target_stage: string;
  transition_probability?: number | null;
  is_forecasted?: boolean;
  transition_horizon_minutes?: number | null;
  evidence_reasons: string[];
  uncertainty: string;
  status: string;
}

interface AttackPathForecast {
  forecast_id: string;
  forecast_timestamp: string;
  target_entity: string;
  current_stage?: string | null;
  predicted_next_stage?: string | null;
  subsequent_stages: string[];
  probability?: number | null;
  uncertainty: string;
  evidence: string[];
  supporting_features: SupportingFeature[];
  horizon_minutes?: number | null;
  target_timestamp?: string | null;
  transition_confidence_status: string;
  model_version: string;
  graph_nodes: AttackPathNode[];
  graph_edges: AttackPathEdge[];
}

interface RiskStateTransition {
  transition_id: string;
  timestamp: string;
  previous_state: string;
  new_state: string;
  triggering_evidence: string[];
  forecast_probability: number;
  anomaly_score: number;
  uncertainty: string;
  triggering_horizon?: number | null;
  reason: string;
  model_version: string;
}

interface RiskStateEvaluation {
  evaluation_id: string;
  timestamp: string;
  current_state: 'NORMAL' | 'WATCH' | 'SUSPICIOUS' | 'ELEVATED' | 'CRITICAL';
  previous_state: 'NORMAL' | 'WATCH' | 'SUSPICIOUS' | 'ELEVATED' | 'CRITICAL';
  state_duration_seconds: number;
  cycles_in_state: number;
  is_hysteresis_dampened: boolean;
  hysteresis_notes: string[];
  max_calibrated_probability: number;
  triggering_horizon_minutes?: number | null;
  active_alert_horizons: number[];
  anomaly_score: number;
  conformal_coverage_status: string;
  uncertainty_level: string;
  evidence_summary: string[];
  top_risk_features: SupportingFeature[];
  attack_path_summary?: AttackPathForecast | null;
  model_version: string;
}

interface RiskTimelineResponse {
  current_evaluation: RiskStateEvaluation;
  timeline_transitions: RiskStateTransition[];
  historical_evaluations: RiskStateEvaluation[];
}

const RISK_SUB_TABS = [
  { id: 'path', label: 'Attack Stage Graph', icon: Workflow },
  { id: 'state', label: 'Risk State & Hysteresis', icon: ShieldAlert },
  { id: 'audit', label: 'Transition Timeline', icon: History },
] as const;

type SubTabId = typeof RISK_SUB_TABS[number]['id'];

const STATE_CONFIG = {
  NORMAL: {
    color: 'emerald',
    badge: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
    border: 'border-emerald-500/40',
    glow: 'rgba(16, 185, 129, 0.15)',
    description: 'All telemetry features conform to verified nominal baseline distribution.',
  },
  WATCH: {
    color: 'cyan',
    badge: 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30',
    border: 'border-cyan-500/40',
    glow: 'rgba(6, 182, 212, 0.15)',
    description: 'Mild behavioral anomaly detected or early risk drift on longer lookahead horizons.',
  },
  SUSPICIOUS: {
    color: 'yellow',
    badge: 'bg-yellow-500/15 text-yellow-300 border-yellow-500/30',
    border: 'border-yellow-500/40',
    glow: 'rgba(234, 179, 8, 0.15)',
    description: 'Single horizon threshold breach or elevated anomaly score with conformal coverage uncertainty.',
  },
  ELEVATED: {
    color: 'amber',
    badge: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
    border: 'border-amber-500/40',
    glow: 'rgba(245, 158, 11, 0.20)',
    description: 'Multiple active multi-horizon alerts with high forward threat escalation trajectory.',
  },
  CRITICAL: {
    color: 'rose',
    badge: 'bg-rose-500/20 text-rose-300 border-rose-500/40 animate-pulse',
    border: 'border-rose-500/60',
    glow: 'rgba(244, 63, 94, 0.25)',
    description: 'Imminent verified multi-horizon attack progression requiring immediate mitigation.',
  },
};

export function RiskStateDashboard() {
  const [activeTab, setActiveTab] = useState<SubTabId>('path');
  const [evaluation, setEvaluation] = useState<RiskStateEvaluation | null>(null);
  const [timelineData, setTimelineData] = useState<RiskTimelineResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<AttackPathNode | null>(null);

  const subTabRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const subNavContainerRef = useRef<HTMLDivElement | null>(null);
  const [indicatorStyle, setIndicatorStyle] = useState<{
    transform: string;
    width: number;
    opacity: number;
  }>({
    transform: 'translate3d(0, 0, 0)',
    width: 0,
    opacity: 0,
  });

  const updateIndicator = useCallback(() => {
    const activeIdx = RISK_SUB_TABS.findIndex((t) => t.id === activeTab);
    const activeEl = subTabRefs.current[activeIdx];
    const containerEl = subNavContainerRef.current;
    if (activeEl && containerEl) {
      setIndicatorStyle({
        transform: `translate3d(${activeEl.offsetLeft}px, 0, 0)`,
        width: activeEl.offsetWidth,
        opacity: 1,
      });
    }
  }, [activeTab]);

  useEffect(() => {
    updateIndicator();
    const handleResize = () => updateIndicator();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [updateIndicator]);

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [stateRes, timelineRes] = await Promise.all([
        fetch(`${API_BASE_URL}/risk/state`),
        fetch(`${API_BASE_URL}/risk/timeline`),
      ]);

      if (stateRes.ok) {
        const sData = await stateRes.json();
        setEvaluation(sData);
      }
      if (timelineRes.ok) {
        const tData = await timelineRes.json();
        setTimelineData(tData);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to connect to Risk State Engine API');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const currentState = evaluation?.current_state || 'NORMAL';
  const stateMeta = STATE_CONFIG[currentState] || STATE_CONFIG.NORMAL;
  const attackPath = evaluation?.attack_path_summary;
  const isAwaitingTelemetry =
    evaluation?.conformal_coverage_status === 'AWAITING_TELEMETRY' ||
    attackPath?.transition_confidence_status === 'AWAITING_TELEMETRY';

  return (
    <div className="space-y-6">
      {/* Top Header Card */}
      <div className="glass-panel p-5 sm:p-6 rounded-2xl border border-glass-border flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="flex items-center gap-3.5">
          <div className="p-2.5 rounded-xl bg-gradient-to-br from-cyan-500/20 to-blue-600/10 border border-cyan-400/30 text-cyan-300 shadow-sm flex items-center justify-center">
            <Workflow className="w-5 h-5 text-cyan-400" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base sm:text-lg font-bold text-white tracking-tight">
                Attack Path Forecasting & Risk State Engine
              </h2>
              <span className={`text-[10px] px-2.5 py-0.5 rounded-full font-mono border ${stateMeta.badge}`}>
                {isAwaitingTelemetry ? 'AWAITING TELEMETRY' : `${currentState} STATE`}
              </span>
            </div>
            <p className="text-xs text-slate-400 font-normal mt-0.5">
              Evidence-Constrained Stage Transitions • Hysteresis-Dampened 5-Tier State Machine • Auditable Transitions
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3 w-full md:w-auto justify-between md:justify-end">
          {/* Continuous Liquid Glass Sub-Navigation Island */}
          <nav
            ref={subNavContainerRef}
            role="tablist"
            aria-label="Risk State Sub-views"
            className="liquid-nav-island w-full md:w-auto max-w-full overflow-x-auto no-scrollbar"
          >
            <div
              className="liquid-nav-indicator"
              style={{
                transform: indicatorStyle.transform,
                width: `${indicatorStyle.width}px`,
                opacity: indicatorStyle.opacity,
              }}
              aria-hidden="true"
            />

            {RISK_SUB_TABS.map((tab, idx) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  ref={(el) => {
                    subTabRefs.current[idx] = el;
                  }}
                  role="tab"
                  id={`risk-tab-${tab.id}`}
                  aria-selected={isActive}
                  aria-controls={`risk-panel-${tab.id}`}
                  tabIndex={isActive ? 0 : -1}
                  onClick={() => setActiveTab(tab.id)}
                  className={`liquid-nav-tab flex-1 whitespace-nowrap ${isActive ? 'is-active' : ''}`}
                >
                  <Icon className={`w-3.5 h-3.5 transition-colors duration-200 ${isActive ? 'text-cyan-400' : 'text-slate-500'}`} />
                  <span>{tab.label}</span>
                </button>
              );
            })}
          </nav>

          <button
            onClick={fetchData}
            disabled={loading}
            className="p-2 rounded-xl glass-button text-slate-300 hover:text-cyan-300 transition-all flex items-center justify-center shrink-0"
            title="Refresh Risk Data"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-cyan-400' : ''}`} />
          </button>
        </div>
      </div>

      {/* Hero Risk State Banner */}
      <div className="glass-panel p-5 sm:p-6 rounded-2xl border border-glass-border relative overflow-hidden">
        <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-6 pb-5 border-b border-white/[0.06]">
          <div className="space-y-2">
            <div className="flex items-center gap-3 flex-wrap">
              <span className="text-xs font-mono text-slate-400 uppercase">System Security State:</span>
              <span className={`px-3 py-1 rounded-full text-xs font-bold font-mono tracking-wide border ${stateMeta.badge}`}>
                ● {isAwaitingTelemetry ? 'AWAITING TELEMETRY' : currentState}
              </span>
              {evaluation?.is_hysteresis_dampened && (
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-amber-950/70 text-amber-300 border border-amber-700/40">
                  Hysteresis Active
                </span>
              )}
            </div>
            <p className="text-sm text-slate-300 max-w-2xl leading-relaxed">
              {isAwaitingTelemetry
                ? 'Awaiting validated telemetry stream. Ingest network flows or PCAP data to evaluate live risk.'
                : evaluation?.evidence_summary?.[0] || stateMeta.description}
            </p>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 w-full lg:w-auto font-mono text-xs">
            <div className="p-3 rounded-xl bg-slate-900/60 border border-white/[0.06] text-center">
              <span className="text-[10px] text-slate-400 block mb-0.5">Persistence</span>
              <span className="text-base font-bold text-white">
                Cycle {evaluation?.cycles_in_state ?? 1}
              </span>
            </div>
            <div className="p-3 rounded-xl bg-slate-900/60 border border-white/[0.06] text-center">
              <span className="text-[10px] text-slate-400 block mb-0.5">Max Cal. Risk</span>
              <span className={`text-base font-bold ${currentState === 'CRITICAL' || currentState === 'ELEVATED' ? 'text-rose-400' : 'text-cyan-300'}`}>
                {evaluation ? `${(evaluation.max_calibrated_probability * 100).toFixed(1)}%` : '--'}
              </span>
            </div>
            <div className="p-3 rounded-xl bg-slate-900/60 border border-white/[0.06] text-center">
              <span className="text-[10px] text-slate-400 block mb-0.5">Anomaly Score</span>
              <span className="text-base font-bold text-emerald-300">
                {evaluation ? evaluation.anomaly_score.toFixed(3) : '--'}
              </span>
            </div>
            <div className="p-3 rounded-xl bg-slate-900/60 border border-white/[0.06] text-center">
              <span className="text-[10px] text-slate-400 block mb-0.5">Active Alerts</span>
              <span className="text-base font-bold text-indigo-300">
                {evaluation?.active_alert_horizons?.length ? `${evaluation.active_alert_horizons.length} Horizons` : '0 Active'}
              </span>
            </div>
          </div>
        </div>

        {/* 5-Stage State Progression Track */}
        <div className="mt-5 grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-2 text-center text-xs font-mono">
          {(['NORMAL', 'WATCH', 'SUSPICIOUS', 'ELEVATED', 'CRITICAL'] as const).map((st) => {
            const isCurrent = currentState === st;
            const meta = STATE_CONFIG[st];
            return (
              <div
                key={st}
                className={`p-2.5 rounded-xl border transition-all ${
                  isCurrent
                    ? `${meta.badge} ring-1 ring-white/20 shadow-glass-card font-bold`
                    : 'bg-slate-900/30 border-white/[0.04] text-slate-500'
                }`}
              >
                <div className="flex items-center justify-center gap-1.5">
                  <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${isCurrent ? 'bg-current' : 'bg-slate-600'}`} />
                  <span className="text-[11px] truncate font-medium">{st}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* VIEW 1: ATTACK STAGE TRANSITION GRAPH */}
      {activeTab === 'path' && (
        <div className="space-y-6 animate-tab-content">
          <div className="glass-panel p-5 sm:p-6 rounded-2xl border border-glass-border space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-white/[0.06]">
              <div className="flex items-center gap-2">
                <Workflow className="w-5 h-5 text-cyan-400" />
                <div>
                  <h3 className="text-base font-bold text-white tracking-tight">
                    Directed Attack Stage Transition Graph
                  </h3>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Separates statistically supported forecast probabilities from domain graph taxonomy.
                  </p>
                </div>
              </div>
              <span className={`text-xs px-3 py-1 rounded-full font-mono border self-start sm:self-auto ${
                attackPath?.transition_confidence_status === 'VALIDATED_TRANSITION'
                  ? 'bg-emerald-950/70 text-emerald-300 border-emerald-800/60'
                  : attackPath?.transition_confidence_status === 'AWAITING_TELEMETRY'
                  ? 'bg-cyan-950/70 text-cyan-300 border-cyan-800/60'
                  : 'bg-slate-900/80 text-slate-400 border-white/[0.06]'
              }`}>
                {attackPath?.transition_confidence_status || 'INSUFFICIENT_EVIDENCE'}
              </span>
            </div>

            {/* Visual Node & Edge Graph */}
            <div className="p-6 rounded-xl bg-slate-950/40 border border-white/[0.06] overflow-x-auto">
              <div className="min-w-[650px] flex items-center justify-between gap-4 relative py-4">
                {isAwaitingTelemetry ? (
                  <div className="w-full text-center py-8 text-slate-400 text-xs font-mono">
                    Awaiting validated telemetry stream. Ingest network flows to view live attack stage graph.
                  </div>
                ) : attackPath?.graph_nodes && attackPath.graph_nodes.length > 0 ? (
                  attackPath.graph_nodes.map((node, idx) => {
                    const edge = attackPath.graph_edges.find((e) => e.source_stage === node.stage);
                    const isSelected = selectedNode?.stage === node.stage;
                    const isObserved = node.is_current;
                    const isForecasted = node.is_forecasted || (node.is_predicted && node.probability !== null && node.probability !== undefined);
                    
                    return (
                      <React.Fragment key={node.stage}>
                        {/* Node Card */}
                        <div
                          onClick={() => setSelectedNode(node)}
                          className={`p-4 rounded-xl glass-card border transition-all cursor-pointer flex-1 max-w-[220px] ${
                            isObserved
                              ? 'border-cyan-400/80 bg-cyan-950/20 ring-1 ring-cyan-400/30'
                              : isForecasted
                              ? 'border-amber-400/80 bg-amber-950/20 ring-1 ring-amber-400/30'
                              : 'border-white/[0.06] hover:border-white/[0.14] opacity-75'
                          } ${isSelected ? 'scale-[1.02] shadow-glass-elevated' : ''}`}
                        >
                          <div className="flex items-center justify-between mb-2">
                            <span className={`text-[10px] uppercase font-mono px-2 py-0.5 rounded-full border ${
                              isObserved
                                ? 'bg-cyan-950 text-cyan-300 border-cyan-700/50'
                                : isForecasted
                                ? 'bg-amber-950 text-amber-300 border-amber-700/50'
                                : 'bg-slate-900 text-slate-400 border-white/[0.06]'
                            }`}>
                              {isObserved ? 'Observed' : isForecasted ? 'Predicted' : 'Graph Possible'}
                            </span>
                            <span className="text-[10px] font-mono text-cyan-300 font-bold">
                              {node.probability !== null && node.probability !== undefined
                                ? `${(node.probability * 100).toFixed(0)}%`
                                : '--'}
                            </span>
                          </div>
                          <h4 className="text-sm font-bold text-white font-mono mt-1">{node.stage}</h4>
                          <span className="text-[10px] text-slate-400 block mt-1">
                            Status: <strong className="text-slate-200">
                              {isForecasted ? 'Forecasted (P ≥ 0.25)' : isObserved ? 'Active Telemetry' : 'Unvalidated Graph Topology'}
                            </strong>
                          </span>
                        </div>

                        {/* Edge Connector */}
                        {edge && idx < attackPath.graph_nodes.length - 1 && (
                          <div className="flex flex-col items-center justify-center shrink-0 px-2 text-center">
                            <span className="text-[10px] font-mono font-bold">
                              {edge.transition_probability !== null && edge.transition_probability !== undefined ? (
                                <span className="text-cyan-400">+{(edge.transition_probability * 100).toFixed(1)}%</span>
                              ) : (
                                <span className="text-slate-500 font-normal">Graph Path</span>
                              )}
                            </span>
                            <div className="flex items-center gap-1 my-1">
                              <div className={`w-10 sm:w-16 h-[2px] ${
                                edge.is_forecasted
                                  ? 'bg-gradient-to-r from-cyan-500/80 to-amber-500/80 animate-pulse'
                                  : 'bg-slate-700/50 border-t border-dashed border-slate-600'
                              }`} />
                              <ArrowRight className={`w-3.5 h-3.5 -ml-1 ${edge.is_forecasted ? 'text-amber-400' : 'text-slate-600'}`} />
                            </div>
                            <span className="text-[9px] font-mono text-slate-400">
                              {edge.transition_horizon_minutes ? `+${edge.transition_horizon_minutes}m` : 'Topology'}
                            </span>
                          </div>
                        )}
                      </React.Fragment>
                    );
                  })
                ) : (
                  <div className="w-full text-center py-8 text-slate-400 text-xs font-mono">
                    Insufficient evidence for next-stage forecast (telemetry within baseline nominal distribution).
                  </div>
                )}
              </div>
            </div>

            {/* Evidence & Supporting Features Detail */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Evidence Log */}
              <div className="p-4 rounded-xl bg-slate-900/40 border border-white/[0.06] space-y-3 font-mono text-xs">
                <h4 className="font-semibold text-slate-200 flex items-center gap-2">
                  <ShieldCheck className="w-4 h-4 text-cyan-400" />
                  Evidence & Rationales Log
                </h4>
                <ul className="space-y-2">
                  {attackPath?.evidence && attackPath.evidence.length > 0 ? (
                    attackPath.evidence.map((ev, i) => (
                      <li key={i} className="flex items-start gap-2 text-slate-300 text-[11px] leading-relaxed">
                        <span className="text-cyan-400 mt-0.5">•</span>
                        <span>{ev}</span>
                      </li>
                    ))
                  ) : (
                    <li className="text-slate-500 text-[11px]">No active threat evidence recorded.</li>
                  )}
                </ul>
              </div>

              {/* Supporting Telemetry Drivers */}
              <div className="p-4 rounded-xl bg-slate-900/40 border border-white/[0.06] space-y-3 font-mono text-xs">
                <h4 className="font-semibold text-slate-200 flex items-center gap-2">
                  <Sliders className="w-4 h-4 text-cyan-400" />
                  Supporting Telemetry Drivers (SHAP)
                </h4>
                <div className="space-y-2">
                  {attackPath?.supporting_features && attackPath.supporting_features.length > 0 ? (
                    attackPath.supporting_features.slice(0, 4).map((feat, i) => (
                      <div
                        key={i}
                        className="p-2.5 rounded-lg bg-slate-950/50 border border-white/[0.04] flex items-center justify-between text-xs"
                      >
                        <span className="text-slate-300 font-medium">{feat.feature_name}</span>
                        <div className="flex items-center gap-3">
                          <span className="text-slate-400 text-[11px]">{feat.observed_value} {feat.unit || ''}</span>
                          <span className="text-rose-400 font-bold">+{feat.shap_value.toFixed(4)}</span>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="text-slate-500 text-[11px]">Baseline telemetry features within normal bounds.</div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* VIEW 2: RISK STATE & HYSTERESIS CONTROLS */}
      {activeTab === 'state' && evaluation && (
        <div className="space-y-6 animate-tab-content">
          <div className="glass-panel p-5 sm:p-6 rounded-2xl border border-glass-border space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-white/[0.06]">
              <div className="flex items-center gap-2">
                <ShieldAlert className="w-5 h-5 text-cyan-400" />
                <div>
                  <h3 className="text-base font-bold text-white tracking-tight">
                    Risk State Machine & Hysteresis Dampening Details
                  </h3>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Anti-flutter state persistence prevents rapid oscillation between alert states.
                  </p>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 font-mono text-xs">
              <div className="p-4 rounded-xl bg-slate-900/40 border border-white/[0.06] space-y-3">
                <h4 className="font-semibold text-slate-200">State Transition Parameters</h4>
                <div className="space-y-2 text-slate-400">
                  <div className="flex justify-between">
                    <span>Current Active State:</span>
                    <span className="text-white font-bold">{evaluation.current_state}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Previous State:</span>
                    <span className="text-slate-300">{evaluation.previous_state}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>State Duration:</span>
                    <span className="text-slate-300">{evaluation.state_duration_seconds}s</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Cycles in State:</span>
                    <span className="text-cyan-300 font-bold">{evaluation.cycles_in_state}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Hysteresis Dampening:</span>
                    <span className={evaluation.is_hysteresis_dampened ? 'text-amber-400 font-bold' : 'text-emerald-400'}>
                      {evaluation.is_hysteresis_dampened ? 'ACTIVE' : 'INACTIVE'}
                    </span>
                  </div>
                </div>
              </div>

              <div className="p-4 rounded-xl bg-slate-900/40 border border-white/[0.06] space-y-3">
                <h4 className="font-semibold text-slate-200">Evaluation Notes</h4>
                <ul className="space-y-1.5 text-[11px] text-slate-300">
                  {evaluation.hysteresis_notes.map((note, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <span className="text-cyan-400 mt-0.5">•</span>
                      <span>{note}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* VIEW 3: TRANSITION TIMELINE AUDIT */}
      {activeTab === 'audit' && (
        <div className="space-y-6 animate-tab-content">
          <div className="glass-panel p-5 sm:p-6 rounded-2xl border border-glass-border space-y-4">
            <div className="flex items-center gap-2 pb-3 border-b border-white/[0.06]">
              <History className="w-5 h-5 text-cyan-400" />
              <div>
                <h3 className="text-base font-bold text-white tracking-tight">
                  Auditable Risk State Transition Log
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Chronological record of escalations, de-escalations, and triggering evidence.
                </p>
              </div>
            </div>

            <div className="space-y-3">
              {timelineData?.timeline_transitions && timelineData.timeline_transitions.length > 0 ? (
                timelineData.timeline_transitions.map((t) => (
                  <div
                    key={t.transition_id}
                    className="p-4 rounded-xl bg-slate-900/40 border border-white/[0.06] space-y-2 text-xs font-mono"
                  >
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] px-2 py-0.5 rounded bg-slate-800 text-slate-400">
                          {t.previous_state}
                        </span>
                        <ArrowRight className="w-3.5 h-3.5 text-slate-500" />
                        <span className={`text-[10px] px-2 py-0.5 rounded font-bold ${
                          STATE_CONFIG[t.new_state as keyof typeof STATE_CONFIG]?.badge || 'bg-slate-800 text-white'
                        }`}>
                          {t.new_state}
                        </span>
                      </div>
                      <span className="text-[10px] text-slate-500">
                        {new Date(t.timestamp).toLocaleTimeString()}
                      </span>
                    </div>
                    <p className="text-slate-300 text-[11px] leading-relaxed">{t.reason}</p>
                    <div className="flex items-center gap-4 text-[10px] text-slate-400 pt-1 border-t border-white/[0.04]">
                      <span>Prob: {(t.forecast_probability * 100).toFixed(1)}%</span>
                      <span>Anomaly: {t.anomaly_score.toFixed(3)}</span>
                      <span>Horizon: {t.triggering_horizon ? `+${t.triggering_horizon}m` : 'Multi'}</span>
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-center py-8 text-slate-400 text-xs font-mono">
                  No state transitions recorded yet. System initialized on baseline nominal distribution.
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
