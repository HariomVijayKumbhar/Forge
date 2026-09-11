"use client";

import React, { useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { AuthGate } from "@/components/auth/AuthGate";
import { TaskForm } from "@/components/agent/TaskForm";
import { LiveStepFeed } from "@/components/agent/LiveStepFeed";
import { DiffViewer } from "@/components/agent/DiffViewer";
import { ResultCard } from "@/components/agent/ResultCard";
import { PRConfirmModal } from "@/components/agent/PRConfirmModal";
import { AuditLogDrawer } from "@/components/agent/AuditLogDrawer";
import { useRun } from "@/lib/run-context";
import { Terminal, GitBranch, Shield } from "lucide-react";

export default function WorkspacePage() {
  const { isAuthenticated, isLoading: isAuthLoading } = useAuth();

  // Run state lives in RunProvider (global) so it survives tab navigation.
  const {
    activeRunId,
    currentRun,
    steps,
    isSubmitting,
    runStatus,
    isTerminal,
    startRun,
    cancelRun,
  } = useRun();

  // Purely local UI state — safe to lose on navigation.
  const [activeTab, setActiveTab] = useState<"steps" | "diff">("steps");
  const [isPRModalOpen, setIsPRModalOpen] = useState(false);
  const [isAuditDrawerOpen, setIsAuditDrawerOpen] = useState(false);
  const [prCreatedUrl, setPrCreatedUrl] = useState<string | null>(null);

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
      {/* Task Submission Form */}
      <TaskForm
        onSubmit={(repoUrl, task, provider) => {
          setPrCreatedUrl(null);
          return startRun(repoUrl, task, provider);
        }}
        isLoading={isSubmitting || runStatus === "running"}
      />

      {/* Main Execution Workspace */}
      {activeRunId && (
        <div className="space-y-6 animate-in fade-in-50 duration-300">
          {/* Action Tabs Bar */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 p-1 rounded-xl bg-surface-100/90 border border-white/5">
              <button
                onClick={() => setActiveTab("steps")}
                className={`px-4 py-2 rounded-lg text-xs font-semibold flex items-center gap-2 transition-all ${activeTab === "steps"
                  ? "bg-indigo-600 text-white shadow-md shadow-indigo-600/20"
                  : "text-slate-400 hover:text-white"
                  }`}
              >
                <Terminal className="w-4 h-4" />
                <span>Live Steps Stream ({steps.length})</span>
              </button>

              <button
                onClick={() => setActiveTab("diff")}
                className={`px-4 py-2 rounded-lg text-xs font-semibold flex items-center gap-2 transition-all ${activeTab === "diff"
                  ? "bg-indigo-600 text-white shadow-md shadow-indigo-600/20"
                  : "text-slate-400 hover:text-white"
                  }`}
              >
                <GitBranch className="w-4 h-4" />
                <span>Unified Git Diff</span>
              </button>
            </div>

            {/* Audit Trail Trigger */}
            <button
              onClick={() => setIsAuditDrawerOpen(true)}
              className="px-3.5 py-2 rounded-xl bg-surface-100 hover:bg-surface-200 border border-white/10 text-slate-300 hover:text-white text-xs font-medium flex items-center gap-1.5 transition-colors"
            >
              <Shield className="w-4 h-4 text-indigo-400" />
              <span>View Security Audit</span>
            </button>
          </div>

          {/* Tab Content */}
          <div>
            {activeTab === "steps" ? (
              <LiveStepFeed steps={steps} status={runStatus} onCancel={cancelRun} />
            ) : (
              <DiffViewer diff={currentRun?.diff} filesChanged={currentRun?.files_changed} />
            )}
          </div>

          {/* Result Card when finished */}
          {currentRun && isTerminal && (
            <ResultCard
              run={currentRun}
              onCreatePR={() => setIsPRModalOpen(true)}
              prSuccessUrl={prCreatedUrl}
            />
          )}
        </div>
      )}

      {/* PR Confirmation Modal */}
      {currentRun && (
        <PRConfirmModal
          isOpen={isPRModalOpen}
          runId={currentRun.id}
          repoUrl={currentRun.repo_url}
          onClose={() => setIsPRModalOpen(false)}
          onSuccess={(url) => setPrCreatedUrl(url)}
        />
      )}

      {/* Security Audit Drawer */}
      {activeRunId && (
        <AuditLogDrawer
          runId={activeRunId}
          isOpen={isAuditDrawerOpen}
          onClose={() => setIsAuditDrawerOpen(false)}
        />
      )}
    </div>
  );
}
