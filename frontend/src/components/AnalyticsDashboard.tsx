import React, { useEffect, useState } from "react";
import { AnalyticsSummary, ProviderMetrics, PerformanceMetrics } from "@/lib/types";
import { useAuth } from "@/lib/auth-context";

interface AnalyticsDashboardProps {
  onClose?: () => void;
}

export function AnalyticsDashboard({ onClose }: AnalyticsDashboardProps) {
  const { token } = useAuth();
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [providers, setProviders] = useState<ProviderMetrics[]>([]);
  const [performance, setPerformance] = useState<PerformanceMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [timeRange, setTimeRange] = useState("30");

  useEffect(() => {
    fetchAnalytics();
  }, [timeRange, token]);

  async function fetchAnalytics() {
    if (!token) return;
    
    setLoading(true);
    setError(null);

    try {
      const [summaryRes, providersRes, performanceRes] = await Promise.all([
        fetch(`/api/analytics/summary?days=${timeRange}`, {
          headers: { Authorization: `Bearer ${token}` },
        }),
        fetch("/api/analytics/providers", {
          headers: { Authorization: `Bearer ${token}` },
        }),
        fetch(`/api/analytics/performance?days=${timeRange}`, {
          headers: { Authorization: `Bearer ${token}` },
        }),
      ]);

      if (!summaryRes.ok || !providersRes.ok || !performanceRes.ok) {
        throw new Error("Failed to fetch analytics");
      }

      setSummary(await summaryRes.json());
      setProviders(await providersRes.json());
      setPerformance(await performanceRes.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">Loading analytics...</div>
      </div>
    );
  }

  return (
    <div className="w-full bg-white rounded-lg shadow-lg p-6">
      {/* Header */}
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Analytics Dashboard</h1>
        <div className="flex gap-2">
          <select
            value={timeRange}
            onChange={(e) => setTimeRange(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-md bg-white text-sm"
          >
            <option value="7">Last 7 days</option>
            <option value="30">Last 30 days</option>
            <option value="90">Last 90 days</option>
            <option value="365">Last year</option>
          </select>
          {onClose && (
            <button
              onClick={onClose}
              className="px-4 py-2 text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-md"
            >
              Close
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-md">
          <p className="text-red-800">Error: {error}</p>
        </div>
      )}

      {/* Summary Cards */}
      {summary && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <div className="bg-blue-50 p-4 rounded-lg border border-blue-200">
            <p className="text-gray-600 text-sm">Total Runs</p>
            <p className="text-3xl font-bold text-blue-600">{summary.total_runs}</p>
          </div>
          <div className="bg-green-50 p-4 rounded-lg border border-green-200">
            <p className="text-gray-600 text-sm">Success Rate</p>
            <p className="text-3xl font-bold text-green-600">
              {summary.total_runs > 0
                ? Math.round((summary.successful_runs / summary.total_runs) * 100)
                : 0}
              %
            </p>
          </div>
          <div className="bg-purple-50 p-4 rounded-lg border border-purple-200">
            <p className="text-gray-600 text-sm">Avg Confidence</p>
            <p className="text-3xl font-bold text-purple-600">
              {summary.average_confidence.toFixed(1)}%
            </p>
          </div>
          <div className="bg-orange-50 p-4 rounded-lg border border-orange-200">
            <p className="text-gray-600 text-sm">Files Changed</p>
            <p className="text-3xl font-bold text-orange-600">{summary.total_files_changed}</p>
          </div>
        </div>
      )}

      {/* Provider Performance */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
        <div className="bg-gray-50 p-6 rounded-lg border border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Provider Performance</h2>
          <div className="space-y-4">
            {providers.map((provider) => (
              <div key={provider.provider} className="bg-white p-4 rounded border border-gray-200">
                <div className="flex justify-between items-center mb-2">
                  <p className="font-medium text-gray-900">{provider.provider}</p>
                  <span className="text-sm text-gray-500">{provider.total_runs} runs</span>
                </div>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div>
                    <p className="text-gray-600">Success Rate</p>
                    <p className="font-semibold text-gray-900">{provider.success_rate.toFixed(1)}%</p>
                  </div>
                  <div>
                    <p className="text-gray-600">Avg Confidence</p>
                    <p className="font-semibold text-gray-900">{provider.average_confidence.toFixed(1)}%</p>
                  </div>
                  <div>
                    <p className="text-gray-600">Avg Duration</p>
                    <p className="font-semibold text-gray-900">{provider.average_duration_seconds.toFixed(1)}s</p>
                  </div>
                  <div>
                    <p className="text-gray-600">Avg Files</p>
                    <p className="font-semibold text-gray-900">{provider.average_files_changed.toFixed(1)}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Performance Metrics */}
        {performance && (
          <div className="bg-gray-50 p-6 rounded-lg border border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Performance Metrics</h2>
            <div className="space-y-4">
              <div className="bg-white p-4 rounded border border-gray-200">
                <p className="text-gray-600 text-sm">Avg Step Time</p>
                <p className="text-2xl font-bold text-gray-900">
                  {performance.average_step_time_seconds.toFixed(2)}s
                </p>
              </div>
              <div className="bg-white p-4 rounded border border-gray-200">
                <p className="text-gray-600 text-sm">Avg Iterations</p>
                <p className="text-2xl font-bold text-gray-900">
                  {performance.average_iterations_per_run.toFixed(1)}
                </p>
              </div>
              {Object.keys(performance.most_used_tools).length > 0 && (
                <div className="bg-white p-4 rounded border border-gray-200">
                  <p className="text-gray-600 text-sm mb-2">Top Tools</p>
                  <ul className="space-y-1">
                    {Object.entries(performance.most_used_tools)
                      .slice(0, 3)
                      .map(([tool, count]) => (
                        <li key={tool} className="flex justify-between text-sm">
                          <span>{tool}</span>
                          <span className="text-gray-600">{count}x</span>
                        </li>
                      ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Daily Activity Chart (simple text-based) */}
      {summary && Object.keys(summary.daily_activity).length > 0 && (
        <div className="bg-gray-50 p-6 rounded-lg border border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Daily Activity</h2>
          <div className="space-y-2">
            {Object.entries(summary.daily_activity)
              .slice(0, 7)
              .map(([date, count]) => (
                <div key={date} className="flex items-center gap-4">
                  <span className="w-20 text-sm text-gray-600">{date}</span>
                  <div className="flex-1 bg-gray-200 rounded h-6 overflow-hidden">
                    <div
                      className="bg-blue-500 h-full"
                      style={{
                        width: `${Math.min(
                          (count /
                            Math.max(
                              ...Object.values(summary.daily_activity).filter(
                                (c) => typeof c === "number"
                              )
                            )) *
                            100,
                          100
                        )}%`,
                      }}
                    />
                  </div>
                  <span className="w-8 text-right text-sm font-medium text-gray-900">{count}</span>
                </div>
              ))}
          </div>
        </div>
      )}
    </div>
  );
}
