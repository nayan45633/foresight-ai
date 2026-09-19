'use client';

import React from 'react';

interface GlassSkeletonProps {
  className?: string;
  count?: number;
  height?: string;
}

export function GlassSkeleton({ className = 'h-6 w-full', count = 1, height }: GlassSkeletonProps) {
  return (
    <div className="space-y-3 w-full animate-pulse">
      {Array.from({ length: count }).map((_, idx) => (
        <div
          key={idx}
          style={height ? { height } : undefined}
          className={`rounded-xl bg-slate-800/40 border border-white/[0.04] backdrop-blur-sm ${className}`}
        />
      ))}
    </div>
  );
}

export function ForecastCardSkeleton() {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 animate-pulse">
      {[1, 2, 3, 4].map((i) => (
        <div key={i} className="p-4 rounded-xl glass-card border border-white/[0.06] space-y-3">
          <div className="flex justify-between items-center">
            <div className="h-4 w-24 bg-slate-800/60 rounded-md" />
            <div className="h-4 w-16 bg-slate-800/60 rounded-full" />
          </div>
          <div className="h-3 w-28 bg-slate-800/40 rounded-md" />
          <div className="space-y-1.5 pt-2">
            <div className="h-3 w-full bg-slate-800/40 rounded-md" />
            <div className="h-2 w-full bg-slate-800/50 rounded-full" />
          </div>
          <div className="h-3 w-32 bg-slate-800/30 rounded-md pt-2" />
        </div>
      ))}
    </div>
  );
}
