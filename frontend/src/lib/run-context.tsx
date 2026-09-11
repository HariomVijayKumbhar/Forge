"use client";

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { api, ApiError } from "@/lib/api";
import { subscribeToAgentStream } from "@/lib/sse";
import { AgentRun, AgentStep, AgentStatus } from "@/lib/types";

const ACTIVE_RUN_KEY = "forge.activeRunId";

interface RunContextValue {
  activeRunId: string | null;
  currentRun: AgentRun | null;
  steps: AgentStep[];
  isSubmitting: boolean;
  runStatus: AgentStatus;
  isTerminal: boolean;
  startRun: (repoUrl: string, task: string, provider?: string) => Promise<void>;
  cancelRun: () => Promise<void>;
  clearActiveRun: () => void;
}

const RunContext = createContext<RunContextValue | null>(null);

const TERMINAL_STATUSES = [
  "success",
  "error",
  "stopped",
  "stuck",
  "provider_unavailable",
];

export function RunProvider({ children }: { children: React.ReactNode }) {
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [currentRun, setCurrentRun] = useState<AgentRun | null>(null);
  const [steps, setSteps] = useState<AgentStep[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Keep a ref of the run id so SSE callbacks never see stale state.
  const activeRunIdRef = useRef<string | null>(null);
  activeRunIdRef.current = activeRunId;

  const fetchRunDetails = useCallback(async (runId: string) => {
    try {
      const run = await api.getRun(runId);
      setCurrentRun(run);
    } catch (err) {
      // 404 -> run no longer exists (e.g. expired session); drop it.
      if (err instanceof ApiError && err.status === 404) {
        sessionStorage.removeItem(ACTIVE_RUN_KEY);
        setActiveRunId(null);
        setCurrentRun(null);
        setSteps([]);
      } else {
        console.error("Error fetching run details:", err);
      }
    }
  }, []);

  // --- Restore an in-flight run after navigation or full page reload ---
  useEffect(() => {
    if (typeof window === "undefined") return;
    const saved = sessionStorage.getItem(ACTIVE_RUN_KEY);
    if (!saved) return;

    (async () => {
      try {
        const run = await api.getRun(saved);
        setActiveRunId(saved);
        setCurrentRun(run);
        // The SSE stream replays all persisted steps from the DB on
        // (re)connect, so steps lost during navigation are restored here.
        if (!TERMINAL_STATUSES.includes(run.status)) {
          // still running -> keep id so the SSE effect below subscribes
        }
      } catch {
        sessionStorage.removeItem(ACTIVE_RUN_KEY);
      }
    })();
  }, []);

  // --- Single SSE subscription owned by the provider ---
  useEffect(() => {
    if (!activeRunId) return;

    const unsubscribe = subscribeToAgentStream(activeRunId, {
      onStep: (newStep) => {
        setSteps((prev) => {
          if (prev.some((s) => s.id === newStep.id)) return prev;
          return [...prev, newStep];
        });
        if (newStep.action_type === "finish" && activeRunIdRef.current) {
          fetchRunDetails(activeRunIdRef.current);
        }
      },
      onError: (err) => {
        console.error("SSE stream error:", err);
      },
      onComplete: () => {
        if (activeRunIdRef.current) fetchRunDetails(activeRunIdRef.current);
      },
    });

    return () => unsubscribe();
  }, [activeRunId, fetchRunDetails]);

  const startRun = useCallback(
    async (repoUrl: string, task: string, provider?: string) => {
      setIsSubmitting(true);
      setCurrentRun(null);
      setSteps([]);

      try {
        const res = await api.startRun(repoUrl, task, provider);
        sessionStorage.setItem(ACTIVE_RUN_KEY, res.run_id);
        setActiveRunId(res.run_id);
        setCurrentRun({
          id: res.run_id,
          repo_url: repoUrl,
          task,
          status: "running",
          created_at: new Date().toISOString(),
        });
      } finally {
        setIsSubmitting(false);
      }
    },
    []
  );

  const cancelRun = useCallback(async () => {
    if (!activeRunId) return;
    try {
      await api.cancelRun(activeRunId);
    } catch (err) {
      console.error("Cancel error:", err);
    }
  }, [activeRunId]);

  const clearActiveRun = useCallback(() => {
    sessionStorage.removeItem(ACTIVE_RUN_KEY);
    setActiveRunId(null);
    setCurrentRun(null);
    setSteps([]);
  }, []);

  const runStatus: AgentStatus = currentRun?.status || (activeRunId ? "running" : "idle");
  const isTerminal = TERMINAL_STATUSES.includes(runStatus);

  const value = useMemo(
    () => ({
      activeRunId,
      currentRun,
      steps,
      isSubmitting,
      runStatus,
      isTerminal,
      startRun,
      cancelRun,
      clearActiveRun,
    }),
    [
      activeRunId,
      currentRun,
      steps,
      isSubmitting,
      runStatus,
      isTerminal,
      startRun,
      cancelRun,
      clearActiveRun,
    ]
  );

  return <RunContext.Provider value={value}>{children}</RunContext.Provider>;
}

export function useRun(): RunContextValue {
  const ctx = useContext(RunContext);
  if (!ctx) throw new Error("useRun must be used within <RunProvider>");
  return ctx;
}
