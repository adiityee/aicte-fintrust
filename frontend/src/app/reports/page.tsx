"use client";

import React, { useState } from "react";
import { useApp } from "@/context/AppContext";
import { formatINR, formatINRCompact, formatDate } from "@/lib/utils";
import { StatCard } from "@/components/ui/StatCard";
import {
  BarChart3,
  Download,
  Building,
  Landmark,
  TrendingUp,
  Clock,
  ShieldCheck,
  FileSpreadsheet,
  CheckCircle2,
} from "lucide-react";

export default function ReportsPage() {
  const { fdrs, stats } = useApp();
  const [selectedState, setSelectedState] = useState<string>("ALL");

  // Group by institution
  const institutionExposure = fdrs.reduce((acc, curr) => {
    if (!acc[curr.institution_name]) {
      acc[curr.institution_name] = {
        name: curr.institution_name,
        state: curr.state,
        aicte_id: curr.aicte_permanent_id,
        activeAmount: 0,
        releasedAmount: 0,
        count: 0,
      };
    }
    if (curr.status === "RELEASED") {
      acc[curr.institution_name].releasedAmount += curr.principal_amount;
    } else {
      acc[curr.institution_name].activeAmount += curr.principal_amount;
    }
    acc[curr.institution_name].count += 1;
    return acc;
  }, {} as Record<string, any>);

  const instList = Object.values(institutionExposure).filter(
    (item) => selectedState === "ALL" || item.state === selectedState
  );

  // Group by Bank
  const bankExposure = fdrs.reduce((acc, curr) => {
    if (!acc[curr.bank_name]) {
      acc[curr.bank_name] = { name: curr.bank_name, totalAmount: 0, count: 0 };
    }
    acc[curr.bank_name].totalAmount += curr.principal_amount;
    acc[curr.bank_name].count += 1;
    return acc;
  }, {} as Record<string, any>);

  const bankList = Object.values(bankExposure);

  const handleExportReportCSV = () => {
    const headers = [
      "Institution Name",
      "AICTE Permanent ID",
      "State",
      "Active Held Deposit (INR)",
      "Released Deposit (INR)",
      "Total Instruments Registered",
    ];

    const rows = instList.map((i) => [
      `"${i.name.replace(/"/g, '""')}"`,
      i.aicte_id,
      i.state,
      i.activeAmount,
      i.releasedAmount,
      i.count,
    ]);

    const csvContent =
      "data:text/csv;charset=utf-8," +
      [headers.join(","), ...rows.map((e) => e.join(","))].join("\n");

    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute(
      "download",
      `AICTE_FinTrust_Institutional_Exposure_Report_${new Date().toISOString().split("T")[0]}.csv`
    );
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="space-y-6 pb-12 animate-fade-in">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl sm:text-2xl font-bold text-slate-900 tracking-tight">
              Statutory Exposure & Bureau Analytics
            </h1>
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-slate-100 text-slate-800 font-bold border border-slate-200">
              Audit Standard
            </span>
          </div>
          <p className="text-xs text-slate-500">
            Institutional exposure aggregation, banking concentration risks, and statutory release reconciliation
          </p>
        </div>

        <button
          onClick={handleExportReportCSV}
          className="inline-flex items-center gap-2 px-3.5 py-2 bg-white hover:bg-slate-50 border border-slate-200 text-slate-700 text-xs font-semibold rounded-lg shadow-subtle transition-all self-start sm:self-auto"
        >
          <FileSpreadsheet className="w-4 h-4 text-emerald-600" />
          <span>Download Exposure CSV Report</span>
        </button>
      </div>

      {/* Summary Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatCard
          title="Currently Held Active Exposure"
          value={formatINRCompact(stats.activeExposure)}
          subtitle="Total live lien under custody"
          icon={TrendingUp}
          badge="Live Custody"
          badgeType="success"
        />
        <StatCard
          title="Total Formally Released"
          value={formatINRCompact(stats.releasedExposure)}
          subtitle="NOC issued & lien revoked"
          icon={CheckCircle2}
          badge="NOC Cleared"
          badgeType="neutral"
        />
        <StatCard
          title="Cumulative Managed Sum"
          value={formatINRCompact(stats.totalExposure)}
          subtitle="Active + Released combined"
          icon={Landmark}
          badge="Total Volume"
          badgeType="info"
        />
      </div>

      {/* Institutional Breakdown Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-subtle overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-bold text-slate-900">
              Security Deposit Exposure by Technical Institution
            </h3>
            <p className="text-xs text-slate-500">
              Aggregated principal holding and release accounting per approved college
            </p>
          </div>

          <div className="flex items-center gap-2 text-xs">
            <span className="text-slate-500">Filter by State:</span>
            <select
              value={selectedState}
              onChange={(e) => setSelectedState(e.target.value)}
              className="px-2.5 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-slate-800 font-medium"
            >
              <option value="ALL">All States</option>
              <option value="Delhi">Delhi</option>
              <option value="Maharashtra">Maharashtra</option>
              <option value="Tamil Nadu">Tamil Nadu</option>
              <option value="Karnataka">Karnataka</option>
              <option value="West Bengal">West Bengal</option>
              <option value="Punjab">Punjab</option>
            </select>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-700">
            <thead className="bg-slate-50 text-slate-600 uppercase text-[10px] font-bold tracking-wider border-b border-slate-200">
              <tr>
                <th className="py-3 px-4">Institution Name</th>
                <th className="py-3 px-4">Permanent ID</th>
                <th className="py-3 px-4">State</th>
                <th className="py-3 px-4">Active Held Deposit (INR)</th>
                <th className="py-3 px-4">Released Deposit (INR)</th>
                <th className="py-3 px-4 text-center">Instruments</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {instList.map((inst, i) => (
                <tr key={i} className="hover:bg-slate-50/70 transition-colors">
                  <td className="py-3.5 px-4 font-bold text-slate-900">
                    {inst.name}
                  </td>
                  <td className="py-3.5 px-4 font-mono text-slate-500">
                    {inst.aicte_id}
                  </td>
                  <td className="py-3.5 px-4 text-slate-600">
                    {inst.state}
                  </td>
                  <td className="py-3.5 px-4 font-bold font-mono text-emerald-700">
                    {formatINR(inst.activeAmount)}
                  </td>
                  <td className="py-3.5 px-4 font-mono text-slate-400">
                    {inst.releasedAmount > 0 ? formatINR(inst.releasedAmount) : "₹ 0.00"}
                  </td>
                  <td className="py-3.5 px-4 text-center font-mono font-bold text-slate-800">
                    {inst.count}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Banking Concentration Exposure */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-subtle space-y-4">
        <div>
          <h3 className="text-sm font-bold text-slate-900">
            Scheduled Bank Concentration Distribution
          </h3>
          <p className="text-xs text-slate-500">
            Lien custody distribution across participating scheduled commercial banks
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {bankList.map((bank, i) => (
            <div
              key={i}
              className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 flex items-center justify-between text-xs"
            >
              <div>
                <span className="font-bold text-slate-800 block">
                  {bank.name}
                </span>
                <span className="text-[11px] text-slate-500">
                  {bank.count} Fixed Receipts Held
                </span>
              </div>
              <div className="text-right">
                <span className="font-mono font-bold text-slate-900 block">
                  {formatINRCompact(bank.totalAmount)}
                </span>
                <span className="text-[10px] text-slate-400">
                  {formatINR(bank.totalAmount)}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
