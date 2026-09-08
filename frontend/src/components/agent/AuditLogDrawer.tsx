"use client";

import React, { useEffect, useState } from "react";
import { AuditLogEntry } from "@/lib/types";
import { api } from "@/lib/api";
import { Shield, ShieldAlert, CheckCircle2, Clock, X, Lock, Terminal, Layers } from "lucide-react";

interface AuditLogDrawerProps {
  runId: string;
  isOpen: boolean;
  onClose: () => void;
}

export const AuditLogDrawer: React.FC<AuditLogDrawerProps> = ({ runId, isOpen, onClose }) => {
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (isOpen && runId) {
      setIsLoading(true);
      api
        .getRunAuditLogs(runId)
        .then(setLogs)
        .catch(console.error)
        .finally(() => setIsLoading(false));
    }
  }, [isOpen, runId]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-end bg-background/60 backdrop-blur-sm">
      <div className="w-full max-w-lg h-full glass-panel-glow border-l border-white/10 p-6 flex flex-col shadow-2xl animate-in slide-in-from-right duration-200">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-white/5 flex-shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400">
              <Shield className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-white tracking-tight">
                Security Audit Log
              </h3>
              <p className="text-xs text-slate-400">Immutable trail for run #{runId}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-lg bg-surface-100 hover:bg-surface-200 text-slate-400 hover:text-white flex items-center justify-center transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Audit Stream List */}
        <div className="flex-1 overflow-y-auto pt-4 space-y-3 pr-1">
          {isLoading && (
            <div className="p-8 text-center text-xs text-slate-400">Loading audit trail...</div>
          )}

          {!isLoading && logs.length === 0 && (
            <div className="p-8 text-center text-xs text-slate-500">No security audit logs recorded for this run.</div>
          )}

          {logs.map((log) => (
            <div
              key={log.id}
              className="p-3.5 rounded-xl bg-surface-100/90 border border-white/5 text-xs space-y-1.5"
            >
              <div className="flex items-center justify-between">
                <span className="font-mono font-semibold uppercase text-indigo-400">
                  {log.event_type}
                </span>
                <span className={`px-2 py-0.5 rounded text-[10px] font-semibold uppercase ${
                  log.status === "success"
                    ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                    : "bg-rose-500/10 text-rose-400 border border-rose-500/20"
                }`}>
                  {log.status}
                </span>
              </div>

              {log.details && (
                <pre className="p-2 rounded bg-background/80 text-slate-300 font-mono text-[11px] overflow-x-auto whitespace-pre-wrap">
                  {log.details}
                </pre>
              )}

              <div className="pt-1 flex items-center justify-between text-[10px] text-slate-500">
                <span>Actor IP: {log.actor_ip || "Internal"}</span>
                <span>{new Date(log.timestamp).toLocaleTimeString()}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
