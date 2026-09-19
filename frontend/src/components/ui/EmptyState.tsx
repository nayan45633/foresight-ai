'use client';

import React from 'react';
import { LucideIcon, HelpCircle } from 'lucide-react';

interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
  className?: string;
}

export function EmptyState({
  icon: Icon = HelpCircle,
  title,
  description,
  actionLabel,
  onAction,
  className = '',
}: EmptyStateProps) {
  return (
    <div className={`glass-panel p-8 sm:p-12 rounded-2xl border border-glass-border text-center flex flex-col items-center justify-center max-w-xl mx-auto ${className}`}>
      <div className="p-4 rounded-2xl bg-cyan-500/10 border border-cyan-400/20 text-cyan-400 mb-4 shadow-sm">
        <Icon className="w-8 h-8" />
      </div>
      <h3 className="text-base sm:text-lg font-bold text-white tracking-tight mb-2">
        {title}
      </h3>
      <p className="text-xs sm:text-sm text-slate-400 leading-relaxed max-w-md mb-6">
        {description}
      </p>
      {actionLabel && onAction && (
        <button
          onClick={onAction}
          className="px-4 py-2 rounded-xl bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-300 border border-cyan-400/30 text-xs font-semibold transition-all shadow-sm flex items-center gap-2"
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
}
