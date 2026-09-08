"use client";

import React, { useState, useEffect, useRef } from "react";
import { AgentStep, AgentStatus } from "@/lib/types";
import {
  Terminal,
  CheckCircle2,
  AlertCircle,
  Clock,
  Ban,
  ChevronDown,
  ChevronRight,
  Cpu,
  StopCircle,
  FileCode,
  Search,
  CheckSquare,
  GitPullRequest,
  GitBranch,
  Eye,
  Bot,
} from "lucide-react";

interface LiveStepFeedProps {
  steps: AgentStep[];
  status: AgentStatus;
  onCancel: () => void;
}

export const LiveStepFeed: React.FC<LiveStepFeedProps> = ({ steps, status, onCancel }) => {
  const [expandedSteps, setExpandedSteps] = useState<Record<number, boolean>>({});
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-expand last 2 steps
  useEffect(() => {
    if (steps.length > 0) {
      const lastIndex = steps.length - 1;
      setExpandedSteps((prev) => ({
        ...prev,
        [lastIndex]: true,
      }));
    }
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [steps.length]);

  const toggleExpand = (idx: number) => {
    setExpandedSteps((prev) => ({
      ...prev,
      [idx]: !prev[idx],
    }));
  };

  const getToolIcon = (toolName?: string | null) => {
    switch (toolName) {
      case "read_file":
        return <Eye className="w-4 h-4 text-cyan-400" />;
      case "write_file":
        return <FileCode className="w-4 h-4 text-amber-400" />;
      case "search_code":
        return <Search className="w-4 h-4 text-indigo-400" />;
      case "run_tests":
      case "run_linter":
        return <CheckSquare className="w-4 h-4 text-emerald-400" />;
      case "git_diff":
        return <GitBranch className="w-4 h-4 text-purple-400" />;
      case "github_issue_pr_lookup":
        return <GitPullRequest className="w-4 h-4 text-pink-400" />;
      default:
        return <Terminal className="w-4 h-4 text-slate-400" />;
    }
  };

  const getActionBadge = (actionType: string) => {
    switch (actionType) {
      case "plan":
        return <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">PLAN</span>;
      case "tool_call":
        return <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">TOOL</span>;
      case "reflection":
        return <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-purple-500/10 text-purple-400 border border-purple-500/20">REFLECTION</span>;
      case "finish":
        return <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">COMPLETED</span>;
      case "error":
        return <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20">ERROR</span>;
      case "stuck":
        return <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">STUCK</span>;
      case "stopped":
        return <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-slate-500/10 text-slate-400 border border-slate-500/20">CANCELLED</span>;
      default:
        return <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-slate-500/10 text-slate-400">{actionType.toUpperCase()}</span>;
    }
  };

  return (
    <div className="w-full glass-panel rounded-2xl p-6 flex flex-col h-[580px] relative overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between pb-4 border-b border-white/5 flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400">
            <Cpu className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white tracking-tight flex items-center gap-2">
              Autonomous Agent Execution Stream
              {status === "running" && (
                <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping" />
              )}
            </h3>
            <p className="text-xs text-slate-400">
              Live step stream ({steps.length} steps recorded)
            </p>
          </div>
        </div>

        {/* Controls */}
        {status === "running" && (
          <button
            onClick={onCancel}
            className="px-3 py-1.5 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/20 text-rose-300 text-xs font-semibold flex items-center gap-1.5 transition-colors"
          >
            <StopCircle className="w-4 h-4" />
            <span>Cancel Run</span>
          </button>
        )}
      </div>

      {/* Steps List */}
      <div className="flex-1 overflow-y-auto pt-4 space-y-3 pr-1">
        {steps.length === 0 && (
          <div className="h-full flex flex-col items-center justify-center text-center p-6 text-slate-500">
            <Bot className="w-12 h-12 stroke-1 mb-3 text-slate-600 animate-pulse" />
            <p className="text-sm font-medium text-slate-400">Waiting for agent loop to initialize...</p>
            <p className="text-xs text-slate-500 mt-1 max-w-xs">
              Cloning repository into network-isolated container and analyzing files.
            </p>
          </div>
        )}

        {steps.map((step, idx) => {
          const isExpanded = !!expandedSteps[idx];
          return (
            <div
              key={step.id || idx}
              className={`rounded-xl border transition-all duration-150 ${
                step.status === "error"
                  ? "bg-rose-950/20 border-rose-500/30"
                  : step.action_type === "finish"
                  ? "bg-emerald-950/20 border-emerald-500/30"
                  : "bg-surface-100/70 border-white/5 hover:border-white/10"
              }`}
            >
              {/* Step Header */}
              <div
                onClick={() => toggleExpand(idx)}
                className="px-4 py-3 flex items-center justify-between cursor-pointer select-none"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <span className="text-xs font-mono text-slate-400 w-6">#{step.step_index}</span>
                  {getActionBadge(step.action_type)}
                  {step.tool_name && (
                    <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-surface-200 text-xs font-mono text-slate-200">
                      {getToolIcon(step.tool_name)}
                      <span>{step.tool_name}</span>
                    </div>
                  )}

                  {/* Summary preview */}
                  <span className="text-xs text-slate-300 truncate max-w-md font-sans">
                    {step.tool_output ? step.tool_output.split("\n")[0] : ""}
                  </span>
                </div>

                <div className="flex items-center gap-2 flex-shrink-0">
                  {step.provider_used && (
                    <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
                      {step.provider_used}
                    </span>
                  )}
                  {isExpanded ? (
                    <ChevronDown className="w-4 h-4 text-slate-400" />
                  ) : (
                    <ChevronRight className="w-4 h-4 text-slate-400" />
                  )}
                </div>
              </div>

              {/* Step Body (Expanded) */}
              {isExpanded && (
                <div className="px-4 pb-3.5 pt-1 text-xs border-t border-white/5 space-y-2">
                  {/* Tool Input */}
                  {step.tool_input && (
                    <div>
                      <div className="text-[10px] uppercase tracking-wider font-semibold text-slate-500 mb-1">
                        Arguments
                      </div>
                      <pre className="p-2.5 rounded-lg bg-surface-200/90 text-slate-300 font-mono overflow-x-auto whitespace-pre-wrap max-h-36">
                        {step.tool_input}
                      </pre>
                    </div>
                  )}

                  {/* Tool Output */}
                  {step.tool_output && (
                    <div>
                      <div className="text-[10px] uppercase tracking-wider font-semibold text-slate-500 mb-1">
                        Output / Observation
                      </div>
                      <pre className="p-2.5 rounded-lg bg-background/90 text-emerald-400 font-mono overflow-x-auto whitespace-pre-wrap max-h-48 border border-white/5">
                        {step.tool_output}
                      </pre>
                    </div>
                  )}

                  {/* Timestamp */}
                  <div className="text-[10px] text-slate-500 pt-1 flex items-center justify-between">
                    <span>Status: <strong className="uppercase text-slate-400">{step.status}</strong></span>
                    <span>{new Date(step.timestamp).toLocaleTimeString()}</span>
                  </div>
                </div>
              )}
            </div>
          );
        })}
        <div ref={bottomRef} />
      </div>
    </div>
  );
};
