"use client";

import React from "react";
import { AgentRun } from "@/lib/types";
import {
  CheckCircle2,
  XCircle,
  AlertTriangle,
  GitPullRequest,
  Check,
  ShieldCheck,
  FileCode,
  Gauge,
  Bot,
} from "lucide-react";

interface ResultCardProps {
  run: AgentRun;
  onCreatePR: () => void;
  prSuccessUrl?: string | null;
}

export const ResultCard: React.FC<ResultCardProps> = ({ run, onCreatePR, prSuccessUrl }) => {
  const isSuccess = run.status === "success";
  const confidence = run.confidence ?? 85;

  return (
    <div className="w-full glass-panel-glow rounded-2xl p-6 sm:p-7 relative overflow-hidden">
      {/* Background Accent */}
      <div className={`absolute top-0 right-0 w-80 h-80 rounded-full blur-3xl pointer-events-none ${
        isSuccess ? "bg-emerald-500/10" : "bg-rose-500/10"
      }`} />

      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-5 border-b border-white/5">
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
            isSuccess
              ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
              : "bg-rose-500/20 text-rose-400 border border-rose-500/30"
          }`}>
            {isSuccess ? <CheckCircle2 className="w-5 h-5" /> : <XCircle className="w-5 h-5" />}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-base font-bold text-white tracking-tight">
                {isSuccess ? "Task Execution Succeeded" : `Execution Ended: ${run.status.toUpperCase()}`}
              </h3>
              {run.provider_used && (
                <span className="px-2 py-0.5 rounded text-[10px] font-mono uppercase bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
                  {run.provider_used}
                </span>
              )}
            </div>
            <p className="text-xs text-slate-400">Structured outcome & audit summary</p>
          </div>
        </div>

        {/* PR Action Button */}
        {isSuccess && !prSuccessUrl && (
          <button
            onClick={onCreatePR}
            className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-500 hover:from-emerald-500 hover:to-teal-400 text-white font-semibold text-xs flex items-center gap-2 shadow-lg shadow-emerald-600/20 hover:shadow-emerald-500/30 transition-all group"
          >
            <GitPullRequest className="w-4 h-4 group-hover:scale-110 transition-transform" />
            <span>Review & Create PR</span>
          </button>
        )}

        {prSuccessUrl && (
          <a
            href={prSuccessUrl}
            target="_blank"
            rel="noreferrer"
            className="px-4 py-2 rounded-xl bg-indigo-600/20 hover:bg-indigo-600/30 border border-indigo-500/40 text-indigo-300 text-xs font-semibold flex items-center gap-2 transition-colors"
          >
            <Check className="w-4 h-4 text-emerald-400" />
            <span>View Created PR on GitHub &rarr;</span>
          </a>
        )}
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 py-5 border-b border-white/5">
        {/* Confidence Score */}
        <div className="p-3.5 rounded-xl bg-surface-100/80 border border-white/5">
          <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5 mb-1">
            <Gauge className="w-3.5 h-3.5 text-indigo-400" />
            Confidence
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-xl font-bold text-white font-mono">{confidence}%</span>
            <span className={`text-[11px] font-medium ${
              confidence >= 80 ? "text-emerald-400" : confidence >= 50 ? "text-amber-400" : "text-rose-400"
            }`}>
              {confidence >= 80 ? "high" : confidence >= 50 ? "medium" : "low"}
            </span>
          </div>
        </div>

        {/* Tests Status */}
        <div className="p-3.5 rounded-xl bg-surface-100/80 border border-white/5">
          <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5 mb-1">
            <ShieldCheck className="w-3.5 h-3.5 text-cyan-400" />
            Test Suite
          </div>
          <div className="text-xl font-bold font-mono">
            {run.tests_passed === true ? (
              <span className="text-emerald-400">PASSED</span>
            ) : run.tests_passed === false ? (
              <span className="text-rose-400">FAILED</span>
            ) : (
              <span className="text-slate-400 text-sm">N/A</span>
            )}
          </div>
        </div>

        {/* Files Changed Count */}
        <div className="p-3.5 rounded-xl bg-surface-100/80 border border-white/5">
          <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5 mb-1">
            <FileCode className="w-3.5 h-3.5 text-amber-400" />
            Files Changed
          </div>
          <div className="text-xl font-bold text-white font-mono">
            {run.files_changed ? run.files_changed.length : 0}
          </div>
        </div>

        {/* Isolation Boundary */}
        <div className="p-3.5 rounded-xl bg-surface-100/80 border border-white/5">
          <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5 mb-1">
            <Bot className="w-3.5 h-3.5 text-purple-400" />
            Sandbox
          </div>
          <div className="text-sm font-semibold text-cyan-300">
            Network Isolated
          </div>
        </div>
      </div>

      {/* Summary Content */}
      <div className="pt-4 space-y-3">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
          Executive Summary
        </h4>
        <div className="p-4 rounded-xl bg-surface-100/90 border border-white/5 text-slate-300 text-sm leading-relaxed font-sans whitespace-pre-wrap">
          {run.summary || run.error_message || "No detailed summary provided."}
        </div>
      </div>
    </div>
  );
};
