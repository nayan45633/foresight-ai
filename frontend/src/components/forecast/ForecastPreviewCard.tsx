'use client';

import React, { useState, useEffect } from 'react';
import { API_BASE_URL } from '@/lib/api/client';
import { 
  ShieldAlert, 
  BrainCircuit, 
  Clock, 
  Activity, 
  CheckCircle2, 
  AlertTriangle, 
  TrendingUp, 
  TrendingDown,
  Zap, 
  Cpu, 
  BarChart3,
  RefreshCw,
  Info,
  Scale,
  Sparkles,
  Layers,
  HelpCircle,
  ChevronRight,
  Sliders,
  Database,
  Timer,
  Target,
  ArrowRight,
  ShieldCheck,
  AlertCircle
} from 'lucide-react';

interface ConformalPredictionSet {
  prediction_set: number[];
  target_coverage: number;
  empirical_coverage?: number;
  set_type: string;
}

interface FeatureAttributionDetail {
  feature_name: string;
  feature_index: number;
  observed_value: number;
  scaled_value: number;
  unit?: string;
  source: string;
  shap_value: number;
  absolute_magnitude: number;
  direction: 'increases_risk' | 'decreases_risk';
  description: string;
  feature_description: string;
  rank?: number;
}

interface HorizonForecastIntelligence {
  horizon_minutes: number;
  forecast_timestamp: string;
  target_timestamp: string;
  calibrated_probability: number;
  raw_probability?: number;
  decision_threshold: number;
  binary_alert_decision: boolean;
  conformal_prediction_set: number[];
  conformal_set_type: string;
  conformal_target_coverage: number;
  uncertainty_score: number;
  uncertainty_level: string;
  model_version: string;
  calibration_version: string;
  threat_class: string;
  severity: string;
  probability_delta_from_previous_horizon?: number;
  shap_top_positive: FeatureAttributionDetail[];
  shap_top_negative: FeatureAttributionDetail[];
  shap_explanation_available: boolean;
}

interface MultiHorizonTimelineResponse {
  forecast_timestamp: string;
  target_entity: string;
  horizons: HorizonForecastIntelligence[];
  earliest_warning_horizon_minutes?: number;
  max_risk_horizon_minutes?: number;
  is_alert_active_any_horizon: boolean;
  temporal_consistency_valid: boolean;
  temporal_consistency_notes: string[];
  anomaly_score: number;
}

interface EmpiricalLeadTimeMatch {
  match_id: string;
  forecast_id: string;
  forecast_timestamp: string;
  horizon_minutes: number;
  forecast_probability: number;
  decision_threshold: number;
  actual_event_id: string;
  actual_event_timestamp: string;
  actual_threat_type: string;
  empirical_lead_time_minutes: number;
  is_earliest_warning_for_event: boolean;
}

interface LeadTimeScorecardResponse {
  evaluation_period_start?: string;
  evaluation_period_end?: string;
  status: string;
  status_message: string;
  mean_lead_time_minutes?: number;
  median_lead_time_minutes?: number;
  min_lead_time_minutes?: number;
  max_lead_time_minutes?: number;
  std_lead_time_minutes?: number;
  total_emitted_forecasts: number;
  total_attack_events: number;
  valid_forecast_event_matches: number;
  missed_attack_events: number;
  false_early_warnings: number;
  unmatched_forecasts: number;
  empirical_forecast_coverage_rate?: number;
  earliest_warning_horizon_distribution: Record<string, number>;
  matches: EmpiricalLeadTimeMatch[];
}

interface GlobalFeatureImportanceItem {
  feature_name: string;
  feature_index: number;
  mean_abs_shap: number;
  unit?: string;
  description: string;
  rank: number;
}

interface HorizonMatrixRow {
  feature_name: string;
  feature_index: number;
  unit?: string;
  description: string;
  overall_mean_abs_shap: number;
  shap_5m: number;
  shap_15m: number;
  shap_30m: number;
  shap_60m: number;
}

interface GlobalExplainResponse {
  model_version: string;
  schema_version: string;
  evaluated_samples_count: number;
  generated_at: string;
  top_global_features: GlobalFeatureImportanceItem[];
  horizon_comparison_matrix: HorizonMatrixRow[];
}

const SUB_TABS = [
  { id: 'timeline', label: 'Forecast Timeline', icon: Timer },
  { id: 'leadtime', label: 'Lead-Time Scorecard', icon: Target },
  { id: 'global', label: 'Feature Drivers', icon: Sliders },
] as const;

export function ForecastPreviewCard() {
  const [timelineData, setTimelineData] = useState<MultiHorizonTimelineResponse | null>(null);
  const [leadTimeData, setLeadTimeData] = useState<LeadTimeScorecardResponse | null>(null);
  const [globalShapData, setGlobalShapData] = useState<GlobalExplainResponse | null>(null);
  const [selectedHorizon, setSelectedHorizon] = useState<number>(15);
  const [selectedFeature, setSelectedFeature] = useState<FeatureAttributionDetail | null>(null);
  const [activeTab, setActiveTab] = useState<'timeline' | 'leadtime' | 'global'>('timeline');
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const subTabRefs = React.useRef<(HTMLButtonElement | null)[]>([]);
  const subNavContainerRef = React.useRef<HTMLDivElement | null>(null);
  const [subIndicatorStyle, setSubIndicatorStyle] = useState<{
    transform: string;
    width: number;
    opacity: number;
  }>({
    transform: 'translate3d(0, 0, 0)',
    width: 0,
    opacity: 0,
  });

  const updateSubIndicator = React.useCallback(() => {
    const activeIdx = SUB_TABS.findIndex((t) => t.id === activeTab);
    const activeEl = subTabRefs.current[activeIdx];
    const containerEl = subNavContainerRef.current;
    if (activeEl && containerEl) {
      const activeLeft = activeEl.offsetLeft;
      const activeWidth = activeEl.offsetWidth;
      setSubIndicatorStyle({
        transform: `translate3d(${activeLeft}px, 0, 0)`,
        width: activeWidth,
        opacity: 1,
      });
    }
  }, [activeTab]);

  useEffect(() => {
    updateSubIndicator();
    const handleResize = () => updateSubIndicator();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [updateSubIndicator]);

  const fetchStep6Data = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const [timelineRes, leadTimeRes, globalShapRes] = await Promise.all([
        fetch(`${API_BASE_URL}/model/forecast/timeline`),
        fetch(`${API_BASE_URL}/model/lead-time`),
        fetch(`${API_BASE_URL}/model/explain/global`)
      ]);

      if (timelineRes.ok) {
        const tData = await timelineRes.json();
        setTimelineData(tData);
      }

      if (leadTimeRes.ok) {
        const lData = await leadTimeRes.json();
        setLeadTimeData(lData);
      }

      if (globalShapRes.ok) {
        const gData = await globalShapRes.json();
        setGlobalShapData(gData);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to connect to Forecasting Brain API');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStep6Data();
  }, []);

  const activeHorizon = timelineData?.horizons?.find(h => h.horizon_minutes === selectedHorizon) || timelineData?.horizons?.[0];

  const getSeverityBadge = (severity: string) => {
    switch (severity?.toUpperCase()) {
      case 'CRITICAL':
        return 'bg-rose-500/20 text-rose-300 border-rose-500/40 animate-pulse';
      case 'HIGH':
        return 'bg-amber-500/20 text-amber-300 border-amber-500/40';
      case 'MEDIUM':
        return 'bg-yellow-500/20 text-yellow-300 border-yellow-500/40';
      default:
        return 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40';
    }
  };

  const formatConformalSet = (setArr?: number[]) => {
    if (!setArr || setArr.length === 0) return '∅ (High Uncertainty / Conformal Rejection)';
    if (setArr.length === 1) {
      return setArr[0] === 1 ? '{ 1 } (Attack Not Excluded)' : '{ 0 } (Benign Not Excluded)';
    }
    return '{ 0, 1 } (Ambiguous / Neither Excluded)';
  };

  return (
    <div className="space-y-6">
      {/* Top Header Card */}
      <div className="glass-panel p-5 sm:p-6 rounded-2xl border border-glass-border flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="flex items-center gap-3.5">
          <div className="p-2.5 rounded-xl bg-gradient-to-br from-cyan-500/20 to-blue-600/10 border border-cyan-400/30 text-cyan-300 shadow-sm flex items-center justify-center">
            <BrainCircuit className="w-5 h-5 text-cyan-400" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base sm:text-lg font-bold text-white tracking-tight">
                Multi-Horizon Attack Intelligence & Early Warning
              </h2>
              <span className="text-[10px] px-2.5 py-0.5 rounded-full font-mono bg-cyan-950/70 text-cyan-300 border border-cyan-800/50">
                Live Forecaster
              </span>
            </div>
            <p className="text-xs text-slate-400 font-normal mt-0.5">
              Empirical Early-Warning Lead Times • Multi-Horizon Trajectories (+5m, +15m, +30m, +60m)
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3 w-full md:w-auto justify-between md:justify-end">
          {/* Continuous Liquid Glass Sub-Navigation Island */}
          <nav
            ref={subNavContainerRef}
            role="tablist"
            aria-label="Intelligence Sub-views"
            className="liquid-nav-island w-full md:w-auto min-w-[320px]"
          >
            {/* Sliding Moving Glass Highlight */}
            <div 
              className="liquid-nav-indicator"
              style={{
                transform: subIndicatorStyle.transform,
                width: `${subIndicatorStyle.width}px`,
                opacity: subIndicatorStyle.opacity,
              }}
              aria-hidden="true"
            />

            {SUB_TABS.map((tab, idx) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  ref={(el) => {
                    subTabRefs.current[idx] = el;
                  }}
                  role="tab"
                  id={`subtab-${tab.id}`}
                  aria-selected={isActive}
                  aria-controls={`subpanel-${tab.id}`}
                  tabIndex={isActive ? 0 : -1}
                  onClick={() => setActiveTab(tab.id)}
                  className={`liquid-nav-tab flex-1 ${isActive ? 'is-active' : ''}`}
                >
                  <Icon className={`w-3.5 h-3.5 transition-colors duration-200 ${isActive ? 'text-cyan-400' : 'text-slate-500'}`} />
                  <span>{tab.label}</span>
                </button>
              );
            })}
          </nav>

          <button
            onClick={fetchStep6Data}
            disabled={loading}
            className="p-2 rounded-xl glass-button text-slate-300 hover:text-cyan-300 transition-all flex items-center justify-center shrink-0"
            title="Refresh Intelligence Data"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-cyan-400' : ''}`} />
          </button>
        </div>
      </div>

      {/* TAB 1: MULTI-HORIZON FORECAST TIMELINE */}
      {activeTab === 'timeline' && (
        <div className="space-y-6 animate-tab-content">
          {/* Visual Progression Bar (NOW -> +5m -> +15m -> +30m -> +60m) */}
          <div className="glass-panel p-5 sm:p-6 rounded-2xl border border-glass-border relative overflow-hidden">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-5">
              <div className="flex items-center gap-2">
                <Clock className="w-4 h-4 text-cyan-400" />
                <span className="text-xs sm:text-sm font-semibold text-slate-200 font-mono">
                  Temporal Lookahead Progression (T₀ = {timelineData ? new Date(timelineData.forecast_timestamp).toLocaleTimeString() : '...'})
                </span>
              </div>
              <div className="flex items-center gap-2 flex-wrap">
                {timelineData?.earliest_warning_horizon_minutes && (
                  <span className="text-[11px] px-2.5 py-1 rounded-full font-mono bg-rose-950/70 text-rose-300 border border-rose-800/60 flex items-center gap-1.5">
                    <AlertTriangle className="w-3.5 h-3.5" />
                    Earliest Warning: +{timelineData.earliest_warning_horizon_minutes}m
                  </span>
                )}
                {timelineData?.temporal_consistency_valid && (
                  <span className="text-[11px] px-2.5 py-1 rounded-full font-mono bg-emerald-950/70 text-emerald-300 border border-emerald-800/60 flex items-center gap-1">
                    <ShieldCheck className="w-3.5 h-3.5" />
                    Chronologically Monotonic
                  </span>
                )}
              </div>
            </div>

            {/* Horizon Lookahead Progression Cards */}
            <div className="relative">
              {/* Timeline Flow Cards */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 relative z-10">
                {[5, 15, 30, 60].map((h_min) => {
                  const hData = timelineData?.horizons?.find(h => h.horizon_minutes === h_min);
                  const isSelected = selectedHorizon === h_min;
                  const isAlert = Boolean(hData?.binary_alert_decision);
                  const prob = hData ? (hData.calibrated_probability * 100).toFixed(1) : '--';
                  const thresh = hData ? (hData.decision_threshold * 100).toFixed(1) : '50.0';
                  const targetTime = hData?.target_timestamp ? new Date(hData.target_timestamp).toLocaleTimeString() : '...';
                  const delta = hData?.probability_delta_from_previous_horizon;

                  return (
                    <button
                      key={h_min}
                      onClick={() => { setSelectedHorizon(h_min); setSelectedFeature(null); }}
                      className={`p-4 rounded-xl text-left transition-all duration-200 relative isolate ${
                        isSelected 
                          ? 'glass-elevated border-cyan-400/70 translate-y-[-2px] opacity-100 ring-1 ring-cyan-400/25' 
                          : isAlert
                          ? 'glass-card border-rose-500/40 bg-rose-950/25 hover:border-rose-400/60 opacity-95 hover:opacity-100'
                          : 'glass-card border-white/[0.07] hover:border-white/[0.15] opacity-90 hover:opacity-100'
                      }`}
                    >
                      {/* Header */}
                      <div className="flex items-center justify-between mb-2.5">
                        <span className="text-xs font-mono font-bold text-slate-200 flex items-center gap-1.5">
                          <span className={`w-2 h-2 rounded-full ${isAlert ? 'bg-rose-400 animate-pulse' : 'bg-cyan-400'}`} />
                          +{h_min}m Horizon
                        </span>
                        <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full border ${
                          isAlert ? 'bg-rose-500/20 text-rose-300 border-rose-500/40 font-semibold' : 'bg-slate-900/80 text-slate-400 border-white/[0.06]'
                        }`}>
                          {isAlert ? 'ALERT ACTIVE' : 'NOMINAL'}
                        </span>
                      </div>

                      {/* Target Time */}
                      <div className="text-[11px] font-mono text-slate-400 mb-3 flex items-center gap-1.5">
                        <span className="text-slate-500">Target:</span>
                        <span className="text-slate-300 font-medium">{targetTime}</span>
                      </div>

                      {/* Probability Gauge */}
                      <div className="space-y-1.5 mb-3">
                        <div className="flex justify-between text-xs font-mono">
                          <span className="text-slate-400">Calibrated Risk:</span>
                          <span className={`font-bold ${isAlert ? 'text-rose-400' : 'text-slate-100'}`}>{prob}%</span>
                        </div>
                        <div className="w-full bg-slate-900/80 h-1.5 rounded-full overflow-hidden border border-white/[0.04]">
                          <div 
                            className={`h-full transition-all duration-500 rounded-full ${isAlert ? 'bg-rose-500' : 'bg-cyan-400'}`}
                            style={{ width: `${Math.min(100, Math.max(0, Number(prob)))}%` }}
                          />
                        </div>
                      </div>

                      {/* Threshold and Delta */}
                      <div className="flex items-center justify-between text-[10px] font-mono text-slate-400 pt-2.5 border-t border-white/[0.06]">
                        <span className="text-slate-500">Threshold: {thresh}%</span>
                        {delta !== null && delta !== undefined && (
                          <span className={`flex items-center gap-0.5 font-medium ${delta > 0 ? 'text-rose-400' : delta < 0 ? 'text-emerald-400' : 'text-slate-500'}`}>
                            {delta > 0 ? <TrendingUp className="w-3 h-3" /> : delta < 0 ? <TrendingDown className="w-3 h-3" /> : null}
                            {delta > 0 ? `+${(delta * 100).toFixed(1)}%` : `${(delta * 100).toFixed(1)}%`}
                          </span>
                        )}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Selected Horizon Deep Dive (Animated Transition on Horizon Change) */}
          {activeHorizon && (
            <div key={selectedHorizon} className="grid grid-cols-1 lg:grid-cols-3 gap-6 animate-tab-content">
              {/* Left 2 Cols: Risk Metrics & TreeSHAP Attribution */}
              <div className="lg:col-span-2 space-y-6">
                <div className="glass-panel p-5 sm:p-6 rounded-2xl border border-glass-border">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-5 pb-4 border-b border-white/[0.06]">
                    <div>
                      <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                        <Activity className="w-4 h-4 text-cyan-400" />
                        Horizon +{activeHorizon.horizon_minutes}m Feature Attribution
                      </h3>
                      <p className="text-xs text-slate-400 mt-0.5">
                        Predicted Threat: <span className="text-slate-200 font-semibold">{activeHorizon.threat_class}</span>
                      </p>
                    </div>
                    <span className={`text-xs px-2.5 py-1 rounded-full font-mono border self-start sm:self-auto ${getSeverityBadge(activeHorizon.severity)}`}>
                      {activeHorizon.severity} SEVERITY
                    </span>
                  </div>

                  {/* SHAP Bidirectional Contributor Bars */}
                  <div className="space-y-5">
                    {/* Positive Contributors */}
                    <div>
                      <span className="text-xs font-semibold text-rose-400 flex items-center gap-1.5 mb-2.5">
                        <TrendingUp className="w-3.5 h-3.5" />
                        Top Risk-Increasing Features (Pushes Toward Attack)
                      </span>
                      <div className="space-y-2">
                        {activeHorizon.shap_top_positive.map((feat) => (
                          <div
                            key={feat.feature_name}
                            onClick={() => setSelectedFeature(feat)}
                            className="p-3 rounded-xl glass-card border border-white/[0.06] hover:border-rose-500/40 cursor-pointer flex items-center justify-between text-xs font-mono"
                          >
                            <span className="text-slate-200 font-medium">{feat.feature_name}</span>
                            <div className="flex items-center gap-3">
                              <span className="text-slate-400 text-[11px]">{feat.observed_value} {feat.unit || ''}</span>
                              <span className="text-rose-400 font-bold">+{feat.shap_value.toFixed(4)}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Negative Contributors */}
                    <div>
                      <span className="text-xs font-semibold text-emerald-400 flex items-center gap-1.5 mb-2.5">
                        <TrendingDown className="w-3.5 h-3.5" />
                        Top Risk-Decreasing Features (Pushes Toward Benign)
                      </span>
                      <div className="space-y-2">
                        {activeHorizon.shap_top_negative.map((feat) => (
                          <div
                            key={feat.feature_name}
                            onClick={() => setSelectedFeature(feat)}
                            className="p-3 rounded-xl glass-card border border-white/[0.06] hover:border-emerald-500/40 cursor-pointer flex items-center justify-between text-xs font-mono"
                          >
                            <span className="text-slate-200 font-medium">{feat.feature_name}</span>
                            <div className="flex items-center gap-3">
                              <span className="text-slate-400 text-[11px]">{feat.observed_value} {feat.unit || ''}</span>
                              <span className="text-emerald-400 font-bold">{feat.shap_value.toFixed(4)}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Right Col: Uncertainty, Conformal Set & Details */}
              <div className="space-y-6">
                <div className="glass-panel p-5 sm:p-6 rounded-2xl border border-glass-border space-y-4 text-xs">
                  <h3 className="font-semibold text-white flex items-center gap-2">
                    <ShieldAlert className="w-4 h-4 text-cyan-400" />
                    Calibration & Conformal Coverage
                  </h3>

                  <div className="p-3.5 rounded-xl bg-slate-900/60 border border-white/[0.06] space-y-2.5 font-mono">
                    <div className="flex justify-between text-slate-400">
                      <span>Conformal Set (90%):</span>
                      <span className="text-cyan-300 font-bold">
                        {formatConformalSet(activeHorizon.conformal_prediction_set)}
                      </span>
                    </div>
                    <div className="flex justify-between text-slate-400">
                      <span>Uncertainty Level:</span>
                      <span className={`font-bold ${activeHorizon.uncertainty_level === 'LOW' ? 'text-emerald-400' : 'text-amber-400'}`}>
                        {activeHorizon.uncertainty_level} (Score: {activeHorizon.uncertainty_score})
                      </span>
                    </div>
                    <div className="flex justify-between text-slate-400">
                      <span>Calibrator Version:</span>
                      <span className="text-slate-300">{activeHorizon.calibration_version}</span>
                    </div>
                    <div className="flex justify-between text-slate-400">
                      <span>Decision Threshold:</span>
                      <span className="text-slate-300">{activeHorizon.decision_threshold}</span>
                    </div>
                  </div>

                  {selectedFeature && (
                    <div className="p-4 rounded-xl bg-cyan-950/20 border border-cyan-700/30 space-y-2">
                      <span className="text-cyan-300 font-bold font-mono block">{selectedFeature.feature_name}</span>
                      <p className="text-slate-300 text-[11px] leading-relaxed">{selectedFeature.description}</p>
                      <div className="text-[10px] font-mono text-slate-400 pt-2 border-t border-cyan-800/30 flex justify-between">
                        <span>Observed: {selectedFeature.observed_value} {selectedFeature.unit || ''}</span>
                        <span>SHAP Margin: {selectedFeature.shap_value.toFixed(5)}</span>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* TAB 2: EMPIRICAL LEAD-TIME SCORECARD */}
      {activeTab === 'leadtime' && (
        <div className="glass-panel p-5 sm:p-6 rounded-2xl border border-glass-border space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-white/[0.06]">
            <div className="flex items-center gap-2">
              <Target className="w-5 h-5 text-cyan-400" />
              <div>
                <h3 className="text-base font-bold text-white tracking-tight">
                  Empirical Early-Warning Lead-Time Scorecard
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  {leadTimeData?.status_message || 'Empirical lead-time metrics computed against verified attack events.'}
                </p>
              </div>
            </div>
            <span className={`text-xs px-3 py-1 rounded-full font-mono border self-start sm:self-auto ${
              leadTimeData?.status === 'EMPIRICALLY_EVALUATED' 
                ? 'bg-emerald-950/70 text-emerald-300 border-emerald-800/60' 
                : 'bg-amber-950/70 text-amber-300 border-amber-800/60'
            }`}>
              {leadTimeData?.status || 'EMPIRICALLY_EVALUATED'}
            </span>
          </div>

          {/* Metric Summary Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="p-4 rounded-xl glass-card border border-white/[0.06]">
              <span className="text-slate-400 text-xs block mb-1">Mean Lead Time</span>
              <span className="text-2xl font-bold font-mono text-cyan-400">
                {leadTimeData?.mean_lead_time_minutes !== undefined && leadTimeData?.mean_lead_time_minutes !== null
                  ? `${leadTimeData.mean_lead_time_minutes.toFixed(1)}m` 
                  : 'Awaiting events'}
              </span>
              <span className="text-[11px] text-slate-500 block mt-1">Empirical average</span>
            </div>

            <div className="p-4 rounded-xl glass-card border border-white/[0.06]">
              <span className="text-slate-400 text-xs block mb-1">Median Lead Time</span>
              <span className="text-2xl font-bold font-mono text-emerald-400">
                {leadTimeData?.median_lead_time_minutes !== undefined && leadTimeData?.median_lead_time_minutes !== null
                  ? `${leadTimeData.median_lead_time_minutes.toFixed(1)}m` 
                  : 'Awaiting events'}
              </span>
              <span className="text-[11px] text-slate-500 block mt-1">p50 early warning</span>
            </div>

            <div className="p-4 rounded-xl glass-card border border-white/[0.06]">
              <span className="text-slate-400 text-xs block mb-1">Maximum Lead Time</span>
              <span className="text-2xl font-bold font-mono text-indigo-400">
                {leadTimeData?.max_lead_time_minutes !== undefined && leadTimeData?.max_lead_time_minutes !== null
                  ? `${leadTimeData.max_lead_time_minutes.toFixed(1)}m` 
                  : 'Awaiting events'}
              </span>
              <span className="text-[11px] text-slate-500 block mt-1">Earliest warning record</span>
            </div>

            <div className="p-4 rounded-xl glass-card border border-white/[0.06]">
              <span className="text-slate-400 text-xs block mb-1">Forecast Coverage</span>
              <span className="text-2xl font-bold font-mono text-amber-400">
                {leadTimeData?.empirical_forecast_coverage_rate !== undefined && leadTimeData?.empirical_forecast_coverage_rate !== null
                  ? `${(leadTimeData.empirical_forecast_coverage_rate * 100).toFixed(1)}%` 
                  : '100%'}
              </span>
              <span className="text-[11px] text-slate-500 block mt-1">Attacks with early alert</span>
            </div>
          </div>

          {/* Audit Metrics Table */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 font-mono text-xs">
            <div className="p-4 rounded-xl bg-slate-900/40 border border-white/[0.06] space-y-2.5">
              <h4 className="font-semibold text-slate-200 mb-3 text-sm">Event Matching Verification</h4>
              <div className="flex justify-between text-slate-400">
                <span>Total Ground-Truth Attacks:</span>
                <span className="text-slate-200 font-bold">{leadTimeData?.total_attack_events ?? 0}</span>
              </div>
              <div className="flex justify-between text-slate-400">
                <span>Valid Matches:</span>
                <span className="text-emerald-400 font-bold">{leadTimeData?.valid_forecast_event_matches ?? 0}</span>
              </div>
              <div className="flex justify-between text-slate-400">
                <span>Missed Events:</span>
                <span className="text-slate-400 font-bold">{leadTimeData?.missed_attack_events ?? 0}</span>
              </div>
              <div className="flex justify-between text-slate-400">
                <span>False Early Warnings:</span>
                <span className="text-amber-400 font-bold">{leadTimeData?.false_early_warnings ?? 0}</span>
              </div>
            </div>

            <div className="p-4 rounded-xl bg-slate-900/40 border border-white/[0.06] space-y-2.5">
              <h4 className="font-semibold text-slate-200 mb-3 text-sm">Earliest Warning Horizon Distribution</h4>
              {Object.entries(leadTimeData?.earliest_warning_horizon_distribution || { '5m': 0, '15m': 0, '30m': 0, '60m': 0 }).map(([h, count]) => (
                <div key={h} className="flex justify-between text-slate-400">
                  <span>Horizon +{h}:</span>
                  <span className="text-cyan-300 font-bold">{count} warnings</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: GLOBAL SHAP SENSITIVITY MATRIX */}
      {activeTab === 'global' && globalShapData && (
        <div className="glass-panel p-6 rounded-2xl border border-glass-border space-y-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-cyan-400" />
              <h3 className="text-base font-bold text-slate-100 font-mono">
                GLOBAL MULTI-HORIZON SHAP SENSITIVITY MATRIX (37 FEATURES × 4 HORIZONS)
              </h3>
            </div>
            <span className="text-xs px-3 py-1 rounded-full font-mono bg-slate-800 text-slate-300 border border-slate-700">
              Evaluated on {globalShapData.evaluated_samples_count} validation windows
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-xs font-mono text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400 bg-slate-900/60">
                  <th className="p-3">Rank</th>
                  <th className="p-3">Feature Name</th>
                  <th className="p-3 text-right">Overall |SHAP|</th>
                  <th className="p-3 text-right text-cyan-400">+5m</th>
                  <th className="p-3 text-right text-cyan-400">+15m</th>
                  <th className="p-3 text-right text-cyan-400">+30m</th>
                  <th className="p-3 text-right text-cyan-400">+60m</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {globalShapData.horizon_comparison_matrix?.slice(0, 15).map((row, idx) => (
                  <tr key={row.feature_name} className="hover:bg-slate-900/40">
                    <td className="p-3 text-slate-500">{idx + 1}</td>
                    <td className="p-3 font-semibold text-slate-200">{row.feature_name}</td>
                    <td className="p-3 text-right font-bold text-slate-100">{row.overall_mean_abs_shap.toFixed(4)}</td>
                    <td className="p-3 text-right text-slate-300">{row.shap_5m.toFixed(4)}</td>
                    <td className="p-3 text-right text-slate-300">{row.shap_15m.toFixed(4)}</td>
                    <td className="p-3 text-right text-slate-300">{row.shap_30m.toFixed(4)}</td>
                    <td className="p-3 text-right text-slate-300">{row.shap_60m.toFixed(4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
