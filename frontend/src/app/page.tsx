'use client';

import React, { useEffect, useState, useCallback, useRef } from 'react';
import { 
  Shield, 
  Activity, 
  Cpu, 
  Radio, 
  Clock, 
  CheckCircle2, 
  AlertTriangle,
  Zap, 
  Layers, 
  BarChart3, 
  Sparkles, 
  Server, 
  Lock, 
  LogOut,
  User,
  Workflow, 
  Check, 
  Sliders,
  BrainCircuit,
  LayoutDashboard,
  Target
} from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import { AuthModal } from '@/components/auth/AuthModal';
import { CommandCenterOverview } from '@/components/overview/CommandCenterOverview';
import { ForecastPreviewCard } from '@/components/forecast/ForecastPreviewCard';
import { TelemetryDashboard } from '@/components/telemetry/TelemetryDashboard';
import { RiskStateDashboard } from '@/components/risk/RiskStateDashboard';
import { ExplainabilityView } from '@/components/explainability/ExplainabilityView';
import { WhatIfLab } from '@/components/whatif/WhatIfLab';
import { SystemHealthView } from '@/components/system/SystemHealthView';
import { systemApi, HealthCheckResponse } from '@/lib/api/system';

const MAIN_TABS = [
  { id: 'OVERVIEW', label: 'Overview', icon: LayoutDashboard },
  { id: 'FORECASTING', label: 'Forecast', icon: Zap },
  { id: 'TELEMETRY', label: 'Telemetry', icon: Radio },
  { id: 'RISK', label: 'Risk', icon: Workflow },
  { id: 'EXPLAINABILITY', label: 'Explainability', icon: BrainCircuit },
  { id: 'WHATIF', label: 'What-If', icon: Sliders },
  { id: 'SYSTEM', label: 'System', icon: Server },
] as const;

export type TabId = typeof MAIN_TABS[number]['id'];

export default function Home() {
  const { user, role, isAuthenticated, logout } = useAuth();
  const [activeTab, setActiveTab] = useState<TabId>('OVERVIEW');
  const [backendHealth, setBackendHealth] = useState<HealthCheckResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [authModalMode, setAuthModalMode] = useState<'login' | 'register'>('login');

  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const navContainerRef = useRef<HTMLDivElement | null>(null);
  const [indicatorStyle, setIndicatorStyle] = useState<{
    transform: string;
    width: number;
    opacity: number;
  }>({
    transform: 'translate3d(0, 0, 0)',
    width: 0,
    opacity: 0,
  });

  const updateIndicatorPosition = useCallback(() => {
    const activeIdx = MAIN_TABS.findIndex((t) => t.id === activeTab);
    const activeEl = tabRefs.current[activeIdx];
    const containerEl = navContainerRef.current;
    if (activeEl && containerEl) {
      const activeLeft = activeEl.offsetLeft;
      const activeWidth = activeEl.offsetWidth;
      setIndicatorStyle({
        transform: `translate3d(${activeLeft}px, 0, 0)`,
        width: activeWidth,
        opacity: 1,
      });
    }
  }, [activeTab]);

  useEffect(() => {
    updateIndicatorPosition();
    const handleResize = () => updateIndicatorPosition();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [updateIndicatorPosition]);

  useEffect(() => {
    async function checkHealth() {
      try {
        const data = await systemApi.getHealth();
        setBackendHealth(data);
      } catch {
        setBackendHealth({ status: 'offline', service: 'Foresight AI', environment: 'production', timestamp: '', python_version: '', system: '' });
      } finally {
        setLoading(false);
      }
    }
    checkHealth();
  }, []);

  const handleKeyDown = (e: React.KeyboardEvent, index: number) => {
    if (e.key === 'ArrowRight') {
      e.preventDefault();
      const nextIdx = (index + 1) % MAIN_TABS.length;
      setActiveTab(MAIN_TABS[nextIdx].id);
      tabRefs.current[nextIdx]?.focus();
    } else if (e.key === 'ArrowLeft') {
      e.preventDefault();
      const prevIdx = (index - 1 + MAIN_TABS.length) % MAIN_TABS.length;
      setActiveTab(MAIN_TABS[prevIdx].id);
      tabRefs.current[prevIdx]?.focus();
    } else if (e.key === 'Home') {
      e.preventDefault();
      setActiveTab(MAIN_TABS[0].id);
      tabRefs.current[0]?.focus();
    } else if (e.key === 'End') {
      e.preventDefault();
      setActiveTab(MAIN_TABS[MAIN_TABS.length - 1].id);
      tabRefs.current[MAIN_TABS.length - 1]?.focus();
    }
  };

  const handleOpenLogin = () => {
    setAuthModalMode('login');
    setIsAuthModalOpen(true);
  };

  return (
    <div className="min-h-screen flex flex-col justify-between p-3 sm:p-5 lg:p-8 relative overflow-x-hidden">
      {/* Ambient Atmospheric Illumination (Subtle Depth) */}
      <div className="fixed top-0 left-1/2 -translate-x-1/2 w-[900px] h-[360px] bg-cyan-500/[0.035] blur-[160px] pointer-events-none rounded-full" />
      <div className="fixed bottom-0 right-10 w-[600px] h-[340px] bg-indigo-600/[0.025] blur-[180px] pointer-events-none rounded-full" />

      {/* Floating Liquid Glass Navigation Header */}
      <header className="sticky top-3 z-40 glass-nav rounded-2xl px-4 sm:px-5 py-3 mb-6 flex flex-col xl:flex-row items-center justify-between gap-3 transition-all duration-300">
        {/* Brand & Identity */}
        <div className="flex items-center gap-3.5 w-full xl:w-auto justify-between xl:justify-start">
          <div className="flex items-center gap-3">
            <div className="relative p-2 rounded-xl bg-gradient-to-br from-cyan-500/20 to-blue-600/10 border border-cyan-400/30 text-cyan-300 shadow-sm flex items-center justify-center">
              <Shield className="w-5 h-5 text-cyan-400" />
              <div className="absolute inset-0 rounded-xl bg-cyan-400/10 blur-sm pointer-events-none" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-base font-bold tracking-tight text-white">
                  FORESIGHT <span className="text-cyan-400 font-extrabold">AI</span>
                </span>
                <span className="hidden sm:inline-flex text-[10px] uppercase font-mono px-2 py-0.5 rounded-full bg-cyan-950/60 text-cyan-300 border border-cyan-700/40">
                  v1.0.0
                </span>
              </div>
              <p className="text-[11px] text-slate-400 font-normal tracking-normal hidden sm:block">
                Predictive Network Attack Intelligence
              </p>
            </div>
          </div>

          {/* Operator Auth Trigger / Status Pill (Mobile View) */}
          <div className="xl:hidden flex items-center gap-2">
            {isAuthenticated ? (
              <div className="flex items-center gap-2 px-2.5 py-1 rounded-full glass-pill text-[11px] font-mono">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                <span className="text-slate-200 font-semibold">{user?.username}</span>
                <button
                  onClick={logout}
                  className="text-slate-400 hover:text-rose-400 ml-1"
                  title="Sign Out"
                >
                  <LogOut className="w-3 h-3" />
                </button>
              </div>
            ) : (
              <button
                onClick={handleOpenLogin}
                className="px-3 py-1 rounded-full bg-cyan-500/20 text-cyan-300 border border-cyan-400/30 text-xs font-semibold"
              >
                Sign In
              </button>
            )}
          </div>
        </div>

        {/* Continuous Liquid Glass Navigation Island (Single Unified Floating Object) */}
        <nav
          ref={navContainerRef}
          role="tablist"
          aria-label="Main Navigation"
          className="liquid-nav-island w-full xl:w-auto max-w-full overflow-x-auto no-scrollbar"
        >
          {/* Moving Light/Refraction Active Tile */}
          <div
            className="liquid-nav-indicator"
            style={{
              transform: indicatorStyle.transform,
              width: `${indicatorStyle.width}px`,
              opacity: indicatorStyle.opacity,
            }}
            aria-hidden="true"
          />

          {MAIN_TABS.map((tab, idx) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                ref={(el) => {
                  tabRefs.current[idx] = el;
                }}
                role="tab"
                id={`tab-${tab.id}`}
                aria-selected={isActive}
                aria-controls={`panel-${tab.id}`}
                tabIndex={isActive ? 0 : -1}
                onClick={() => setActiveTab(tab.id)}
                onKeyDown={(e) => handleKeyDown(e, idx)}
                className={`liquid-nav-tab flex-1 sm:flex-initial text-xs whitespace-nowrap shrink-0 ${isActive ? 'is-active' : ''}`}
              >
                <Icon
                  className={`w-3.5 h-3.5 transition-colors duration-200 shrink-0 ${
                    isActive ? 'text-cyan-400' : 'text-slate-500'
                  }`}
                />
                <span className="truncate">{tab.label}</span>
              </button>
            );
          })}
        </nav>

        {/* Desktop Header Actions (Auth & Status) */}
        <div className="hidden xl:flex items-center gap-3">
          {/* Operator Profile / Login Button */}
          {isAuthenticated ? (
            <div className="flex items-center gap-2.5 px-3 py-1.5 rounded-full glass-pill border border-white/[0.08]">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-emerald-400 shadow-status-glow animate-pulse" />
                <span className="text-xs font-mono font-bold text-slate-200">{user?.username}</span>
                <span className={`text-[10px] px-2 py-0.5 rounded-full font-mono font-bold uppercase ${
                  role === 'admin' ? 'bg-purple-500/20 text-purple-300 border border-purple-500/30' :
                  role === 'analyst' ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30' :
                  'bg-slate-800 text-slate-400'
                }`}>
                  {role}
                </span>
              </div>
              <button
                onClick={logout}
                className="p-1 rounded-md text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
                title="Sign Out Session"
              >
                <LogOut className="w-3.5 h-3.5" />
              </button>
            </div>
          ) : (
            <button
              onClick={handleOpenLogin}
              className="px-3.5 py-1.5 rounded-full bg-cyan-500/15 hover:bg-cyan-500/25 text-cyan-300 border border-cyan-400/30 text-xs font-semibold transition-all flex items-center gap-1.5 shadow-sm"
            >
              <User className="w-3.5 h-3.5" /> Sign In
            </button>
          )}

          {/* System Health Pill */}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full glass-pill border border-white/[0.08]">
            <span className="relative flex h-2 w-2">
              {backendHealth?.status === 'healthy' && (
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
              )}
              <span className={`relative inline-flex rounded-full h-2 w-2 ${backendHealth?.status === 'healthy' ? 'bg-emerald-400 shadow-status-glow' : 'bg-amber-400'}`} />
            </span>
            <span className="text-[11px] font-mono font-medium tracking-wide text-slate-300">
              {loading ? 'PROBING...' : backendHealth?.status === 'healthy' ? 'API HEALTHY' : 'API DISCONNECTED'}
            </span>
          </div>
        </div>
      </header>

      {/* Main Content Workspace */}
      <main className="flex-1 z-10 w-full max-w-7xl mx-auto">
        <div
          key={activeTab}
          role="tabpanel"
          id={`panel-${activeTab}`}
          aria-labelledby={`tab-${activeTab}`}
          className="animate-tab-content"
        >
          {activeTab === 'OVERVIEW' && (
            <CommandCenterOverview onNavigateTab={(tab) => setActiveTab(tab as TabId)} />
          )}
          {activeTab === 'FORECASTING' && <ForecastPreviewCard />}
          {activeTab === 'TELEMETRY' && <TelemetryDashboard />}
          {activeTab === 'RISK' && <RiskStateDashboard />}
          {activeTab === 'EXPLAINABILITY' && <ExplainabilityView />}
          {activeTab === 'WHATIF' && <WhatIfLab />}
          {activeTab === 'SYSTEM' && <SystemHealthView />}
        </div>
      </main>

      {/* Authentication Modal */}
      <AuthModal
        isOpen={isAuthModalOpen}
        onClose={() => setIsAuthModalOpen(false)}
        initialMode={authModalMode}
      />

      {/* Enterprise SOC Footer */}
      <footer className="mt-8 z-10 border-t border-glass-border pt-4 flex flex-col sm:flex-row items-center justify-between text-xs text-slate-500 font-mono">
        <div className="flex items-center gap-2">
          <span>FORESIGHT AI © 2026</span>
          <span>•</span>
          <span className="text-slate-400">Network Attack Forecasting Intelligence</span>
        </div>
        <div className="flex items-center gap-4 mt-2 sm:mt-0">
          <span>Lookahead Horizons: <strong className="text-cyan-400 font-mono">+5m, +15m, +30m, +60m</strong></span>
          <span>•</span>
          <span>Security Architecture: <strong className="text-slate-400">SOC Enterprise Grade</strong></span>
        </div>
      </footer>
    </div>
  );
}
