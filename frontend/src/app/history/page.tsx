"use client";

import React, { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { AuthGate } from "@/components/auth/AuthGate";
import { DiffViewer } from "@/components/agent/DiffViewer";
import { ResultCard } from "@/components/agent/ResultCard";
import { AuditLogDrawer } from "@/components/agent/AuditLogDrawer";
import { AgentRun } from "@/lib/types";
import { api } from "@/lib/api";
import {
  History,
  CheckCircle2,
  XCircle,
  Clock,
  Ban,
  AlertTriangle,
  Github,
  ChevronRight,
  Shield,
  Layers,
  ArrowLeft,
  RotateCcw,
} from "lucide-react";

export default function HistoryPage() {
  const { isAuthenticated, isLoading: isAuthLoading } = useAuth();
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [selectedRun, setSelectedRun] = useState<AgentRun | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isAuditDrawerOpen, setIsAuditDrawerOpen] = useState(false);

  const fetchRuns = async () => {
    setIsLoading(true);
    try {
      const data = await api.listRuns(50, 0);
      setRuns(data);
    } catch (err) {
      console.error("Failed to fetch run history:", err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (isAuthenticated) {
      fetchRuns();
    }
  }, [isAuthenticated]);

  if (isAuthLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="w-8 h-8 rounded-full border-2 border-indigo-500 border-t-transparent animate-spin" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <AuthGate />;
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400">
            <History className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white tracking-tight">Run History & Audit Trails</h1>
            <p className="text-xs text-slate-400">Persistent execution records stored in SQLite</p>
          </div>
        </div>

        <button
          onClick={fetchRuns}
          disabled={isLoading}
          className="px-3.5 py-2 rounded-xl bg-surface-100 hover:bg-surface-200 border border-white/10 text-slate-300 text-xs font-semibold flex items-center gap-2 transition-colors"
        >
          <RotateCcw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Selected Run Details Inspector */}
      {selectedRun ? (
        <div className="space-y-6 animate-in fade-in-50 duration-200">
          <button
            onClick={() => setSelectedRun(null)}
            className="px-3 py-1.5 rounded-lg bg-surface-100 hover:bg-surface-200 text-slate-300 text-xs font-medium flex items-center gap-1.5 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Back to All Runs</span>
          </button>

          <ResultCard
            run={selectedRun}
            onCreatePR={() => {}}
          />

          <div className="flex items-center justify-between pt-2">
            <h3 className="text-sm font-bold text-white tracking-tight">Git Diff & File Changes</h3>
            <button
              onClick={() => setIsAuditDrawerOpen(true)}
              className="px-3.5 py-1.5 rounded-lg bg-surface-100 hover:bg-surface-200 border border-white/10 text-slate-300 text-xs font-medium flex items-center gap-1.5 transition-colors"
            >
              <Shield className="w-3.5 h-3.5 text-indigo-400" />
              <span>Inspect Security Logs</span>
            </button>
          </div>

          <DiffViewer diff={selectedRun.diff} filesChanged={selectedRun.files_changed} />

          <AuditLogDrawer
            runId={selectedRun.id}
            isOpen={isAuditDrawerOpen}
            onClose={() => setIsAuditDrawerOpen(false)}
          />
        </div>
      ) : (
        <>
          {/* Runs Table / List */}
          <div className="glass-panel rounded-2xl overflow-hidden">
          {isLoading && (
            <div className="p-12 text-center text-xs text-slate-400">Loading history records...</div>
          )}

          {!isLoading && runs.length === 0 && (
            <div className="p-12 text-center text-slate-500 text-sm">
              No previous agent runs found in database.
            </div>
          )}

          {!isLoading && runs.length > 0 && (
            <div className="divide-y divide-white/5">
              {runs.map((run) => (
                <div
                  key={run.id}
                  onClick={() => setSelectedRun(run)}
                  className="p-4 sm:p-5 hover:bg-surface-100/50 transition-colors cursor-pointer flex items-center justify-between gap-4 group"
                >
                  <div className="flex items-center gap-3.5 min-w-0">
                    <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${
                      run.status === "success"
                        ? "bg-emerald-500/20 text-emerald-400"
                        : run.status === "running"
                        ? "bg-cyan-500/20 text-cyan-400"
                        : "bg-rose-500/20 text-rose-400"
                    }`}>
                      {run.status === "success" ? (
                        <CheckCircle2 className="w-4 h-4" />
                      ) : run.status === "running" ? (
                        <Clock className="w-4 h-4" />
                      ) : run.status === "stopped" ? (
                        <Ban className="w-4 h-4" />
                      ) : run.status === "stuck" ? (
                        <AlertTriangle className="w-4 h-4" />
                      ) : (
                        <XCircle className="w-4 h-4" />
                      )}
                    </div>

                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-mono text-xs font-semibold text-white">#{run.id}</span>
                        <span className="text-xs text-slate-400 truncate max-w-xs sm:max-w-md font-sans">
                          {run.task}
                        </span>
                        {run.provider_used && (
                          <span className="px-2 py-0.5 rounded text-[10px] font-mono uppercase bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
                            {run.provider_used}
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-3 text-[11px] text-slate-500 mt-1">
                        <span className="flex items-center gap-1">
                          <Github className="w-3 h-3 text-slate-400" />
                          {run.repo_url.replace("https://github.com/", "")}
                        </span>
                        <span>&bull;</span>
                        <span>{new Date(run.created_at).toLocaleString()}</span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-3 flex-shrink-0">
                    {run.confidence && (
                      <span className="text-xs font-mono text-emerald-400 font-semibold hidden sm:inline">
                        {run.confidence}% confidence
                      </span>
                    )}
                    <ChevronRight className="w-4 h-4 text-slate-500 group-hover:text-white group-hover:translate-x-0.5 transition-all" />
                  </div>
                </div>
              ))}
            </div>
          )}
          </div>
        </>
      )}
    </div>
  );
}
