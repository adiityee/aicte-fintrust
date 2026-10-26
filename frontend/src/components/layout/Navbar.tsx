"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useApp } from "@/context/AppContext";
import { ROLES } from "@/lib/mockData";
import {
  Shield,
  Layers,
  Bell,
  RefreshCw,
  ChevronDown,
  CheckCircle2,
  AlertTriangle,
  Server,
  Lock,
  X,
  ExternalLink,
  Zap,
} from "lucide-react";

interface NavbarProps {
  onOpenAuditModal: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({ onOpenAuditModal }) => {
  const {
    role,
    setRole,
    alerts,
    appMode,
    setAppMode,
    backendStatus,
    backendError,
    clearBackendError,
    resetAllDemoData,
  } = useApp();
  const [roleDropdownOpen, setRoleDropdownOpen] = useState(false);

  const currentRoleConfig = ROLES.find((r) => r.id === role) || ROLES[0];
  const unacknowledgedAlerts = alerts.filter((a) => !a.acknowledged).length;

  return (
    <header className="sticky top-0 z-40 w-full bg-white border-b border-slate-200 shadow-sm">
      {/* Top micro-bar for Government Portal Identity */}
      <div className="bg-[#0F1C36] text-slate-300 text-[11px] px-4 sm:px-6 py-1.5 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-white tracking-wide">
            GOVERNMENT OF INDIA
          </span>
          <span className="text-slate-500">|</span>
          <span>All India Council for Technical Education (AICTE)</span>
          <span className="text-slate-500">|</span>
          <span className="text-amber-400 font-medium">SIH26265 Protocol</span>
        </div>

        <div className="flex items-center gap-3">
          {/* Active Mode Pill & Switcher */}
          <div className="flex items-center gap-1.5 bg-slate-800/80 px-2 py-0.5 rounded border border-slate-700">
            <span
              className={`w-2 h-2 rounded-full ${
                appMode === "LIVE"
                  ? backendStatus === "ONLINE"
                    ? "bg-emerald-400 animate-pulse"
                    : "bg-rose-500"
                  : "bg-amber-400"
              }`}
            />
            <span className="text-[10px] text-slate-200 font-mono font-semibold">
              {appMode === "LIVE"
                ? backendStatus === "ONLINE"
                  ? "FASTAPI LIVE: CONNECTED"
                  : `FASTAPI LIVE: ${backendStatus}`
                : "DEMO ADAPTER: ACTIVE"}
            </span>

            <button
              onClick={() => setAppMode(appMode === "LIVE" ? "DEMO" : "LIVE")}
              className="ml-1 text-[9px] uppercase font-bold px-1.5 py-0.2 rounded bg-slate-700 hover:bg-slate-600 text-amber-300 transition-colors"
              title="Toggle between Live FastAPI connection and isolated Demo Mode"
            >
              {appMode === "LIVE" ? "Use Demo Mode" : "Connect Live"}
            </button>
          </div>

          <span className="text-slate-500">|</span>
          <span className="text-slate-400 hidden md:inline">
            Security: AES-256 + SHA-256
          </span>
        </div>
      </div>

      {/* Backend Error Alert Banner (Shown if live backend connection fails or errors occur) */}
      {backendError && (
        <div className="bg-rose-50 border-b border-rose-200 px-4 sm:px-6 py-2 flex items-center justify-between text-xs text-rose-800 animate-fade-in">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
            <span className="font-semibold">Live Backend Notice:</span>
            <span>{backendError}</span>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={() => setAppMode("DEMO")}
              className="px-2 py-0.5 rounded bg-rose-200 hover:bg-rose-300 text-rose-900 text-[10px] font-bold"
            >
              Switch to Demo Mode
            </button>
            <button
              onClick={clearBackendError}
              className="p-1 text-rose-500 hover:text-rose-700"
              title="Dismiss notification"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}

      {/* Main Navbar */}
      <div className="px-4 sm:px-6 h-16 flex items-center justify-between">
        {/* Brand identity */}
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-primary flex items-center justify-center text-white shadow-md">
            <Shield className="w-6 h-6 text-amber-300" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-lg font-bold tracking-tight text-primary">
                AICTE FinTrust
              </span>
              <span className="text-[10px] font-semibold uppercase px-2 py-0.5 rounded bg-primary/10 text-primary border border-primary/20">
                Portal SIH26265
              </span>
              {appMode === "DEMO" && (
                <span className="text-[9px] font-mono font-bold uppercase px-1.5 py-0.2 rounded bg-amber-50 text-amber-800 border border-amber-300">
                  Demo Mode
                </span>
              )}
            </div>
            <p className="text-xs text-slate-500 hidden sm:block">
              Security Deposit & Fixed Deposit Receipt Integrity Console
            </p>
          </div>
        </div>

        {/* Center / Right controls */}
        <div className="flex items-center gap-3">
          {/* Audit Chain Verifier Quick Access */}
          <button
            onClick={onOpenAuditModal}
            className="hidden md:inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-primary bg-primary/5 hover:bg-primary/10 border border-primary/20 rounded-lg transition-colors"
            title="Inspect SHA-256 cryptographic audit chain"
          >
            <Layers className="w-3.5 h-3.5" />
            <span>Audit Ledger</span>
          </button>

          {/* Reset Demo Data */}
          <button
            onClick={() => {
              if (confirm("Reset demo data to initial state?")) {
                resetAllDemoData();
              }
            }}
            className="p-1.5 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-lg text-xs"
            title="Reset demo data to initial state"
          >
            <RefreshCw className="w-4 h-4" />
          </button>

          {/* Alerts Bell */}
          <Link
            href="/alerts"
            className="relative p-2 text-slate-600 hover:text-primary hover:bg-slate-100 rounded-lg transition-colors"
            title="View system alerts"
          >
            <Bell className="w-4 h-4" />
            {unacknowledgedAlerts > 0 && (
              <span className="absolute top-1 right-1 w-4 h-4 text-[10px] font-bold text-white bg-rose-600 rounded-full flex items-center justify-center animate-pulse">
                {unacknowledgedAlerts}
              </span>
            )}
          </Link>

          {/* Vertical divider */}
          <div className="h-6 w-px bg-slate-200" />

          {/* Demo Role Switcher */}
          <div className="relative">
            <button
              onClick={() => setRoleDropdownOpen(!roleDropdownOpen)}
              className="flex items-center gap-2.5 px-3 py-1.5 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-lg text-left transition-all"
            >
              <div className="w-2 h-2 rounded-full bg-emerald-500" />
              <div>
                <div className="flex items-center gap-1.5">
                  <span className="text-xs font-bold text-slate-900">
                    {currentRoleConfig.title}
                  </span>
                  <span className="text-[10px] font-medium px-1.5 py-0.2 rounded bg-amber-100 text-amber-900 border border-amber-200">
                    Role Switcher
                  </span>
                </div>
                <div className="text-[10px] text-slate-500 leading-tight">
                  {currentRoleConfig.shortName}
                </div>
              </div>
              <ChevronDown className="w-4 h-4 text-slate-400 ml-1" />
            </button>

            {roleDropdownOpen && (
              <>
                <div
                  className="fixed inset-0 z-40"
                  onClick={() => setRoleDropdownOpen(false)}
                />
                <div className="absolute right-0 mt-2 w-72 bg-white rounded-xl shadow-dropdown border border-slate-200 py-2 z-50">
                  <div className="px-3 py-2 border-b border-slate-100 bg-slate-50/70">
                    <p className="text-xs font-semibold text-slate-800">
                      Select Role Perspective
                    </p>
                    <p className="text-[11px] text-slate-500 mt-0.5">
                      Demo mode: switches view, permissions & queue actions.
                    </p>
                  </div>

                  <div className="py-1">
                    {ROLES.map((r) => {
                      const isSelected = r.id === role;
                      return (
                        <button
                          key={r.id}
                          onClick={() => {
                            setRole(r.id);
                            setRoleDropdownOpen(false);
                          }}
                          className={`w-full px-3 py-2 text-left text-xs flex items-start gap-2.5 hover:bg-slate-50 transition-colors ${
                            isSelected
                              ? "bg-primary/5 text-primary font-semibold"
                              : "text-slate-700"
                          }`}
                        >
                          <div className="mt-0.5">
                            {isSelected ? (
                              <CheckCircle2 className="w-4 h-4 text-primary" />
                            ) : (
                              <div className="w-4 h-4 rounded-full border border-slate-300" />
                            )}
                          </div>
                          <div>
                            <div className="flex items-center gap-1.5">
                              <span>{r.title}</span>
                              <span className="text-[9px] px-1 rounded bg-slate-100 text-slate-600 font-normal">
                                {r.badge}
                              </span>
                            </div>
                            <p className="text-[10px] text-slate-500 mt-0.5 line-clamp-1 font-normal">
                              {r.description}
                            </p>
                          </div>
                        </button>
                      );
                    })}
                  </div>

                  <div className="px-3 py-2 border-t border-slate-100 text-[10px] text-slate-400 bg-slate-50/50">
                    <Lock className="w-3 h-3 inline mr-1 text-slate-400" />
                    Demo switcher: distinct from actual backend authentication and permissions.
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </header>
  );
};
