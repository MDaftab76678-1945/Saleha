---
id: "agent_web_developer"
name: "Modern Web Developer"
type: "agent_profile"
version: "2.0.0"
---

# Web Developer Specification

## 1. Accessible, High-Performance UI Component (React 18+ / Tailwind)
```tsx
import React, { useId } from 'react';

interface MetricCardProps {
  title: string;
  value: string | number;
  changeRate: number;
  isLoading?: boolean;
}

export const MetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  changeRate,
  isLoading = false,
}) => {
  const labelId = useId();
  const isPositive = changeRate >= 0;

  if (isLoading) {
    return (
      <div className="animate-pulse p-6 bg-slate-900 border border-slate-800 rounded-xl">
        <div className="h-4 bg-slate-700 rounded w-1/3 mb-4"></div>
        <div className="h-8 bg-slate-700 rounded w-1/2"></div>
      </div>
    );
  }

  return (
    <article
      aria-labelledby={labelId}
      className="p-6 bg-slate-900/80 backdrop-blur border border-slate-800 rounded-xl shadow-lg hover:border-slate-700 transition duration-200"
    >
      <h3 id={labelId} className="text-sm font-medium text-slate-400">
        {title}
      </h3>
      <div className="mt-2 flex items-baseline justify-between">
        <p className="text-3xl font-semibold tracking-tight text-white">{value}</p>
        <span
          className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold ${
            isPositive ? 'bg-emerald-950 text-emerald-400 border border-emerald-800' : 'bg-rose-950 text-rose-400 border border-rose-800'
          }`}
        >
          {isPositive ? '+' : ''}{changeRate}%
        </span>
      </div>
    </article>
  );
};
```
