'use client';

import React, { useEffect, useState, useMemo, useCallback } from 'react';
import { API_BASE_URL } from '@/lib/api/client';
import {
  Sliders,
  Sparkles,
  RefreshCw,
  Play,
  ShieldAlert,
  ShieldCheck,
  ArrowRight,
  ArrowDown,
  ArrowUp,
  Info,
  Layers,
  RotateCcw,
  Search,
  Zap,
  Activity,
  CheckCircle2,
  AlertTriangle,
  History,
  TrendingDown,
  TrendingUp,
  SlidersHorizontal,
  ChevronRight,
  Check
} from 'lucide-react';

interface FeatureMetadata {
  index: number;
  name: string;
  display_name: string;
  datatype: string;
  unit: string | null;
  category: string;
  classification: 'DIRECTLY_PERTURBABLE' | 'DERIVED' | 'DEPENDENCY_CONSTRAINED' | string;
  min_value: number;
  max_value: number;
  default_value: number;
  slider_step: number;
  description: string;
  positive_risk_meaning: string;
  negative_risk_meaning: string;
}

interface CounterfactualPreset {
  preset_id: string;
  title: string;
  category: string;
  description: string;
  perturbations: Record<string, number>;
  recompute_derived: boolean;
  suggested_use_case: string;
}

interface AppliedPerturbation {
  feature_name: string;
  feature_index: number;
  original_value: number;
  perturbed_value: number;
  mode: string;
  delta: number;
  delta_percent: number | null;
  classification: string;
  unit: string | null;
  is_derived_auto_sync: boolean;
}

interface ShapDelta {
  feature_name: string;
  feature_index: number;
  baseline_shap: number;
  counterfactual_shap: number;
  delta_shap: number;
  direction: string;
  baseline_observed: number;
  counterfactual_observed: number;
  unit: string | null;
}

interface HorizonResult {
  horizon_minutes: number;
  baseline_probability: number;
  counterfactual_probability: number;
  probability_delta: number;
  baseline_alert: boolean;
  counterfactual_alert: boolean;
  decision_flip: 'ALERT_TO_NO_ALERT' | 'NO_ALERT_TO_ALERT' | 'NO_CHANGE' | string;
  decision_threshold: number;
  baseline_conformal_set: number[];
  counterfactual_conformal_set: number[];
  conformal_set_transition: string;
  baseline_uncertainty_score: number;
  counterfactual_uncertainty_score: number;
  baseline_uncertainty_level: string;
  counterfactual_uncertainty_level: string;
  shap_deltas: ShapDelta[];
  top_increased_risk_features: string[];
  top_decreased_risk_features: string[];
}

interface SimulationResponse {
  scenario_id: string;
  scenario_name: string;
  description?: string;
  timestamp: string;
  scientific_disclaimer: string;
  model_version: string;
  applied_perturbations: AppliedPerturbation[];
  horizon_results: Record<string, HorizonResult>;
  any_decision_flipped: boolean;
  max_risk_reduction: number;
  max_risk_elevation: number;
  execution_latency_ms: number;
  baseline_vector_summary: Record<string, number>;
  counterfactual_vector_summary: Record<string, number>;
}

const CATEGORY_NAMES: Record<string, string> = {
  volume: 'Traffic Volume & Rates',
  duration: 'Flow Duration & Variance',
  tcp_flags: 'TCP Handshake & Flags',
  entropy: 'Cardinality & Entropy',
  protocol: 'Protocol & Packet Dynamics',
  temporal_delta: 'Temporal Derivatives',
  anomaly: 'Behavioral Anomaly Model',
};

export function WhatIfLab() {
  const [catalog, setCatalog] = useState<{
    features: FeatureMetadata[];
    presets: CounterfactualPreset[];
    scientific_disclaimer: string;
  } | null>(null);

  const [loadingCatalog, setLoadingCatalog] = useState(true);
  const [evaluating, setEvaluating] = useState(false);
  const [activeCategory, setActiveCategory] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [recomputeDerived, setRecomputeDerived] = useState(true);
  const [includeShap, setIncludeShap] = useState(true);

  // Baseline values and active perturbations
  const [baselineValues, setBaselineValues] = useState<Record<string, number>>({});
  const [perturbations, setPerturbations] = useState<Record<string, number>>({});
  const [selectedPreset, setSelectedPreset] = useState<string | null>(null);

  // Simulation response & history
  const [currentResult, setCurrentResult] = useState<SimulationResponse | null>(null);
  const [history, setHistory] = useState<SimulationResponse[]>([]);
  const [selectedHorizonTab, setSelectedHorizonTab] = useState<string>('15');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // 1. Fetch feature catalog and presets
  useEffect(() => {
    async function loadCatalog() {
      try {
        setLoadingCatalog(true);
        const res = await fetch(`${API_BASE_URL}/model/counterfactual/features`);
        if (!res.ok) throw new Error('Failed to load feature catalog');
        const data = await res.json();
        setCatalog(data);

        // Initialize baseline values with defaults
        const baseMap: Record<string, number> = {};
        data.features.forEach((f: FeatureMetadata) => {
          baseMap[f.name] = f.default_value;
        });
        setBaselineValues(baseMap);

        // Run initial default simulation
        runInitialSimulation(baseMap);
      } catch (err: any) {
        setErrorMsg(err.message || 'Error connecting to counterfactual engine');
      } finally {
        setLoadingCatalog(false);
      }
    }
    loadCatalog();
  }, []);

  // Run initial simulation
  const runInitialSimulation = async (baseMap: Record<string, number>) => {
    try {
      const res = await fetch(`${API_BASE_URL}/model/counterfactual`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          scenario_name: 'Baseline Operational State',
          description: 'Initial nominal perimeter state',
          perturbations: { syn_count: baseMap['syn_count'] || 45.0 },
          recompute_derived: true,
          include_shap: true,
        }),
      });
      if (res.ok) {
        const data: SimulationResponse = await res.json();
        setCurrentResult(data);
        if (data.baseline_vector_summary) {
          setBaselineValues(data.baseline_vector_summary);
        }
      }
    } catch {
      // Standby fallback
    }
  };

  // Handle slider/input change
  const handleFeatureChange = (name: string, val: number) => {
    setSelectedPreset(null);
    setPerturbations((prev) => ({
      ...prev,
      [name]: val,
    }));
  };

  // Reset single feature
  const handleResetSingleFeature = (name: string) => {
    setPerturbations((prev) => {
      const copy = { ...prev };
      delete copy[name];
      return copy;
    });
  };

  // Reset all perturbations
  const handleResetAll = () => {
    setPerturbations({});
    setSelectedPreset(null);
    if (currentResult) {
      runSimulation({});
    }
  };

  // Load a preset
  const handleApplyPreset = (preset: CounterfactualPreset) => {
    setSelectedPreset(preset.preset_id);
    setPerturbations(preset.perturbations);
    setRecomputeDerived(preset.recompute_derived);
    runSimulation(preset.perturbations, preset.title, preset.description, preset.recompute_derived);
  };

  // Run full simulation
  const runSimulation = async (
    activePerturbs: Record<string, number> = perturbations,
    title?: string,
    desc?: string,
    autoRecompute: boolean = recomputeDerived
  ) => {
    try {
      setEvaluating(true);
      setErrorMsg(null);

      // If no perturbations active, supply trivial baseline probe
      const payloadPerturbs =
        Object.keys(activePerturbs).length > 0
          ? activePerturbs
          : { syn_count: baselineValues['syn_count'] || 45.0 };

      const payload = {
        scenario_name: title || (selectedPreset ? `Preset: ${selectedPreset}` : `Custom What-If (${Object.keys(activePerturbs).length} features)`),
        description: desc || 'Interactive operator model sensitivity simulation',
        perturbations: payloadPerturbs,
        recompute_derived: autoRecompute,
        include_shap: includeShap,
      };

      const res = await fetch(`${API_BASE_URL}/model/counterfactual`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || 'Counterfactual evaluation failed');
      }

      const data: SimulationResponse = await res.json();
      setCurrentResult(data);
      setHistory((prev) => [data, ...prev.slice(0, 9)]);
      if (data.baseline_vector_summary) {
        setBaselineValues(data.baseline_vector_summary);
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Simulation failed');
    } finally {
      setEvaluating(false);
    }
  };

  // Filtered feature list
  const filteredFeatures = useMemo(() => {
    if (!catalog) return [];
    return catalog.features.filter((f) => {
      const matchCat = activeCategory === 'all' || f.category === activeCategory;
      const matchQuery =
        !searchQuery ||
        f.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        f.display_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        f.description.toLowerCase().includes(searchQuery.toLowerCase());
      return matchCat && matchQuery;
    });
  }, [catalog, activeCategory, searchQuery]);

  const activePerturbationCount = Object.keys(perturbations).length;
  const currentHorizonResult = currentResult?.horizon_results[selectedHorizonTab];

  return (
    <div className="space-y-6">
      {/* 1. Header Banner & Scientific Disclaimer */}
      <div className="glass-panel p-6 sm:p-8 rounded-2xl border border-glass-border">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6 pb-6 border-b border-white/[0.06]">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-cyan-500/10 text-cyan-400 text-xs font-mono mb-3 border border-cyan-500/20">
              <Sliders className="w-3.5 h-3.5" /> Model Sensitivity & Counterfactual Engine
            </div>
            <h2 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
              Interactive What-If Scenario Lab
            </h2>
            <p className="mt-2 text-slate-300 text-sm max-w-3xl leading-relaxed">
              Perturb 37-dimensional network telemetry features and trigger real model re-inference across all forward horizons. Evaluate how rate limits, firewall rules, and traffic anomalies shift probability distributions, flip alert decisions, and transform TreeSHAP attributions.
            </p>
          </div>

          <div className="flex items-center gap-3 shrink-0">
            <button
              onClick={() => runSimulation()}
              disabled={evaluating}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-300 font-mono text-sm font-semibold border border-cyan-500/40 transition-all shadow-glow-cyan disabled:opacity-50"
            >
              <Play className={`w-4 h-4 ${evaluating ? 'animate-spin' : ''}`} />
              {evaluating ? 'Simulating...' : 'Run Simulation'}
            </button>
            <button
              onClick={handleResetAll}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-slate-800/80 hover:bg-slate-700 text-slate-300 font-mono text-sm border border-white/[0.08] transition-all"
            >
              <RotateCcw className="w-4 h-4" /> Reset
            </button>
          </div>
        </div>

        {/* Scientific Framing Alert */}
        <div className="mt-4 p-3.5 rounded-xl bg-slate-900/80 border border-cyan-500/20 flex items-start gap-3 text-xs text-slate-300">
          <Info className="w-4 h-4 text-cyan-400 shrink-0 mt-0.5" />
          <div>
            <strong className="text-cyan-300 font-semibold font-mono">SCIENTIFIC METHODOLOGY NOTE: </strong>
            <span>
              This simulation quantifies <em>model sensitivity</em> (ΔP = P<sub>counterfactual</sub> − P<sub>baseline</sub>) under frozen gradient boosted trees and Isotonic calibrators. It isolates how the model responds to specific feature shifts; it does not claim real-world physical causal counterfactuals.
            </span>
          </div>
        </div>

        {/* 2. Builtin Scenario Presets Quick-Bar */}
        <div className="mt-6">
          <span className="text-xs uppercase tracking-wider text-slate-400 font-mono mb-3 block flex items-center gap-2">
            <Zap className="w-3.5 h-3.5 text-amber-400" />
            Intervention & Stress-Testing Presets:
          </span>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-2.5">
            {catalog?.presets.map((preset) => {
              const isSelected = selectedPreset === preset.preset_id;
              const isMitigation = preset.category.includes('Mitigation');
              return (
                <button
                  key={preset.preset_id}
                  onClick={() => handleApplyPreset(preset)}
                  className={`p-3 rounded-xl border text-left transition-all ${
                    isSelected
                      ? 'bg-cyan-500/20 border-cyan-400/60 shadow-glow-cyan'
                      : 'bg-slate-900/60 hover:bg-slate-800/80 border-white/[0.06]'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span
                      className={`text-[10px] font-mono uppercase px-2 py-0.5 rounded-full ${
                        isMitigation ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-400'
                      }`}
                    >
                      {preset.category}
                    </span>
                    {isSelected && <Check className="w-3.5 h-3.5 text-cyan-400" />}
                  </div>
                  <h4 className="text-xs font-semibold text-slate-100 mt-2 line-clamp-1">{preset.title}</h4>
                  <p className="text-[11px] text-slate-400 mt-1 line-clamp-2 leading-tight">{preset.description}</p>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {errorMsg && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-3">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* 3. Main Dual-Column Simulation Workspace */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Feature Perturbation Controls (7 Cols) */}
        <div className="lg:col-span-7 space-y-4">
          <div className="glass-panel p-5 rounded-2xl border border-glass-border">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-white/[0.06]">
              <div className="flex items-center gap-2">
                <SlidersHorizontal className="w-4 h-4 text-cyan-400" />
                <h3 className="text-sm font-semibold text-slate-100">Telemetry Feature Adjuster</h3>
                <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-slate-800 text-cyan-400 border border-white/[0.06]">
                  {activePerturbationCount} Perturbed
                </span>
              </div>

              {/* Search Box */}
              <div className="relative">
                <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-2.5" />
                <input
                  type="text"
                  placeholder="Filter 37 features..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-8 pr-3 py-1.5 rounded-xl bg-slate-900/90 border border-white/[0.08] text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500/50 w-full sm:w-48 font-mono"
                />
              </div>
            </div>

            {/* Category Filter Pills */}
            <div className="flex items-center gap-1.5 overflow-x-auto py-3 no-scrollbar border-b border-white/[0.04]">
              <button
                onClick={() => setActiveCategory('all')}
                className={`px-3 py-1 rounded-lg text-xs font-mono transition-all shrink-0 ${
                  activeCategory === 'all'
                    ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
                    : 'bg-slate-900/60 text-slate-400 hover:text-slate-200'
                }`}
              >
                All (37)
              </button>
              {Object.entries(CATEGORY_NAMES).map(([catKey, catLabel]) => (
                <button
                  key={catKey}
                  onClick={() => setActiveCategory(catKey)}
                  className={`px-3 py-1 rounded-lg text-xs font-mono transition-all shrink-0 ${
                    activeCategory === catKey
                      ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
                      : 'bg-slate-900/60 text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {catLabel}
                </button>
              ))}
            </div>

            {/* Toggles */}
            <div className="flex items-center justify-between py-2 text-xs text-slate-400 border-b border-white/[0.04]">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={recomputeDerived}
                  onChange={(e) => setRecomputeDerived(e.target.checked)}
                  className="rounded border-slate-700 text-cyan-500 focus:ring-0 bg-slate-900"
                />
                <span>Auto-sync derived metrics (SYN/ACK ratio, PPS, BPS)</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={includeShap}
                  onChange={(e) => setIncludeShap(e.target.checked)}
                  className="rounded border-slate-700 text-cyan-500 focus:ring-0 bg-slate-900"
                />
                <span>Compute TreeSHAP attributions</span>
              </label>
            </div>

            {/* Feature Slider List */}
            <div className="divide-y divide-white/[0.04] max-h-[580px] overflow-y-auto pr-1">
              {loadingCatalog ? (
                <div className="py-12 text-center text-slate-400 font-mono text-xs animate-pulse">
                  Loading feature schemas...
                </div>
              ) : filteredFeatures.length === 0 ? (
                <div className="py-12 text-center text-slate-400 font-mono text-xs">
                  No matching features found.
                </div>
              ) : (
                filteredFeatures.map((feat) => {
                  const baseVal = baselineValues[feat.name] ?? feat.default_value;
                  const currentVal = perturbations[feat.name] ?? baseVal;
                  const isPerturbed = perturbations[feat.name] !== undefined;
                  const delta = currentVal - baseVal;
                  const deltaPct = baseVal !== 0 ? (delta / baseVal) * 100 : null;

                  return (
                    <div key={feat.name} className="py-3.5 space-y-2">
                      <div className="flex items-center justify-between text-xs">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-slate-200">{feat.display_name}</span>
                          <span className="text-[10px] font-mono text-slate-500">[{feat.unit || 'unitless'}]</span>
                          <span
                            className={`text-[9px] font-mono px-1.5 py-0.2 rounded ${
                              feat.classification === 'DIRECTLY_PERTURBABLE'
                                ? 'bg-cyan-500/10 text-cyan-400'
                                : feat.classification === 'DERIVED'
                                ? 'bg-purple-500/10 text-purple-400'
                                : 'bg-amber-500/10 text-amber-400'
                            }`}
                          >
                            {feat.classification === 'DIRECTLY_PERTURBABLE'
                              ? 'Direct'
                              : feat.classification === 'DERIVED'
                              ? 'Derived'
                              : 'Temporal'}
                          </span>
                        </div>

                        {/* Baseline vs Current & Delta */}
                        <div className="flex items-center gap-2 font-mono">
                          {isPerturbed && (
                            <>
                              <span
                                className={`text-[10px] px-1.5 py-0.5 rounded ${
                                  delta < 0
                                    ? 'bg-emerald-500/10 text-emerald-400'
                                    : delta > 0
                                    ? 'bg-rose-500/10 text-rose-400'
                                    : 'text-slate-400'
                                }`}
                              >
                                {delta > 0 ? '+' : ''}
                                {delta.toFixed(2)} {deltaPct !== null ? `(${deltaPct.toFixed(0)}%)` : ''}
                              </span>
                              <button
                                onClick={() => handleResetSingleFeature(feat.name)}
                                title="Reset to baseline"
                                className="text-slate-500 hover:text-slate-300"
                              >
                                <RotateCcw className="w-3 h-3" />
                              </button>
                            </>
                          )}
                          <span className="text-slate-400 text-[11px]">Base: {baseVal.toFixed(2)}</span>
                          <span className="text-cyan-300 font-bold text-xs min-w-[50px] text-right">
                            {currentVal.toFixed(2)}
                          </span>
                        </div>
                      </div>

                      {/* Slider and Range Bounds */}
                      <div className="flex items-center gap-3">
                        <span className="text-[10px] font-mono text-slate-500 min-w-[36px]">
                          {feat.min_value}
                        </span>
                        <input
                          type="range"
                          min={feat.min_value}
                          max={feat.max_value}
                          step={feat.slider_step}
                          value={currentVal}
                          onChange={(e) => handleFeatureChange(feat.name, parseFloat(e.target.value))}
                          className="flex-1 accent-cyan-400 bg-slate-800 h-1.5 rounded-lg cursor-pointer"
                        />
                        <span className="text-[10px] font-mono text-slate-500 min-w-[36px] text-right">
                          {feat.max_value}
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-400 leading-tight">{feat.description}</p>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>

        {/* Right Column: Comparative Multi-Horizon Results & TreeSHAP (5 Cols) */}
        <div className="lg:col-span-5 space-y-4">
          {/* Multi-Horizon Probability Diff Cards */}
          <div className="glass-panel p-5 rounded-2xl border border-glass-border space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-white/[0.06]">
              <div className="flex items-center gap-2">
                <Activity className="w-4 h-4 text-cyan-400" />
                <h3 className="text-sm font-semibold text-slate-100">Multi-Horizon Sensitivity</h3>
              </div>
              <span className="text-[11px] font-mono text-slate-400">
                Latency: <strong className="text-cyan-400">{currentResult?.execution_latency_ms ?? 0}ms</strong>
              </span>
            </div>

            {/* Horizon Selector Tabs */}
            <div className="grid grid-cols-4 gap-1.5 p-1 rounded-xl bg-slate-900/80 border border-white/[0.04]">
              {['5', '15', '30', '60'].map((hStr) => {
                const res = currentResult?.horizon_results[hStr];
                const isSelected = selectedHorizonTab === hStr;
                const isFlipped = res?.decision_flip !== 'NO_CHANGE';
                return (
                  <button
                    key={hStr}
                    onClick={() => setSelectedHorizonTab(hStr)}
                    className={`py-2 px-1 rounded-lg text-center transition-all ${
                      isSelected
                        ? 'bg-cyan-500/20 text-cyan-300 font-semibold border border-cyan-500/40 shadow-glow-cyan'
                        : 'text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    <div className="text-xs font-mono font-bold">+{hStr}m</div>
                    <div className="text-[10px] font-mono mt-0.5">
                      {res ? `${(res.counterfactual_probability * 100).toFixed(0)}%` : '--'}
                    </div>
                    {isFlipped && (
                      <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 mx-auto mt-1 animate-pulse" />
                    )}
                  </button>
                );
              })}
            </div>

            {/* Selected Horizon Detail Card */}
            {currentHorizonResult && (
              <div className="space-y-4 pt-2">
                {/* Decision Flip Banner */}
                <div
                  className={`p-3 rounded-xl border flex items-center justify-between ${
                    currentHorizonResult.decision_flip === 'ALERT_TO_NO_ALERT'
                      ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                      : currentHorizonResult.decision_flip === 'NO_ALERT_TO_ALERT'
                      ? 'bg-rose-500/10 border-rose-500/30 text-rose-300'
                      : 'bg-slate-900/60 border-white/[0.06] text-slate-300'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    {currentHorizonResult.decision_flip === 'ALERT_TO_NO_ALERT' ? (
                      <ShieldCheck className="w-4 h-4 text-emerald-400" />
                    ) : currentHorizonResult.decision_flip === 'NO_ALERT_TO_ALERT' ? (
                      <ShieldAlert className="w-4 h-4 text-rose-400" />
                    ) : (
                      <CheckCircle2 className="w-4 h-4 text-slate-400" />
                    )}
                    <div>
                      <div className="text-xs font-semibold font-mono">
                        {currentHorizonResult.decision_flip === 'ALERT_TO_NO_ALERT'
                          ? 'DECISION FLIP: ALERT CLEARED'
                          : currentHorizonResult.decision_flip === 'NO_ALERT_TO_ALERT'
                          ? 'DECISION FLIP: ALERT TRIGGERED'
                          : 'DECISION STATUS: NO CHANGE'}
                      </div>
                      <div className="text-[10px] text-slate-400 mt-0.5">
                        Cutoff Threshold: {(currentHorizonResult.decision_threshold * 100).toFixed(1)}%
                      </div>
                    </div>
                  </div>

                  {/* Conformal Set Shift */}
                  <div className="text-right font-mono text-xs">
                    <span className="text-[10px] text-slate-400 block">Conformal Set</span>
                    <span className="font-bold text-cyan-300">
                      {currentHorizonResult.conformal_set_transition}
                    </span>
                  </div>
                </div>

                {/* Probability Gauges (Baseline vs Counterfactual) */}
                <div className="grid grid-cols-2 gap-3">
                  {/* Baseline */}
                  <div className="p-3.5 rounded-xl bg-slate-900/70 border border-white/[0.06]">
                    <span className="text-[10px] font-mono text-slate-400 block uppercase">
                      Baseline Calibrated
                    </span>
                    <div className="text-xl font-bold font-mono text-slate-200 mt-1">
                      {(currentHorizonResult.baseline_probability * 100).toFixed(1)}%
                    </div>
                    <div className="w-full bg-slate-800 h-1.5 rounded-full mt-2 overflow-hidden">
                      <div
                        className="bg-slate-400 h-full rounded-full"
                        style={{ width: `${Math.min(100, currentHorizonResult.baseline_probability * 100)}%` }}
                      />
                    </div>
                    <span className="text-[10px] font-mono text-slate-500 mt-1.5 block">
                      Alert: {currentHorizonResult.baseline_alert ? 'YES' : 'NO'}
                    </span>
                  </div>

                  {/* Counterfactual */}
                  <div className="p-3.5 rounded-xl bg-slate-900/70 border border-cyan-500/20">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-mono text-cyan-400 block uppercase">
                        What-If Calibrated
                      </span>
                      <span
                        className={`text-[10px] font-mono font-bold flex items-center gap-0.5 ${
                          currentHorizonResult.probability_delta < 0
                            ? 'text-emerald-400'
                            : currentHorizonResult.probability_delta > 0
                            ? 'text-rose-400'
                            : 'text-slate-400'
                        }`}
                      >
                        {currentHorizonResult.probability_delta < 0 ? (
                          <TrendingDown className="w-3 h-3" />
                        ) : currentHorizonResult.probability_delta > 0 ? (
                          <TrendingUp className="w-3 h-3" />
                        ) : null}
                        {currentHorizonResult.probability_delta > 0 ? '+' : ''}
                        {(currentHorizonResult.probability_delta * 100).toFixed(1)}%
                      </span>
                    </div>
                    <div className="text-xl font-bold font-mono text-cyan-300 mt-1">
                      {(currentHorizonResult.counterfactual_probability * 100).toFixed(1)}%
                    </div>
                    <div className="w-full bg-slate-800 h-1.5 rounded-full mt-2 overflow-hidden">
                      <div
                        className={`h-full rounded-full ${
                          currentHorizonResult.probability_delta < 0 ? 'bg-emerald-400' : 'bg-cyan-400'
                        }`}
                        style={{
                          width: `${Math.min(100, currentHorizonResult.counterfactual_probability * 100)}%`,
                        }}
                      />
                    </div>
                    <span className="text-[10px] font-mono text-slate-400 mt-1.5 block">
                      Alert: {currentHorizonResult.counterfactual_alert ? 'YES' : 'NO'}
                    </span>
                  </div>
                </div>

                {/* TreeSHAP Attribution Differential List */}
                <div className="pt-2">
                  <h4 className="text-xs font-mono uppercase tracking-wider text-slate-400 mb-3 flex items-center justify-between">
                    <span className="flex items-center gap-1.5">
                      <Layers className="w-3.5 h-3.5 text-cyan-400" /> Top TreeSHAP Sensitivity Deltas (Δφ)
                    </span>
                    <span className="text-[10px] text-slate-500">Margin Shift</span>
                  </h4>

                  <div className="space-y-2">
                    {currentHorizonResult.shap_deltas.length === 0 ? (
                      <p className="text-xs text-slate-500 font-mono italic">
                        No significant feature attribution differential.
                      </p>
                    ) : (
                      currentHorizonResult.shap_deltas.slice(0, 5).map((item) => {
                        const isReduction = item.delta_shap < 0;
                        return (
                          <div
                            key={item.feature_name}
                            className="p-2.5 rounded-xl bg-slate-900/50 border border-white/[0.04] text-xs space-y-1"
                          >
                            <div className="flex items-center justify-between font-mono">
                              <span className="text-slate-200 font-semibold">{item.feature_name}</span>
                              <span
                                className={`font-bold ${
                                  isReduction ? 'text-emerald-400' : 'text-rose-400'
                                }`}
                              >
                                {item.delta_shap > 0 ? '+' : ''}
                                {item.delta_shap.toFixed(4)}
                              </span>
                            </div>
                            <div className="flex items-center justify-between text-[10px] text-slate-400 font-mono">
                              <span>
                                {item.baseline_observed.toFixed(1)} → {item.counterfactual_observed.toFixed(1)}{' '}
                                {item.unit || ''}
                              </span>
                              <span
                                className={
                                  isReduction ? 'text-emerald-400/80' : 'text-rose-400/80'
                                }
                              >
                                {isReduction ? 'Decreased Risk' : 'Increased Risk'}
                              </span>
                            </div>
                          </div>
                        );
                      })
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Scenario Audit History Drawer */}
          {history.length > 0 && (
            <div className="glass-panel p-4 rounded-2xl border border-glass-border">
              <div className="flex items-center gap-2 pb-2.5 border-b border-white/[0.06] text-xs font-semibold text-slate-300">
                <History className="w-3.5 h-3.5 text-cyan-400" />
                <span>Session Simulation History</span>
              </div>
              <div className="divide-y divide-white/[0.04] mt-2 max-h-40 overflow-y-auto">
                {history.map((histItem, idx) => (
                  <div
                    key={histItem.scenario_id}
                    className="py-2 flex items-center justify-between text-xs font-mono"
                  >
                    <div>
                      <span className="text-slate-300 font-semibold block line-clamp-1">
                        {histItem.scenario_name}
                      </span>
                      <span className="text-[10px] text-slate-500">
                        {new Date(histItem.timestamp).toLocaleTimeString()} •{' '}
                        {histItem.applied_perturbations.length} shifts
                      </span>
                    </div>
                    <div className="text-right">
                      {histItem.max_risk_reduction > 0 ? (
                        <span className="text-emerald-400 text-[11px]">
                          ▼ -{(histItem.max_risk_reduction * 100).toFixed(0)}%
                        </span>
                      ) : histItem.max_risk_elevation > 0 ? (
                        <span className="text-rose-400 text-[11px]">
                          ▲ +{(histItem.max_risk_elevation * 100).toFixed(0)}%
                        </span>
                      ) : (
                        <span className="text-slate-500 text-[11px]">0.0%</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
