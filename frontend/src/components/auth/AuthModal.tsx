'use client';

import React, { useState } from 'react';
import { Shield, Lock, User, Mail, AlertCircle, X, KeyRound, CheckCircle2 } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  initialMode?: 'login' | 'register';
}

export function AuthModal({ isOpen, onClose, initialMode = 'login' }: AuthModalProps) {
  const { login, register } = useAuth();
  const [mode, setMode] = useState<'login' | 'register'>(initialMode);
  const [usernameOrEmail, setUsernameOrEmail] = useState('');
  const [email, setEmail] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [role, setRole] = useState('analyst');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      if (mode === 'login') {
        await login({
          username_or_email: usernameOrEmail.trim(),
          password,
        });
      } else {
        await register({
          email: email.trim(),
          username: username.trim(),
          password,
          full_name: fullName.trim() || undefined,
          role,
        });
      }
      onClose();
    } catch (err: any) {
      setError(err.message || 'Authentication failed. Please check credentials.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-md animate-fade-slide">
      <div 
        className="w-full max-w-md glass-panel p-6 sm:p-8 rounded-2xl border border-white/[0.12] shadow-2xl relative"
        role="dialog"
        aria-modal="true"
        aria-labelledby="auth-modal-title"
      >
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-2 rounded-xl glass-button text-slate-400 hover:text-white transition-colors"
          aria-label="Close dialog"
        >
          <X className="w-4 h-4" />
        </button>

        {/* Header */}
        <div className="flex items-center gap-3 mb-6">
          <div className="p-2.5 rounded-xl bg-cyan-500/10 border border-cyan-400/30 text-cyan-400">
            <Shield className="w-5 h-5" />
          </div>
          <div>
            <h3 id="auth-modal-title" className="text-lg font-bold text-white tracking-tight">
              {mode === 'login' ? 'Operator Sign In' : 'Register SOC Operator'}
            </h3>
            <p className="text-xs text-slate-400">
              {mode === 'login' 
                ? 'Authenticate to access persistent intelligence & simulation' 
                : 'Create an authorized SOC operator profile'}
            </p>
          </div>
        </div>

        {/* Mode Selector */}
        <div className="flex rounded-xl p-1 bg-slate-900/60 border border-white/[0.06] mb-5">
          <button
            type="button"
            onClick={() => { setMode('login'); setError(null); }}
            className={`flex-1 py-1.5 text-xs font-semibold rounded-lg transition-all ${
              mode === 'login' ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-400/30 shadow-sm' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Sign In
          </button>
          <button
            type="button"
            onClick={() => { setMode('register'); setError(null); }}
            className={`flex-1 py-1.5 text-xs font-semibold rounded-lg transition-all ${
              mode === 'register' ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-400/30 shadow-sm' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Register
          </button>
        </div>

        {/* Error Alert */}
        {error && (
          <div className="p-3 mb-4 rounded-xl bg-rose-950/40 border border-rose-500/40 text-rose-300 text-xs flex items-start gap-2">
            <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
            <span className="leading-relaxed">{error}</span>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {mode === 'login' ? (
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">Username or Email</label>
              <div className="relative">
                <User className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                <input
                  type="text"
                  required
                  value={usernameOrEmail}
                  onChange={(e) => setUsernameOrEmail(e.target.value)}
                  placeholder="analyst_soc1 or user@foresight.ai"
                  className="w-full pl-9 pr-3 py-2 text-xs bg-slate-950/60 border border-white/[0.08] rounded-xl text-slate-100 placeholder-slate-500 focus:outline-none focus:border-cyan-400 focus:ring-1 focus:ring-cyan-400/30 transition-all font-mono"
                />
              </div>
            </div>
          ) : (
            <>
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Email Address</label>
                <div className="relative">
                  <Mail className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="analyst@foresight.ai"
                    className="w-full pl-9 pr-3 py-2 text-xs bg-slate-950/60 border border-white/[0.08] rounded-xl text-slate-100 placeholder-slate-500 focus:outline-none focus:border-cyan-400 font-mono"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Username</label>
                <div className="relative">
                  <User className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                  <input
                    type="text"
                    required
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    placeholder="soc_analyst"
                    className="w-full pl-9 pr-3 py-2 text-xs bg-slate-950/60 border border-white/[0.08] rounded-xl text-slate-100 placeholder-slate-500 focus:outline-none focus:border-cyan-400 font-mono"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Full Name (Optional)</label>
                <input
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Alex Rivera"
                  className="w-full px-3 py-2 text-xs bg-slate-950/60 border border-white/[0.08] rounded-xl text-slate-100 placeholder-slate-500 focus:outline-none focus:border-cyan-400"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">SOC Role</label>
                <select
                  value={role}
                  onChange={(e) => setRole(e.target.value)}
                  className="w-full px-3 py-2 text-xs bg-slate-950/60 border border-white/[0.08] rounded-xl text-slate-100 focus:outline-none focus:border-cyan-400 font-mono"
                >
                  <option value="analyst">Analyst (Forecasting, Risk & Simulation Access)</option>
                  <option value="user">User (Read-only Operational Dashboards)</option>
                  <option value="admin">Administrator (Model Promotion & User Registry)</option>
                </select>
              </div>
            </>
          )}

          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1">Password</label>
            <div className="relative">
              <KeyRound className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
              <input
                type="password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                className="w-full pl-9 pr-3 py-2 text-xs bg-slate-950/60 border border-white/[0.08] rounded-xl text-slate-100 placeholder-slate-500 focus:outline-none focus:border-cyan-400 font-mono"
              />
            </div>
            {mode === 'register' && (
              <span className="text-[10px] text-slate-500 mt-1 block">Minimum 8 characters with salted bcrypt hashing</span>
            )}
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full mt-2 py-2.5 px-4 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-slate-950 font-bold text-xs shadow-lg shadow-cyan-500/20 transition-all flex items-center justify-center gap-2"
          >
            {loading ? (
              <span className="animate-spin rounded-full h-4 w-4 border-2 border-slate-950 border-t-transparent" />
            ) : mode === 'login' ? (
              <>
                <Lock className="w-3.5 h-3.5" /> Authenticate Session
              </>
            ) : (
              <>
                <CheckCircle2 className="w-3.5 h-3.5" /> Create Operator Account
              </>
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
