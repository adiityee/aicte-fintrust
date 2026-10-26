"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useApp } from "@/context/AppContext";
import { formatINR, formatINRCompact, formatDate, getOverallProvenance } from "@/lib/utils";
import { StatCard } from "@/components/ui/StatCard";
import { BadgeStatus } from "@/components/ui/BadgeStatus";
import { BadgeProvenance } from "@/components/ui/BadgeProvenance";
import {
  ShieldCheck,
  AlertTriangle,
  FolderArchive,
  Clock,
  ArrowRight,
  TrendingUp,
  FileCheck2,
  KeyRound,
  FilePlus,
  Building,
  CheckCircle2,
  AlertOctagon,
  ScanSearch,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from "recharts";

export default function CommandOverview() {
  const { stats, fdrs, alerts, role } = useApp();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Compute status counts for charts
  const statusCounts = fdrs.reduce((acc, curr) => {
    acc[curr.status] = (acc[curr.status] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  const pieData = [
    { name: "Active (Lien)", value: statusCounts["ACTIVE"] || 0, color: "#059669" },
    { name: "Under Scrutiny", value: (statusCounts["UNDER_SCRUTINY"] || 0) + (statusCounts["SUBMITTED"] || 0), color: "#D97706" },
    { name: "Release Gate", value: (statusCounts["RELEASE_REQUESTED"] || 0) + (statusCounts["CLEARANCES_APPROVED"] || 0), color: "#2563EB" },
    { name: "Bank Pending", value: statusCounts["BANK_VERIFICATION_PENDING"] || 0, color: "#8B5CF6" },
    { name: "Matured", value: statusCounts["MATURED"] || 0, color: "#EA580C" },
    { name: "Released", value: statusCounts["RELEASED"] || 0, color: "#64748B" },
  ].filter((d) => d.value > 0);

  // Maturity runway data (Next 6 quarters/months)
  const runwayData = [
    { period: "Nov 2026", amount: 3500000, count: 1, label: "VJTI Mumbai" },
    { period: "Dec 2026", amount: 0, count: 0, label: "None" },
    { period: "Jan 2027", amount: 0, count: 0, label: "None" },
    { period: "Feb 2027", amount: 0, count: 0, label: "None" },
    { period: "Mar 2027", amount: 5000000, count: 1, label: "CEG Anna Univ" },
    { period: "Apr 2027", amount: 1000000, count: 1, label: "DTU Delhi" },
    { period: "Oct 2027", amount: 6000000, count: 2, label: "Heritage + Jadavpur" },
  ];

  // Role-specific action items
  const roleActions = {
    INSTITUTION_ADMIN: [
      {
        title: "Submit New Security Deposit",
        desc: "Upload bank receipt PDF and enter branch particulars for AICTE accreditation.",
        href: "/submit",
        icon: FilePlus,
        badge: "Mandatory Step",
        badgeColor: "bg-blue-50 text-blue-700",
      },
      {
        title: "Track Discrepancy & Query Status",
        desc: "Examine Scrutiny Cell remarks and upload rectified certificate versions.",
        href: "/repository",
        icon: ScanSearch,
        badge: "1 Pending Query",
        badgeColor: "bg-amber-50 text-amber-700",
      },
      {
        title: "Apply for Security Deposit Release",
        desc: "Submit petition for 10-year lock-in maturity return or course closure NOC.",
        href: "/release",
        icon: KeyRound,
        badge: "Clearance Matrix",
        badgeColor: "bg-emerald-50 text-emerald-700",
      },
    ],
    SCRUTINY_OFFICER: [
      {
        title: "Review High Priority Mismatch Case",
        desc: "Delhi Technological University: INR 10,00,000 declared vs INR 1,00,000 OCR text.",
        href: "/scrutiny",
        icon: AlertTriangle,
        badge: "Urgent Mismatch",
        badgeColor: "bg-rose-50 text-rose-700",
      },
      {
        title: "Examine Incremental PDF Revisions",
        desc: "Review multiple %%EOF markers flagged on recently submitted certificates.",
        href: "/scrutiny",
        icon: ScanSearch,
        badge: "Forensics Review",
        badgeColor: "bg-amber-50 text-amber-700",
      },
      {
        title: "Dispatch Signed Link for Bank Verification",
        desc: "Heritage Institute: All OCR checks passed; forward token to SBI branch.",
        href: "/scrutiny",
        icon: ShieldCheck,
        badge: "Ready for Dispatch",
        badgeColor: "bg-blue-50 text-blue-700",
      },
    ],
    CLEARANCE_OFFICER: [
      {
        title: "Pending Vigilance Clearance: Anna University CEG",
        desc: "PGRC, Approval Bureau, Legal & Finance cleared. Vigilance affirmation pending.",
        href: "/release",
        icon: KeyRound,
        badge: "Gatekeeper Lock",
        badgeColor: "bg-amber-50 text-amber-700",
      },
      {
        title: "Verify Student Grievance Records",
        desc: "Ensure zero pending fee refund orders on institution profile.",
        href: "/release",
        icon: FileCheck2,
        badge: "PGRC Bureau",
        badgeColor: "bg-blue-50 text-blue-700",
      },
      {
        title: "Examine Legal Court Cases",
        desc: "Cross-reference High Court petitions prior to releasing statutory lien.",
        href: "/release",
        icon: Clock,
        badge: "Legal Cell",
        badgeColor: "bg-slate-50 text-slate-700",
      },
    ],
    COMPETENT_AUTHORITY: [
      {
        title: "Authorize Final Release: BMS College of Engg",
        desc: "All 5 bureau clearances APPROVED. Statutory authorization lock ready for sign-off.",
        href: "/release",
        icon: KeyRound,
        badge: "Sign-off Ready",
        badgeColor: "bg-emerald-50 text-emerald-800",
      },
      {
        title: "Review Exposure Distribution & Runway",
        desc: "Inspect currently held security deposit exposure (excl. released) vs maturing run.",
        href: "/reports",
        icon: TrendingUp,
        badge: "Executive Summary",
        badgeColor: "bg-blue-50 text-blue-700",
      },
      {
        title: "Verify Audit Ledger Cryptographic Chain",
        desc: "Execute complete SHA-256 traversal from genesis block to current block tip.",
        href: "/repository",
        icon: ShieldCheck,
        badge: "Integrity Verification",
        badgeColor: "bg-purple-50 text-purple-700",
      },
    ],
  }[role];

  return (
    <div className="space-y-8 animate-fade-in pb-12">
      {/* Top Welcome & Perspective Banner */}
      <div className="bg-gradient-to-r from-primary to-[#233C6B] text-white rounded-2xl p-6 sm:p-7 shadow-card relative overflow-hidden">
        <div className="relative z-10 max-w-3xl space-y-2">
          <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-white/10 text-amber-300 text-xs font-semibold backdrop-blur-sm">
            <span className="w-2 h-2 rounded-full bg-amber-400" />
            Active Role: {role.replace(/_/g, " ")} Perspective
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight">
            Security Deposit & FDR Command Overview
          </h1>
          <p className="text-slate-200 text-xs sm:text-sm leading-relaxed">
            Centralized portal for AICTE-approved technical institutions. Every data point carries provenance, releases require parallel 5-bureau clearances, and all state transitions are recorded to an immutable ledger.
          </p>
        </div>

        {/* Decorative background watermark */}
        <div className="absolute right-4 -bottom-10 opacity-10 pointer-events-none hidden md:block">
          <Building className="w-64 h-64 text-white" />
        </div>
      </div>

      {/* Primary Key Exposure Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-5">
        <StatCard
          title="Active Held Exposure"
          value={formatINRCompact(stats.activeExposure)}
          subtitle="Strictly excludes released deposits"
          icon={TrendingUp}
          badge="Live Lien"
          badgeType="success"
        />
        <StatCard
          title="Active Instruments"
          value={`${stats.activeCount} FDRs`}
          subtitle={`Total Registered: ${stats.totalInstruments}`}
          icon={FolderArchive}
          badge={`${stats.releasedExposure > 0 ? "1 Released" : "None Released"}`}
          badgeType="info"
        />
        <StatCard
          title="Maturity Runway (<45d)"
          value={`${stats.maturingSoonCount} FDRs`}
          subtitle="Action required before lapse"
          icon={Clock}
          badge="Approaching"
          badgeType="warning"
        />
        <StatCard
          title="Scrutiny & Discrepancies"
          value={`${stats.discrepancyCount} Flagged`}
          subtitle={`${stats.pendingScrutinyCount} awaiting verification`}
          icon={AlertTriangle}
          badge={stats.discrepancyCount > 0 ? "High Priority" : "Zero Flags"}
          badgeType={stats.discrepancyCount > 0 ? "danger" : "neutral"}
        />
      </div>

      {/* Role-Specific Action Queue */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-bold text-slate-900 tracking-tight flex items-center gap-2">
              <span>Priority Action Queue</span>
              <span className="text-xs px-2 py-0.5 rounded-full bg-primary/10 text-primary font-semibold">
                {role.replace(/_/g, " ")}
              </span>
            </h2>
            <p className="text-xs text-slate-500">
              Immediate operational tasks assigned to your administrative jurisdiction
            </p>
          </div>
          <Link
            href="/alerts"
            className="text-xs font-semibold text-primary hover:underline flex items-center gap-1"
          >
            <span>View All Escalations ({alerts.length})</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {roleActions.map((act, i) => {
            const Icon = act.icon;
            return (
              <Link
                key={i}
                href={act.href}
                className="group bg-white rounded-xl border border-slate-200 p-4 shadow-subtle hover:border-primary/40 hover:shadow-card transition-all flex flex-col justify-between"
              >
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="p-2 rounded-lg bg-slate-50 group-hover:bg-primary/10 text-primary transition-colors">
                      <Icon className="w-4 h-4" />
                    </div>
                    <span
                      className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${act.badgeColor}`}
                    >
                      {act.badge}
                    </span>
                  </div>
                  <h3 className="text-sm font-bold text-slate-900 group-hover:text-primary transition-colors">
                    {act.title}
                  </h3>
                  <p className="text-xs text-slate-500 line-clamp-2">
                    {act.desc}
                  </p>
                </div>
                <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-xs font-semibold text-primary">
                  <span>Open task</span>
                  <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition-transform" />
                </div>
              </Link>
            );
          })}
        </div>
      </div>

      {/* Visual Analytics Grid: Maturity Runway & Status Distribution */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Maturity Runway Bar Chart */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200 p-5 shadow-subtle flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-slate-900">
                  Maturity Runway (Next 12 Months)
                </h3>
                <p className="text-xs text-slate-500">
                  Fixed deposit scheduled maturities by volume and institutional holder
                </p>
              </div>
              <span className="text-[11px] font-medium text-slate-500 bg-slate-50 px-2 py-1 rounded border border-slate-200">
                AICTE Schedule
              </span>
            </div>

            <div className="h-64 mt-4 w-full">
              {mounted ? (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={runwayData} margin={{ top: 10, right: 10, left: 10, bottom: 20 }}>
                    <XAxis dataKey="period" tick={{ fontSize: 11, fill: "#64748B" }} />
                    <YAxis
                      tick={{ fontSize: 11, fill: "#64748B" }}
                      tickFormatter={(v) => `₹${v / 100000}L`}
                    />
                    <Tooltip
                      formatter={(val: any) => [formatINR(Number(val)), "Maturing Exposure"]}
                      labelStyle={{ fontWeight: "bold", color: "#192B52" }}
                      contentStyle={{
                        backgroundColor: "#FFFFFF",
                        borderColor: "#E2E8F0",
                        borderRadius: "8px",
                        fontSize: "12px",
                      }}
                    />
                    <Bar dataKey="amount" fill="#192B52" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-full flex items-center justify-center text-xs text-slate-400">
                  Loading visual analytics...
                </div>
              )}
            </div>
          </div>

          <div className="pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
            <span>Nearest maturity: <strong>VJTI Mumbai (14 Nov 2026)</strong></span>
            <Link href="/reports" className="text-primary font-semibold hover:underline">
              Full schedule report →
            </Link>
          </div>
        </div>

        {/* Status Distribution Donut Chart */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-subtle flex flex-col justify-between">
          <div>
            <h3 className="text-sm font-bold text-slate-900">
              Lifecycle State Distribution
            </h3>
            <p className="text-xs text-slate-500">
              Active instruments across verification stages
            </p>

            <div className="h-48 mt-2 w-full flex items-center justify-center">
              {mounted ? (
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={pieData}
                      dataKey="value"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      innerRadius={45}
                      outerRadius={75}
                      paddingAngle={3}
                    >
                      {pieData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "#FFFFFF",
                        borderColor: "#E2E8F0",
                        borderRadius: "8px",
                        fontSize: "12px",
                      }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <div className="text-xs text-slate-400">Loading chart...</div>
              )}
            </div>

            <div className="space-y-1.5 mt-2">
              {pieData.map((p, i) => (
                <div key={i} className="flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2">
                    <span
                      className="w-2.5 h-2.5 rounded-full shrink-0"
                      style={{ backgroundColor: p.color }}
                    />
                    <span className="text-slate-600 truncate">{p.name}</span>
                  </div>
                  <span className="font-semibold text-slate-900 font-mono">
                    {p.value}
                  </span>
                </div>
              ))}
            </div>
          </div>

          <div className="pt-3 border-t border-slate-100 text-[11px] text-slate-400 text-center">
            Updated live from state transitions
          </div>
        </div>
      </div>

      {/* Recent Key Instruments Preview */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-subtle overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-bold text-slate-900">
              Active Security Deposit Instruments
            </h3>
            <p className="text-xs text-slate-500">
              Latest deposits submitted and tracked under AICTE jurisdiction
            </p>
          </div>
          <Link
            href="/repository"
            className="text-xs font-semibold text-primary hover:underline flex items-center gap-1"
          >
            <span>Open Instrument Repository</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-700">
            <thead className="bg-slate-50 text-slate-600 uppercase text-[10px] font-bold tracking-wider border-b border-slate-200">
              <tr>
                <th className="py-3 px-4">Instrument / FDR #</th>
                <th className="py-3 px-4">Institution Name</th>
                <th className="py-3 px-4">Issuing Bank</th>
                <th className="py-3 px-4">Principal (INR)</th>
                <th className="py-3 px-4">Maturity Date</th>
                <th className="py-3 px-4">Provenance</th>
                <th className="py-3 px-4">Lifecycle Status</th>
                <th className="py-3 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {fdrs.slice(0, 5).map((f) => {
                const { sourceType: provSource, confidenceScore: provScore } =
                  getOverallProvenance(f.provenance_records);

                return (
                  <tr key={f.id} className="hover:bg-slate-50/70 transition-colors">
                    <td className="py-3 px-4 font-mono font-bold text-primary">
                      {f.fdr_number}
                    </td>
                    <td className="py-3 px-4 max-w-xs">
                      <div className="font-semibold text-slate-900 truncate">
                        {f.institution_name}
                      </div>
                      <div className="text-[10px] text-slate-400 font-mono">
                        {f.aicte_permanent_id} · {f.state}
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <div className="font-medium text-slate-800">{f.bank_name}</div>
                      <div className="text-[10px] text-slate-400 font-mono">
                        {f.ifsc_code}
                      </div>
                    </td>
                    <td className="py-3 px-4 font-semibold font-mono text-slate-900">
                      {formatINR(f.principal_amount)}
                    </td>
                    <td className="py-3 px-4 whitespace-nowrap text-slate-600">
                      {formatDate(f.maturity_date)}
                    </td>
                    <td className="py-3 px-4">
                      <BadgeProvenance
                        sourceType={provSource}
                        confidenceScore={provScore}
                        size="sm"
                      />
                    </td>
                    <td className="py-3 px-4">
                      <BadgeStatus status={f.status} size="sm" />
                    </td>
                    <td className="py-3 px-4 text-right">
                      <Link
                        href={
                          f.status === "UNDER_SCRUTINY"
                            ? "/scrutiny"
                            : f.status === "RELEASE_REQUESTED" ||
                              f.status === "CLEARANCES_APPROVED"
                            ? "/release"
                            : `/repository?search=${f.fdr_number}`
                        }
                        className="text-xs font-semibold text-primary hover:underline"
                      >
                        Inspect →
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
