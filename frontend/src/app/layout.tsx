import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/lib/auth-context";
import { RunProvider } from "@/lib/run-context";
import { Navbar } from "@/components/Navbar";

export const metadata: Metadata = {
  title: "Forge — Autonomous AI Coding Agent",
  description: "Autonomous multi-provider coding agent running inside a hardened, isolated sandbox.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-background text-slate-100 min-h-screen flex flex-col font-sans antialiased selection:bg-indigo-500/30 selection:text-indigo-200">
        <AuthProvider>
          <RunProvider>
          <Navbar />
          <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 lg:p-8">
            {children}
          </main>
          </RunProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
