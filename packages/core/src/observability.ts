/**
 * @saleha/core - Structured Observability & Telemetry Loop
 * Real-time monitoring for Web Vitals, nanosecond jitter, and error reporting.
 */

export interface TelemetryMetric {
  name: string;
  value: number;
  unit: "ms" | "ns" | "count" | "percent";
  tags: Record<string, string>;
  timestamp: number;
}

export class ObservabilityEngine {
  private static metrics: TelemetryMetric[] = [];

  static recordMetric(name: string, value: number, unit: TelemetryMetric["unit"] = "ms", tags: Record<string, string> = {}) {
    const metric: TelemetryMetric = {
      name,
      value,
      unit,
      tags,
      timestamp: Date.now(),
    };
    this.metrics.push(metric);
    if (this.metrics.length > 1000) {
      this.metrics.shift();
    }
  }

  static getRecentMetrics(): TelemetryMetric[] {
    return [...this.metrics];
  }

  static getSystemHealth() {
    // The previous version returned fixed p50/p99 nanosecond figures with
    // no measurement behind them. Now the percentiles come from the
    // recorded metrics, and an empty store reports NO_DATA instead of
    // a healthy verdict.
    const values = this.metrics.map((m) => m.value).sort((a, b) => a - b);
    if (values.length === 0) {
      return {
        status: "NO_DATA",
        uptimeSeconds: process.uptime ? process.uptime() : 0,
        totalMetricsRecorded: 0,
        p50LatencyNs: 0,
        p99LatencyNs: 0,
      };
    }
    const at = (p: number) => values[Math.min(values.length - 1, Math.floor(p * values.length))];
    return {
      status: "HEALTHY",
      uptimeSeconds: process.uptime ? process.uptime() : 0,
      totalMetricsRecorded: values.length,
      p50LatencyNs: at(0.5),
      p99LatencyNs: at(0.99),
    };
  }
}

