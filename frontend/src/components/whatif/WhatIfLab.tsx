'use client';

import React, { useEffect, useState, useMemo, useCallback } from 'react';
import { counterfactualApi, FeatureMetadataCatalogResponse, CounterfactualScenarioResponse, FeatureMetadataItem, CounterfactualPreset, AppliedFeaturePerturbation, HorizonCounterfactualResult, ShapDeltaItem } from '@/lib/api/counterfactual';
import { ApiError } from '@/lib/api/client';
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

const CATEGORY_NAMES: Record<string, string> = {
  volume: 'Traffic Volume & Rates',
  duration: 'Flow Duration & Variance',
  tcp_flags: 'TCP Handshake & Flags',
  entropy: 'Cardinality & Entropy',
  protocol: 'Protocol & Packet Dynamics',
  temporal_delta: 'Temporal Derivatives',
  anomaly: 'Behavioral Anomaly Model',
};

type ErrorType = 'NETWORK_ERROR' | 'AUTH_ERROR' | 'BACKEND_ERROR' | 'VALIDATION_ERROR' | null;

export function WhatIfLab() {
  const [catalog, setCatalog] = useState<FeatureMetadataCatalogResponse | null>(null);
  const [loadingCatalog, setLoadingCatalog] = useState<boolean>(true);
  const [evaluating, setEvaluating] = useState<boolean>(false);
  const [activeCategory, setActiveCategory] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [recomputeDerived, setRecomputeDerived] = useState(true);
  const [includeShap, setIncludeShap] = useState(true);

  // Baseline values and active perturbations
  const [baselineValues, setBaselineValues] = useState<Record<string, number>>({});
  const [perturbations, setPerturbations] = useState<Record<string, number>>({});
  const [selectedPreset, setSelectedPreset] = useState<string | null>(null);

  // Simulation response & history
  const [currentResult, setCurrentResult] = useState<CounterfactualScenarioResponse | null>(null);
  const [history, setHistory] = useState<CounterfactualScenarioResponse[]>([]);
  const [selectedHorizonTab, setSelectedHorizonTab] = useState<string>('15');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [errorType, setErrorType] = useState<ErrorType>(null);

  // 1. Fetch feature catalog and presets with cold-start auto-retry
  const loadCatalog = useCallback(async (retryCount = 0) => {
    try {
      setLoadingCatalog(true);
      setErrorMsg(null);
      setErrorType(null);

      const data = await counterfactualApi.getCatalog();
      setCatalog(data);

      // Initialize baseline values with defaults
      const baseMap: Record<string, number> = {};
      data.features.forEach((f: FeatureMetadataItem) => {
        baseMap[f.name] = f.default_value;
      });
      setBaselineValues(baseMap);

      // Run initial default simulation
      await runInitialSimulation(baseMap);
    } catch (err: any) {
      const isNetwork =
        (err instanceof ApiError &&
          (err.code === 'NETWORK_ERROR' || err.status === 0 || err.status === 502 || err.status === 503 || err.status === 504)) ||
        !(err instanceof ApiError);

      if (isNetwork && retryCount < 3) {
        setTimeout(() => {
          loadCatalog(retryCount + 1);
        }, (retryCount + 1) * 3000);
        return;
      }

      if (err instanceof ApiError) {
        if (err.status === 401) {
          setErrorType('AUTH_ERROR');
          setErrorMsg('Authentication token expired or session unverified.');
        } else if (err.code === 'NETWORK_ERROR' || err.status === 0 || err.status === 502 || err.status === 503 || err.status === 504) {
          setErrorType('NETWORK_ERROR');
          setErrorMsg('Unable to connect to the Foresight AI forecasting API. The backend service may be cold-starting on Render.');
        } else {
          setErrorType('BACKEND_ERROR');
          setErrorMsg(err.message || 'Failed to initialize counterfactual forecasting models.');
        }
      } else {
        setErrorType('NETWORK_ERROR');
        setErrorMsg(err.message || 'Unable to connect to the counterfactual engine.');
      }
    } finally {
      setLoadingCatalog(false);
    }
  }, []);

  useEffect(() => {
    loadCatalog();
  }, [loadCatalog]);

  // Run initial simulation
  const runInitialSimulation = async (baseMap: Record<string, number>) => {
    try {
      const data = await counterfactualApi.evaluateScenario({
        scenario_name: 'Baseline Operational State',
        description: 'Initial nominal perimeter state',
        perturbations: { syn_count: baseMap['syn_count'] || 45.0 },
        recompute_derived: true,
        include_shap: true,
      });
      setCurrentResult(data);
      if (data.baseline_vector_summary) {
        setBaselineValues(data.baseline_vector_summary);
      }
    } catch {
      // Non-blocking fallback for initial probe
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
      setErrorType(null);

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

      const data = await counterfactualApi.evaluateScenario(payload);
      setCurrentResult(data);
      setHistory((prev) => [data, ...prev.slice(0, 9)]);
      if (data.baseline_vector_summary) {
        setBaselineValues(data.baseline_vector_summary);
      }
    } catch (err: any) {
      if (err instanceof ApiError) {
        if (err.status === 401) {
          setErrorType('AUTH_ERROR');
          setErrorMsg('Session expired. Please sign in to execute simulations.');
        } else if (err.status === 422) {
          setErrorType('VALIDATION_ERROR');
          setErrorMsg(err.message || 'Feature perturbations outside allowed boundary conditions.');
        } else {
          setErrorType('BACKEND_ERROR');
          setErrorMsg(err.message || 'Counterfactual simulation failed on the backend.');
        }
      } else {
        setErrorType('NETWORK_ERROR');
        setErrorMsg(err.message || 'Simulation network request failed.');
      }
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
  const currentHorizonResult = currentResult?.horizon_results?.[selectedHorizonTab];

  // 1. Initial Full Loading State
  if (loadingCatalog) {
    return (
      <div className="space-y-6 animate-tab-content">
        <div className="glass-panel p-8 sm:p-12 rounded-2xl border border-glass-border flex flex-col items-center justify-center py-20 text-center space-y-4">
          <div className="p-4 rounded-2xl bg-cyan-500/10 border border-cyan-400/30 text-cyan-400 animate-pulse">
            <Sliders className="w-8 h-8 animate-spin" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-white tracking-tight">Initializing What-If Scenario Lab</h3>
            <p className="text-xs text-slate-400 mt-1 max-w-md mx-auto">
              Connecting to Foresight AI forecasting engine, loading 37-feature telemetry schema definitions, and preparing multi-horizon sensitivity models (+5m, +15m, +30m, +60m)...
            </p>
          </div>
          <div className="flex items-center gap-2 text-xs font-mono text-cyan-400 bg-cyan-950/60 px-3 py-1.5 rounded-full border border-cyan-800/40">
            <RefreshCw className="w-3.5 h-3.5 animate-spin" />
            <span>Syncing telemetry contracts...</span>
          </div>
        </div>
      </div>
    );
  }

  // 2. Initial Full Load Error State (Prevents empty broken UI)
  if (!catalog && errorMsg) {
    const isAuth = errorType === 'AUTH_ERROR';
    return (
      <div className="space-y-6 animate-tab-content">
        <div className="glass-panel p-8 sm:p-12 rounded-2xl border border-rose-500/30 bg-rose-950/10 flex flex-col items-center justify-center py-16 text-center space-y-4">
          <div className="p-4 rounded-2xl bg-rose-500/10 border border-rose-500/30 text-rose-400">
            <AlertTriangle className="w-8 h-8" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-white tracking-tight">
              {isAuth ? 'Session Authentication Required' : 'Forecasting Engine Unavailable'}
            </h3>
            <p className="text-xs text-slate-300 mt-1.5 max-w-lg mx-auto leading-relaxed">
              {isAuth
                ? 'Your security session has expired or requires analyst authorization to run model sensitivity simulations.'
                : errorMsg}
            </p>
            {!isAuth && (
              <p className="text-[11px] text-slate-400 mt-2 font-mono">
                If the backend was inactive, Render free instances wake up in ~30–45s.
              </p>
            )}
          </div>
          <div className="flex items-center gap-3 pt-2">
            <button
              onClick={() => loadCatalog()}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-300 font-mono text-xs font-semibold border border-cyan-500/40 transition-all shadow-glow-cyan"
            >
              <RefreshCw className="w-4 h-4" /> Retry Connection
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-tab-content">
      {/* 1. Header Banner & Scientific Disclaimer */}
      <div className="glass-panel p-5 sm:p-8 rounded-2xl border border-glass-border">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6 pb-6 border-b border-white/[0.06]">
          <div className="min-w-0">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-cyan-500/10 text-cyan-400 text-xs font-mono mb-3 border border-cyan-500/20">
              <Sliders className="w-3.5 h-3.5" /> Model Sensitivity & Counterfactual Engine
            </div>
            <h2 className="text-xl sm:text-2xl lg:text-3xl font-bold text-white tracking-tight">
              Interactive What-If Scenario Lab
            </h2>
            <p className="mt-2 text-slate-300 text-xs sm:text-sm max-w-3xl leading-relaxed">
              Perturb 37-dimensional network telemetry features and trigger real model re-inference across all forward horizons. Evaluate how rate limits, firewall rules, and traffic anomalies shift probability distributions, flip alert decisions, and transform TreeSHAP attributions.
            </p>
          </div>

          <div className="flex flex-wrap sm:flex-nowrap items-center gap-2.5 sm:gap-3 shrink-0">
            <button
              onClick={() => runSimulation()}
              disabled={evaluating}
              className="flex-1 sm:flex-initial flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-300 font-mono text-xs sm:text-sm font-semibold border border-cyan-500/40 transition-all shadow-glow-cyan disabled:opacity-50"
            >
              <Play className={`w-4 h-4 ${evaluating ? 'animate-spin' : ''}`} />
              {evaluating ? 'Simulating...' : 'Run Simulation'}
            </button>
            <button
              onClick={handleResetAll}
              className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-slate-800/80 hover:bg-slate-700 text-slate-300 font-mono text-xs sm:text-sm border border-white/[0.08] transition-all"
            >
              <RotateCcw className="w-4 h-4" /> Reset
            </button>
          </div>
        </div>

        {/* Scientific Framing Alert */}
        <div className="mt-4 p-3.5 rounded-xl bg-slate-900/80 border border-cyan-500/20 flex items-start gap-3 text-xs text-slate-300">
          <Info className="w-4 h-4 text-cyan-400 shrink-0 mt-0.5" />
          <div className="min-w-0">
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
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-2.5">
            {catalog?.presets.map((preset) => {
              const isSelected = selectedPreset === preset.preset_id;
              const isMitigation = preset.category.includes('Mitigation');
              return (
                <button
                  key={preset.preset_id}
                  onClick={() => handleApplyPreset(preset)}
                  className={`p-3 rounded-xl border text-left transition-all min-w-0 ${
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
                  <h4 className="text-xs font-semibold text-slate-100 mt-2 truncate">{preset.title}</h4>
                  <p className="text-[11px] text-slate-400 mt-1 line-clamp-2 leading-tight">{preset.description}</p>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Inline Warning/Error Banner */}
      {errorMsg && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span className="truncate">{errorMsg}</span>
          </div>
          <button
            onClick={() => runSimulation()}
            className="px-3 py-1 rounded-lg bg-rose-500/20 text-rose-200 hover:bg-rose-500/30 font-mono text-xs shrink-0"
          >
            Retry
          </button>
        </div>
      )}

      {/* 3. Main Dual-Column Simulation Workspace */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 sm:gap-6">
        {/* Left Column: Feature Perturbation Controls (7 Cols) */}
        <div className="lg:col-span-7 space-y-4 min-w-0">
          <div className="glass-panel p-4 sm:p-5 rounded-2xl border border-glass-border">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-white/[0.06]">
              <div className="flex items-center gap-2">
                <SlidersHorizontal className="w-4 h-4 text-cyan-400" />
                <h3 className="text-sm font-semibold text-slate-100">Telemetry Feature Adjuster</h3>
                <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-slate-800 text-cyan-400 border border-white/[0.06]">
                  {activePerturbationCount} Perturbed
                </span>
              </div>

              {/* Search Box */}
              <div className="relative w-full sm:w-48">
                <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-2.5" />
                <input
                  type="text"
                  placeholder="Filter 37 features..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-8 pr-3 py-1.5 rounded-xl bg-slate-900/90 border border-white/[0.08] text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500/50 w-full font-mono"
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
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 py-2.5 text-xs text-slate-400 border-b border-white/[0.04]">
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
              {filteredFeatures.length === 0 ? (
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
                    <div key={feat.name} className="py-3.5 space-y-2 min-w-0">
                      <div className="flex flex-wrap items-center justify-between gap-1 text-xs">
                        <div className="flex items-center gap-2 min-w-0">
                          <span className="font-semibold text-slate-200 truncate">{feat.display_name}</span>
                          <span className="text-[10px] font-mono text-slate-500 shrink-0">[{feat.unit || 'unitless'}]</span>
                          <span
                            className={`text-[9px] font-mono px-1.5 py-0.2 rounded shrink-0 ${
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
                        <div className="flex items-center gap-2 font-mono ml-auto">
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
                      <div className="flex items-center gap-2 sm:gap-3">
                        <span className="text-[10px] font-mono text-slate-500 min-w-[32px] sm:min-w-[36px]">
                          {feat.min_value}
                        </span>
                        <input
                          type="range"
                          min={feat.min_value}
                          max={feat.max_value}
                          step={feat.slider_step}
                          value={currentVal}
                          onChange={(e) => handleFeatureChange(feat.name, parseFloat(e.target.value))}
                          className="flex-1 accent-cyan-400 bg-slate-800 h-1.5 rounded-lg cursor-pointer min-w-0"
                        />
                        <span className="text-[10px] font-mono text-slate-500 min-w-[32px] sm:min-w-[36px] text-right">
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
        <div className="lg:col-span-5 space-y-4 min-w-0">
          {/* Multi-Horizon Probability Diff Cards */}
          <div className="glass-panel p-4 sm:p-5 rounded-2xl border border-glass-border space-y-4">
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
            <div className="grid grid-cols-4 gap-1 sm:gap-1.5 p-1 rounded-xl bg-slate-900/80 border border-white/[0.04]">
              {['5', '15', '30', '60'].map((hStr) => {
                const res = currentResult?.horizon_results?.[hStr];
                const isSelected = selectedHorizonTab === hStr;
                const isFlipped = res?.decision_flip && res.decision_flip !== 'NO_CHANGE';
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
            {currentHorizonResult ? (
              <div className="space-y-4 pt-2">
                {/* Decision Flip Banner */}
                <div
                  className={`p-3 rounded-xl border flex items-center justify-between gap-2 ${
                    currentHorizonResult.decision_flip === 'ALERT_TO_NO_ALERT'
                      ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                      : currentHorizonResult.decision_flip === 'NO_ALERT_TO_ALERT'
                      ? 'bg-rose-500/10 border-rose-500/30 text-rose-300'
                      : 'bg-slate-900/60 border-white/[0.06] text-slate-300'
                  }`}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    {currentHorizonResult.decision_flip === 'ALERT_TO_NO_ALERT' ? (
                      <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
                    ) : currentHorizonResult.decision_flip === 'NO_ALERT_TO_ALERT' ? (
                      <ShieldAlert className="w-4 h-4 text-rose-400 shrink-0" />
                    ) : (
                      <CheckCircle2 className="w-4 h-4 text-slate-400 shrink-0" />
                    )}
                    <div className="min-w-0">
                      <div className="text-xs font-semibold font-mono truncate">
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
                  <div className="text-right font-mono text-xs shrink-0">
                    <span className="text-[10px] text-slate-400 block">Conformal Set</span>
                    <span className="font-bold text-cyan-300">
                      {currentHorizonResult.conformal_set_transition}
                    </span>
                  </div>
                </div>

                {/* Probability Gauges (Baseline vs Counterfactual) */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
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
                    {!currentHorizonResult.shap_deltas || currentHorizonResult.shap_deltas.length === 0 ? (
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
                              <span className="text-slate-200 font-semibold truncate">{item.feature_name}</span>
                              <span
                                className={`font-bold shrink-0 ml-2 ${
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
            ) : (
              <div className="py-8 text-center text-slate-400 font-mono text-xs">
                Run simulation to compute multi-horizon risk sensitivity.
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
                {history.map((histItem) => (
                  <div
                    key={histItem.scenario_id}
                    className="py-2 flex items-center justify-between text-xs font-mono gap-2"
                  >
                    <div className="min-w-0">
                      <span className="text-slate-300 font-semibold block truncate">
                        {histItem.scenario_name}
                      </span>
                      <span className="text-[10px] text-slate-500">
                        {new Date(histItem.timestamp).toLocaleTimeString()} •{' '}
                        {histItem.applied_perturbations.length} shifts
                      </span>
                    </div>
                    <div className="text-right shrink-0">
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
