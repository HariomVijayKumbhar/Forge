"use client";

import React, { useState } from "react";
import { Play, Sparkles, Github, Bot, Check, HelpCircle, Layers } from "lucide-react";

interface TaskFormProps {
  onSubmit: (repoUrl: string, task: string, provider?: string) => Promise<void>;
  isLoading: boolean;
}

const PRESET_EXAMPLES = [
  {
    title: "Add Unit Tests",
    repo: "https://github.com/pallets/click",
    task: "Inspect the repository and add unit tests for argument parsing options.",
  },
  {
    title: "Fix Issue / Validation",
    repo: "https://github.com/tiangolo/fastapi",
    task: "Add input validation tests for query parameter parsing.",
  },
  {
    title: "Refactor Linter Issues",
    repo: "https://github.com/psf/requests",
    task: "Run the code linter, identify code style warnings, and clean up imports.",
  },
];

export const TaskForm: React.FC<TaskFormProps> = ({ onSubmit, isLoading }) => {
  const [repoUrl, setRepoUrl] = useState("https://github.com/pallets/click");
  const [task, setTask] = useState("");
  const [provider, setProvider] = useState<string>("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!repoUrl.trim() || !task.trim() || isLoading) return;
    onSubmit(repoUrl.trim(), task.trim(), provider ? provider : undefined);
  };

  const applyPreset = (preset: typeof PRESET_EXAMPLES[0]) => {
    setRepoUrl(preset.repo);
    setTask(preset.task);
  };

  return (
    <div className="w-full glass-panel rounded-2xl p-6 sm:p-7 relative overflow-hidden">
      {/* Background radial glow */}
      <div className="absolute top-0 right-0 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />

      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400">
            <Sparkles className="w-4 h-4" />
          </div>
          <h2 className="text-lg font-bold text-white tracking-tight">Deploy Autonomous Agent</h2>
        </div>

        {/* Quick Presets */}
        <div className="hidden md:flex items-center gap-1.5 text-xs text-slate-400">
          <span className="text-[11px] uppercase tracking-wider font-semibold mr-1">Presets:</span>
          {PRESET_EXAMPLES.map((preset, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => applyPreset(preset)}
              className="px-2.5 py-1 rounded-lg bg-white/5 hover:bg-indigo-500/20 hover:text-indigo-300 border border-white/5 hover:border-indigo-500/30 transition-all"
            >
              {preset.title}
            </button>
          ))}
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Repo URL & Provider Row */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="md:col-span-2">
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
              Public GitHub Repository URL
            </label>
            <div className="relative">
              <input
                type="url"
                required
                value={repoUrl}
                onChange={(e) => setRepoUrl(e.target.value)}
                placeholder="https://github.com/username/repository"
                disabled={isLoading}
                className="w-full px-4 py-2.5 rounded-xl bg-surface-100/90 border border-white/10 text-white placeholder-slate-500 text-sm focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 transition-all font-mono pl-10"
              />
              <Github className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5 flex items-center justify-between">
              <span>LLM Engine</span>
              <span className="text-[10px] text-cyan-400 lowercase font-normal">multi-provider</span>
            </label>
            <div className="relative">
              <select
                value={provider}
                onChange={(e) => setProvider(e.target.value)}
                disabled={isLoading}
                className="w-full px-3.5 py-2.5 rounded-xl bg-surface-100/90 border border-white/10 text-white text-sm focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 transition-all appearance-none cursor-pointer pl-9"
              >
                <option value="">Auto Fallback (Claude &rarr; Gemini)</option>
                <option value="claude">Claude 3.5 Sonnet (Primary)</option>
                <option value="gemini-flash">Gemini 2.0 Flash (Free)</option>
              </select>
              <Bot className="w-4 h-4 text-indigo-400 absolute left-3 top-3 pointer-events-none" />
              <Layers className="w-3.5 h-3.5 text-slate-400 absolute right-3 top-3.5 pointer-events-none" />
            </div>
          </div>
        </div>

        {/* Task Description Prompt */}
        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5 flex items-center justify-between">
            <span>Task Instructions</span>
            <span className="text-[11px] text-slate-500 lowercase font-normal">markdown supported</span>
          </label>
          <textarea
            required
            rows={3}
            value={task}
            onChange={(e) => setTask(e.target.value)}
            placeholder="Describe what the agent should accomplish (e.g. 'Fix the test failures in tests/test_auth.py and verify git diff')..."
            disabled={isLoading}
            className="w-full px-4 py-3 rounded-xl bg-surface-100/90 border border-white/10 text-white placeholder-slate-500 text-sm focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 transition-all resize-none font-sans leading-relaxed"
          />
        </div>

        {/* Submit Bar */}
        <div className="flex items-center justify-between pt-1">
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <span className="w-2 h-2 rounded-full bg-cyan-400" />
            <span>Ephemeral container created on run with --network none</span>
          </div>

          <button
            type="submit"
            disabled={isLoading || !repoUrl.trim() || !task.trim()}
            className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 via-indigo-500 to-cyan-500 hover:from-indigo-500 hover:to-cyan-400 text-white font-semibold text-sm flex items-center gap-2 shadow-lg shadow-indigo-600/20 hover:shadow-indigo-500/30 transition-all disabled:opacity-50 disabled:cursor-not-allowed group"
          >
            <Play className="w-4 h-4 fill-white group-hover:scale-110 transition-transform" />
            <span>{isLoading ? "Agent Running..." : "Start Agent Run"}</span>
          </button>
        </div>
      </form>
    </div>
  );
};
