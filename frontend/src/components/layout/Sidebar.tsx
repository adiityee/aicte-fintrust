"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useApp } from "@/context/AppContext";
import {
  LayoutDashboard,
  FolderArchive,
  FilePlus2,
  ScanSearch,
  KeyRound,
  AlertOctagon,
  BarChart3,
  SearchCheck,
  ShieldAlert,
  FileLock2,
  Building2,
} from "lucide-react";

interface NavItem {
  title: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: string;
  badgeType?: "warning" | "info" | "success" | "critical";
  roles?: string[];
}

export const Sidebar: React.FC = () => {
  const pathname = usePathname();
  const { role, stats, fdrs, alerts } = useApp();

  const unacknowledgedAlerts = alerts.filter((a) => !a.acknowledged).length;

  const navItems: NavItem[] = [
    {
      title: "Command Overview",
      href: "/",
      icon: LayoutDashboard,
    },
    {
      title: "Instrument Repository",
      href: "/repository",
      icon: FolderArchive,
      badge: `${stats.totalInstruments}`,
      badgeType: "info",
    },
    {
      title: "Institution Submission",
      href: "/submit",
      icon: FilePlus2,
      roles: ["INSTITUTION_ADMIN", "COMPETENT_AUTHORITY"],
    },
    {
      title: "Scrutiny Console",
      href: "/scrutiny",
      icon: ScanSearch,
      badge: stats.pendingScrutinyCount > 0 ? `${stats.pendingScrutinyCount}` : undefined,
      badgeType: "warning",
      roles: ["SCRUTINY_OFFICER", "COMPETENT_AUTHORITY"],
    },
    {
      title: "Release & Refund Gate",
      href: "/release",
      icon: KeyRound,
      badge: stats.pendingClearancesCount > 0 ? `${stats.pendingClearancesCount}` : undefined,
      badgeType: stats.pendingClearancesCount > 0 ? "warning" : "info",
      roles: ["CLEARANCE_OFFICER", "COMPETENT_AUTHORITY", "INSTITUTION_ADMIN"],
    },
    {
      title: "Alerts & Escalation",
      href: "/alerts",
      icon: AlertOctagon,
      badge: unacknowledgedAlerts > 0 ? `${unacknowledgedAlerts}` : undefined,
      badgeType: unacknowledgedAlerts > 0 ? "critical" : undefined,
    },
    {
      title: "Reports & Analytics",
      href: "/reports",
      icon: BarChart3,
    },
    {
      title: "Public Verification",
      href: "/verify",
      icon: SearchCheck,
    },
  ];

  return (
    <aside className="w-64 bg-white border-r border-slate-200 shrink-0 hidden lg:flex flex-col justify-between min-h-[calc(100vh-6.5rem)]">
      <div className="p-4 space-y-6">
        {/* Role contextual card */}
        <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl space-y-1.5">
          <div className="flex items-center justify-between">
            <span className="text-[10px] uppercase font-bold tracking-wider text-slate-500">
              Active Scope
            </span>
            <span className="text-[10px] font-semibold text-primary px-1.5 py-0.5 rounded bg-primary/10">
              {role === "INSTITUTION_ADMIN"
                ? "Institution"
                : role === "SCRUTINY_OFFICER"
                ? "Scrutiny Cell"
                : role === "CLEARANCE_OFFICER"
                ? "Vigilance Cell"
                : "Executive Desk"}
            </span>
          </div>
          <div className="text-xs font-semibold text-slate-900 truncate">
            {role === "INSTITUTION_ADMIN"
              ? "Delhi Tech University"
              : role === "SCRUTINY_OFFICER"
              ? "Dual-Pass OCR Console"
              : role === "CLEARANCE_OFFICER"
              ? "Multi-Bureau Clearance"
              : "Member Secretary AICTE"}
          </div>
          <p className="text-[11px] text-slate-500 leading-tight">
            {role === "INSTITUTION_ADMIN"
              ? "Permanent ID: AICTE-1-102938471"
              : role === "SCRUTINY_OFFICER"
              ? "Queue: 1 flagged discrepancy"
              : role === "CLEARANCE_OFFICER"
              ? "Cell: Vigilance clearance gate"
              : "Statutory release authority"}
          </p>
        </div>

        {/* Navigation list */}
        <nav className="space-y-1">
          {navItems.map((item) => {
            const isActive = pathname === item.href;
            const isRelevant = !item.roles || item.roles.includes(role);
            const Icon = item.icon;

            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center justify-between px-3 py-2.5 rounded-lg text-xs font-medium transition-colors ${
                  isActive
                    ? "bg-primary text-white shadow-sm font-semibold"
                    : isRelevant
                    ? "text-slate-700 hover:bg-slate-100 hover:text-slate-900"
                    : "text-slate-400 hover:bg-slate-50 hover:text-slate-600"
                }`}
              >
                <div className="flex items-center gap-3">
                  <Icon
                    className={`w-4 h-4 ${
                      isActive
                        ? "text-white"
                        : isRelevant
                        ? "text-slate-500"
                        : "text-slate-400"
                    }`}
                  />
                  <span>{item.title}</span>
                </div>

                {item.badge && (
                  <span
                    className={`px-1.5 py-0.5 rounded-full text-[10px] font-bold ${
                      isActive
                        ? "bg-white/20 text-white"
                        : item.badgeType === "critical"
                        ? "bg-rose-100 text-rose-700"
                        : item.badgeType === "warning"
                        ? "bg-amber-100 text-amber-800"
                        : "bg-slate-100 text-slate-600"
                    }`}
                  >
                    {item.badge}
                  </span>
                )}
              </Link>
            );
          })}
        </nav>
      </div>

      {/* Bottom Compliance & Security Footnote */}
      <div className="p-4 border-t border-slate-200 bg-slate-50/60 space-y-2">
        <div className="flex items-center gap-2 text-slate-600 text-[11px] font-semibold">
          <FileLock2 className="w-3.5 h-3.5 text-primary" />
          <span>Statutory Compliance</span>
        </div>
        <p className="text-[10px] text-slate-500 leading-normal">
          AICTE Approval Process Handbook (Clause 6.46). All operations cryptographic SHA-256 ledger signed.
        </p>
      </div>
    </aside>
  );
};
