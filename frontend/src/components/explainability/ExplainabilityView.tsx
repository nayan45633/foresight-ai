'use client';

import React, { useEffect, useState } from 'react';
import { 
  BarChart3, 
  BrainCircuit, 
  CheckCircle2, 
  ChevronRight, 
  Clock, 
  Info, 
  Layers, 
  RefreshCw, 
  Scale, 
  Sparkles, 
  TrendingDown, 
  TrendingUp, 
  Zap 
} from 'lucide-react';
import { explainabilityApi, GlobalExplainResponse, InstanceExplainResponse } from '@/lib/api/explainability';
import { FeatureAttributionDetail } from '@/lib/api/forecast';
import { GlassSkeleton } from '@/components/ui/GlassSkeleton';
import { EmptyState } from '@/components/ui/EmptyState';

export function ExplainabilityView() {
  const [selectedHorizon, setSelectedHorizon] = useState<number>(15);
  const [instanceData, setInstanceData] = useState<InstanceExplainResponse | null>(null);
  const [globalData, setGlobalData] = useState<GlobalExplainResponse | null>(null);
  const [selectedFeature, setSelectedFeature] = useState<FeatureAttributionDetail | null>(null);
  const [activeTab, setActiveTab] = useState<'instance' | 'global'>('instance');
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchExplainability = async () => {
    try {
      setLoading(true);
      setError(null);
      const [instRes, globRes] = await Promise.allSettled([
        explainabilityApi.explainHorizon(selectedHorizon),
        explainabilityApi.getGlobal(),
      ]);

      if (instRes.status === 'fulfilled') setInstanceData(instRes.value);
      if (globRes.status === 'fulfilled') setGlobalData(globRes.value);

      if (instRes.status === 'rejected' && globRes.status === 'rejected') {
        setError('SHAP explainability engine is currently initializing.');
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load SHAP attribution metrics');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchExplainability();
  }, [selectedHorizon]);

  return (
    <div className="space-y-6 animate-tab-content">
      {/* Header & Horizon Selector */}
      <div className="glass-panel p-5 sm:p-6 rounded-2xl border border-glass-border flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="flex items-center gap-3.5">
          <div className="p-2.5 rounded-xl bg-cyan-500/10 border border-cyan-400/30 text-cyan-400">
            <BrainCircuit className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base sm:text-lg font-bold text-white tracking-tight">
                Model Explainability & TreeSHAP Attribution
              </h2>
              <span className="text-[10px] px-2.5 py-0.5 rounded-full font-mono bg-cyan-950/70 text-cyan-300 border border-cyan-800/50">
                Exact Additive SHAP
              </span>
            </div>
            <p className="text-xs text-slate-400 font-normal mt-0.5">
              Mathematically grounded feature attribution explaining why the model predicted risk for each lookahead horizon.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3 w-full md:w-auto justify-between md:justify-end">
          {/* Sub-Tabs: Instance Attribution vs Global Matrix */}
          <div className="flex rounded-xl p-1 bg-slate-900/60 border border-white/[0.06]">
            <button
              onClick={() => setActiveTab('instance')}
              className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-all ${
                activeTab === 'instance' ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-400/30 shadow-sm' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Horizon Attribution
            </button>
            <button
              onClick={() => setActiveTab('global')}
              className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-all ${
                activeTab === 'global' ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-400/30 shadow-sm' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Global Matrix
            </button>
          </div>

          <button
            onClick={fetchExplainability}
            disabled={loading}
            className="p-2 rounded-xl glass-button text-slate-300 hover:text-cyan-300 transition-all flex items-center justify-center shrink-0"
            title="Refresh SHAP Values"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-cyan-400' : ''}`} />
          </button>
        </div>
      </div>

      {/* TAB 1: HORIZON INSTANCE ATTRIBUTIONS */}
      {activeTab === 'instance' && (
        <div className="space-y-6">
          {/* Horizon Selection Strip */}
          <div className="flex items-center gap-2.5 overflow-x-auto pb-1">
            <span className="text-xs font-mono text-slate-400 mr-1 flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5 text-cyan-400" /> Horizon:
            </span>
            {[5, 15, 30, 60].map((h) => {
              const isSelected = selectedHorizon === h;
              return (
                <button
                  key={h}
                  onClick={() => setSelectedHorizon(h)}
                  className={`px-4 py-2 rounded-xl text-xs font-mono font-semibold transition-all ${
                    isSelected
                      ? 'glass-elevated border-cyan-400 text-white ring-1 ring-cyan-400/30'
                      : 'glass-card text-slate-400 hover:text-slate-200 border-white/[0.06]'
                  }`}
                >
                  +{h}m Lookahead
                </button>
              );
            })}
          </div>

          {loading && !instanceData ? (
            <GlassSkeleton count={4} height="80px" />
          ) : instanceData ? (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Left 2 Columns: Bidirectional Attribution */}
              <div className="lg:col-span-2 space-y-6">
                <div className="glass-panel p-6 rounded-2xl border border-glass-border">
                  <div className="flex items-center justify-between pb-4 mb-5 border-b border-white/[0.06]">
                    <div>
                      <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                        <Sparkles className="w-4 h-4 text-cyan-400" />
                        Feature Drivers for +{instanceData.horizon_minutes}m Forecast
                      </h3>
                      <p className="text-xs text-slate-400 mt-0.5">
                        Calibrated Probability: <span className="text-cyan-300 font-mono font-bold">{(instanceData.calibrated_probability * 100).toFixed(1)}%</span>
                        {' '}· Base Model Value: <span className="font-mono">{instanceData.base_value.toFixed(4)}</span>
                      </p>
                    </div>

                    <div className="flex items-center gap-2">
                      <span className={`text-[10px] font-mono px-2.5 py-1 rounded-full border ${
                        instanceData.additivity_verified 
                          ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' 
                          : 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                      }`}>
                        {instanceData.additivity_verified ? 'Additivity Verified' : 'Approximated'}
                      </span>
                    </div>
                  </div>

                  {/* Positive Risk Contributors */}
                  <div className="space-y-4 mb-6">
                    <span className="text-xs font-semibold text-rose-400 flex items-center gap-1.5">
                      <TrendingUp className="w-3.5 h-3.5" />
                      Features Increasing Model Output
                    </span>
                    <div className="space-y-2.5">
                      {instanceData.top_positive_contributors.map((feat) => (
                        <div
                          key={feat.feature_name}
                          onClick={() => setSelectedFeature(feat)}
                          className={`p-3.5 rounded-xl glass-card border cursor-pointer transition-all flex items-center justify-between text-xs font-mono ${
                            selectedFeature?.feature_name === feat.feature_name 
                              ? 'border-cyan-400 bg-cyan-950/20' 
                              : 'border-white/[0.06] hover:border-rose-500/40'
                          }`}
                        >
                          <div className="space-y-1">
                            <span className="text-slate-200 font-bold block">{feat.feature_name}</span>
                            <span className="text-[11px] text-slate-400">
                              Observed: <strong className="text-slate-300">{feat.observed_value}</strong> {feat.unit || ''}
                            </span>
                          </div>
                          <div className="text-right">
                            <span className="text-rose-400 font-bold text-sm">+{feat.shap_value.toFixed(4)}</span>
                            <span className="text-[10px] text-slate-500 block">Rank #{feat.rank || 1}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Negative Risk Contributors */}
                  <div className="space-y-4">
                    <span className="text-xs font-semibold text-emerald-400 flex items-center gap-1.5">
                      <TrendingDown className="w-3.5 h-3.5" />
                      Features Decreasing Model Output
                    </span>
                    <div className="space-y-2.5">
                      {instanceData.top_negative_contributors.map((feat) => (
                        <div
                          key={feat.feature_name}
                          onClick={() => setSelectedFeature(feat)}
                          className={`p-3.5 rounded-xl glass-card border cursor-pointer transition-all flex items-center justify-between text-xs font-mono ${
                            selectedFeature?.feature_name === feat.feature_name 
                              ? 'border-cyan-400 bg-cyan-950/20' 
                              : 'border-white/[0.06] hover:border-emerald-500/40'
                          }`}
                        >
                          <div className="space-y-1">
                            <span className="text-slate-200 font-bold block">{feat.feature_name}</span>
                            <span className="text-[11px] text-slate-400">
                              Observed: <strong className="text-slate-300">{feat.observed_value}</strong> {feat.unit || ''}
                            </span>
                          </div>
                          <div className="text-right">
                            <span className="text-emerald-400 font-bold text-sm">{feat.shap_value.toFixed(4)}</span>
                            <span className="text-[10px] text-slate-500 block">Rank #{feat.rank || 1}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>

              {/* Right Column: Feature Inspection Sidebar */}
              <div className="space-y-6">
                <div className="glass-panel p-5 sm:p-6 rounded-2xl border border-glass-border space-y-4 text-xs">
                  <h4 className="font-semibold text-white flex items-center gap-2">
                    <Info className="w-4 h-4 text-cyan-400" />
                    Feature Detail & Semantics
                  </h4>

                  {selectedFeature ? (
                    <div className="space-y-3">
                      <div className="p-3.5 rounded-xl bg-slate-900/60 border border-white/[0.06] space-y-2">
                        <span className="text-cyan-300 font-bold font-mono text-sm block">{selectedFeature.feature_name}</span>
                        <p className="text-slate-300 text-xs leading-relaxed">{selectedFeature.description}</p>
                      </div>

                      <div className="p-3.5 rounded-xl bg-slate-900/60 border border-white/[0.06] space-y-2 font-mono text-xs">
                        <div className="flex justify-between text-slate-400">
                          <span>Observed Value:</span>
                          <span className="text-white font-bold">{selectedFeature.observed_value} {selectedFeature.unit || ''}</span>
                        </div>
                        <div className="flex justify-between text-slate-400">
                          <span>Scaled Score:</span>
                          <span className="text-slate-200">{selectedFeature.scaled_value.toFixed(4)}</span>
                        </div>
                        <div className="flex justify-between text-slate-400">
                          <span>Attribution Delta:</span>
                          <span className={selectedFeature.shap_value > 0 ? 'text-rose-400 font-bold' : 'text-emerald-400 font-bold'}>
                            {selectedFeature.shap_value > 0 ? `+${selectedFeature.shap_value.toFixed(5)}` : selectedFeature.shap_value.toFixed(5)}
                          </span>
                        </div>
                        <div className="flex justify-between text-slate-400">
                          <span>Source Engine:</span>
                          <span className="text-slate-300">{selectedFeature.source}</span>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <p className="text-slate-400 text-xs leading-relaxed">
                      Select any positive or negative contributor on the left to inspect its physical meaning and scaled telemetry input.
                    </p>
                  )}

                  <div className="p-3 rounded-xl bg-cyan-950/20 border border-cyan-800/30 text-[11px] text-cyan-200">
                    <strong>Interpretation Note:</strong> SHAP contributions are measured in model-output space. They explain relative feature influence and are not percentage-point changes in calibrated probability.
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <EmptyState
              icon={BrainCircuit}
              title="Awaiting Model Explanation"
              description="SHAP attributions will appear once telemetry windows are processed by the forecasting models."
              actionLabel="Refresh SHAP"
              onAction={fetchExplainability}
            />
          )}
        </div>
      )}

      {/* TAB 2: GLOBAL FEATURE IMPORTANCE MATRIX */}
      {activeTab === 'global' && globalData && (
        <div className="glass-panel p-6 rounded-2xl border border-glass-border space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-white/[0.06]">
            <div>
              <h3 className="text-base font-bold text-white tracking-tight">
                Global 37-Feature Multi-Horizon Attribution Matrix
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Mean absolute SHAP value across {globalData.evaluated_samples_count} held-out validation samples.
              </p>
            </div>
            <span className="text-xs px-3 py-1 rounded-full font-mono bg-slate-900 border border-white/[0.08] text-slate-300">
              Schema {globalData.schema_version}
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-xs font-mono text-left border-collapse">
              <thead>
                <tr className="border-b border-white/[0.06] text-slate-400 bg-slate-900/60">
                  <th className="p-3">Rank</th>
                  <th className="p-3">Feature Name</th>
                  <th className="p-3 text-right">Mean |SHAP|</th>
                  <th className="p-3 text-right text-cyan-400">+5m Horizon</th>
                  <th className="p-3 text-right text-cyan-400">+15m Horizon</th>
                  <th className="p-3 text-right text-cyan-400">+30m Horizon</th>
                  <th className="p-3 text-right text-cyan-400">+60m Horizon</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.04]">
                {globalData.horizon_comparison_matrix?.slice(0, 20).map((row, idx) => (
                  <tr key={row.feature_name} className="hover:bg-slate-900/40 transition-colors">
                    <td className="p-3 text-slate-500">#{idx + 1}</td>
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
