"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { Terminal, Shield, History, Lock, Cpu, LogOut, CheckCircle2, BarChart3 } from "lucide-react";

export const Navbar = () => {
  const { isAuthenticated, user, logout } = useAuth();
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-40 w-full glass-panel border-b border-white/5 px-6 py-3.5">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        {/* Logo & Brand */}
        <Link href="/" className="flex items-center gap-3 group">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 via-indigo-500 to-cyan-400 flex items-center justify-center shadow-lg shadow-indigo-500/20 group-hover:scale-105 transition-transform duration-200">
            <Terminal className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-lg text-white tracking-tight">Forge</span>
              <span className="text-[10px] uppercase font-semibold tracking-wider px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                Sandbox v2
              </span>
            </div>
            <p className="text-xs text-slate-400 font-medium">Autonomous Multi-Provider Coding Agent</p>
          </div>
        </Link>

        {/* Navigation & Controls */}
        <div className="flex items-center gap-3">
          {isAuthenticated && (
            <>
              <Link
                href="/"
                className={`px-3.5 py-1.5 rounded-lg text-sm font-medium transition-all flex items-center gap-2 ${
                  pathname === "/"
                    ? "bg-indigo-600/20 text-indigo-300 border border-indigo-500/30"
                    : "text-slate-400 hover:text-white hover:bg-white/5"
                }`}
              >
                <Cpu className="w-4 h-4" />
                Workspace
              </Link>
              <Link
                href="/history"
                className={`px-3.5 py-1.5 rounded-lg text-sm font-medium transition-all flex items-center gap-2 ${
                  pathname === "/history"
                    ? "bg-indigo-600/20 text-indigo-300 border border-indigo-500/30"
                    : "text-slate-400 hover:text-white hover:bg-white/5"
                }`}
              >
                <History className="w-4 h-4" />
                Run History
              </Link>
              <Link
                href="/analytics"
                className={`px-3.5 py-1.5 rounded-lg text-sm font-medium transition-all flex items-center gap-2 ${
                  pathname === "/analytics"
                    ? "bg-indigo-600/20 text-indigo-300 border border-indigo-500/30"
                    : "text-slate-400 hover:text-white hover:bg-white/5"
                }`}
              >
                <BarChart3 className="w-4 h-4" />
                Analytics
              </Link>

              <div className="h-5 w-[1px] bg-white/10 mx-1" />

              {user?.username && (
                <span className="text-sm text-slate-300 font-medium">
                  {user.username}
                </span>
              )}

              {/* Status Badge */}
              <div className="hidden sm:flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-medium">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                Docker Sandbox Active
              </div>

              {/* Logout Button */}
              <button
                onClick={() => logout()}
                className="px-3 py-1.5 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 transition-colors text-sm font-medium flex items-center gap-1.5"
                title="Logout session"
              >
                <LogOut className="w-4 h-4" />
                <span className="hidden sm:inline">Logout</span>
              </button>
            </>
          )}

          {!isAuthenticated && (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-300 text-xs font-medium">
              <Lock className="w-3.5 h-3.5" />
              Authentication Required
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
