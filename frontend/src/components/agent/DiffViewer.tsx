"use client";

import React, { useState } from "react";
import { GitBranch, Copy, Check, FileText } from "lucide-react";

interface DiffViewerProps {
  diff?: string | null;
  filesChanged?: string[];
}

export const DiffViewer: React.FC<DiffViewerProps> = ({ diff, filesChanged = [] }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    if (!diff) return;
    navigator.clipboard.writeText(diff);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (!diff || !diff.trim()) {
    return (
      <div className="w-full glass-panel rounded-2xl p-6 flex flex-col items-center justify-center text-center h-64 text-slate-500">
        <GitBranch className="w-10 h-10 stroke-1 text-slate-600 mb-2" />
        <p className="text-sm font-medium text-slate-400">No Git Diff Available</p>
        <p className="text-xs text-slate-500 mt-1">
          Modifications made by the agent will appear here formatted as unified diff chunks.
        </p>
      </div>
    );
  }

  const lines = diff.split("\n");

  return (
    <div className="w-full glass-panel rounded-2xl p-6 flex flex-col h-[580px] overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between pb-3.5 border-b border-white/5 flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400">
            <GitBranch className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white tracking-tight">Modified Changes Diff</h3>
            <p className="text-xs text-slate-400">
              {filesChanged.length} file{filesChanged.length === 1 ? "" : "s"} modified
            </p>
          </div>
        </div>

        <button
          onClick={handleCopy}
          className="px-3 py-1.5 rounded-lg bg-surface-100 hover:bg-surface-200 border border-white/10 text-slate-300 hover:text-white text-xs font-medium flex items-center gap-1.5 transition-colors"
        >
          {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
          <span>{copied ? "Copied" : "Copy Diff"}</span>
        </button>
      </div>

      {/* Changed Files Pill Bar */}
      {filesChanged.length > 0 && (
        <div className="py-2.5 flex items-center gap-2 overflow-x-auto flex-shrink-0 border-b border-white/5">
          <span className="text-[10px] uppercase font-semibold text-slate-500">Files:</span>
          {filesChanged.map((file, idx) => (
            <span
              key={idx}
              className="px-2 py-0.5 rounded bg-surface-200 border border-white/5 text-[11px] font-mono text-slate-300 flex items-center gap-1"
            >
              <FileText className="w-3 h-3 text-cyan-400" />
              {file}
            </span>
          ))}
        </div>
      )}

      {/* Diff Content */}
      <div className="flex-1 overflow-y-auto pt-3 font-mono text-xs leading-relaxed select-text">
        <pre className="p-3.5 rounded-xl bg-background/90 border border-white/5 overflow-x-auto min-h-full">
          {lines.map((line, idx) => {
            let lineStyle = "text-slate-400";
            let bgStyle = "";

            if (line.startsWith("+++") || line.startsWith("---")) {
              lineStyle = "text-slate-300 font-bold";
            } else if (line.startsWith("+")) {
              lineStyle = "text-emerald-300";
              bgStyle = "bg-emerald-950/40";
            } else if (line.startsWith("-")) {
              lineStyle = "text-rose-300";
              bgStyle = "bg-rose-950/40";
            } else if (line.startsWith("@@")) {
              lineStyle = "text-purple-400 font-semibold";
              bgStyle = "bg-purple-950/20";
            }

            return (
              <div key={idx} className={`px-2 py-0.5 rounded ${lineStyle} ${bgStyle}`}>
                {line || " "}
              </div>
            );
          })}
        </pre>
      </div>
    </div>
  );
};
