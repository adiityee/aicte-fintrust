"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useApp } from "@/context/AppContext";
import { formatDate } from "@/lib/utils";
import {
  AlertOctagon,
  Clock,
  AlertTriangle,
  CheckCircle2,
  Filter,
  User,
  Calendar,
  ArrowRight,
  ShieldAlert,
  Flame,
} from "lucide-react";

export default function AlertsPage() {
  const { alerts, acknowledgeAlert } = useApp();
  const [filterUrgency, setFilterUrgency] = useState<string>("ALL");
  const [filterCategory, setFilterCategory] = useState<string>("ALL");

  const filteredAlerts = alerts.filter((a) => {
    const matchesUrgency =
      filterUrgency === "ALL" || a.urgency === filterUrgency;
    const matchesCat =
      filterCategory === "ALL" || a.category === filterCategory;
    return matchesUrgency && matchesCat;
  });

  const getUrgencyBadge = (urgency: string) => {
    switch (urgency) {
      case "CRITICAL":
        return "bg-rose-100 text-rose-800 border-rose-300";
      case "HIGH":
        return "bg-amber-100 text-amber-800 border-amber-300";
      case "MEDIUM":
        return "bg-blue-100 text-blue-800 border-blue-300";
      default:
        return "bg-slate-100 text-slate-700 border-slate-300";
    }
  };

  return (
    <div className="space-y-6 pb-12 animate-fade-in">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl sm:text-2xl font-bold text-slate-900 tracking-tight">
              Actionable Alerts & Compliance Escalations
            </h1>
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-rose-100 text-rose-800 font-bold border border-rose-200">
              Celery Beat & Redis Engine
            </span>
          </div>
          <p className="text-xs text-slate-500">
            Every alert explicitly defines the required action, statutory deadline, assigned owner, and regulatory consequences of delay
          </p>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-subtle flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            <Filter className="w-3.5 h-3.5 text-slate-400" />
            <span className="font-semibold text-slate-600">Urgency:</span>
            <select
              value={filterUrgency}
              onChange={(e) => setFilterUrgency(e.target.value)}
              className="px-2.5 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-slate-800 font-medium"
            >
              <option value="ALL">All Urgencies</option>
              <option value="CRITICAL">Critical</option>
              <option value="HIGH">High</option>
              <option value="MEDIUM">Medium</option>
            </select>
          </div>

          <div className="flex items-center gap-1.5">
            <span className="font-semibold text-slate-600">Category:</span>
            <select
              value={filterCategory}
              onChange={(e) => setFilterCategory(e.target.value)}
              className="px-2.5 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-slate-800 font-medium"
            >
              <option value="ALL">All Categories</option>
              <option value="MATURITY">Maturity Runway</option>
              <option value="DISCREPANCY">Discrepancy / Forensics</option>
              <option value="CLEARANCE">Clearance Gate</option>
            </select>
          </div>
        </div>

        <div className="text-[11px] text-slate-500">
          Total Notifications: <strong>{filteredAlerts.length}</strong>
        </div>
      </div>

      {/* Alerts List */}
      <div className="space-y-4">
        {filteredAlerts.map((item) => {
          return (
            <div
              key={item.id}
              className={`bg-white rounded-xl border p-5 shadow-subtle transition-all space-y-4 ${
                item.acknowledged
                  ? "border-slate-200 opacity-75"
                  : item.urgency === "CRITICAL"
                  ? "border-rose-300 ring-1 ring-rose-200"
                  : "border-slate-200"
              }`}
            >
              {/* Alert Header */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-100 pb-3">
                <div className="flex items-center gap-2.5">
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-bold border uppercase tracking-wider ${getUrgencyBadge(
                      item.urgency
                    )}`}
                  >
                    {item.urgency}
                  </span>
                  <span className="text-xs font-mono font-semibold text-slate-500">
                    #{item.id} · FDR #{item.fdr_number}
                  </span>
                  <span className="text-xs font-semibold text-slate-800">
                    ({item.institution_name})
                  </span>
                </div>

                <div className="flex items-center gap-2 text-xs text-slate-500">
                  <Calendar className="w-3.5 h-3.5 text-slate-400" />
                  <span>
                    Deadline: <strong className="text-slate-800">{formatDate(item.deadline)}</strong>
                  </span>
                </div>
              </div>

              {/* Title & Description */}
              <div className="space-y-1">
                <h3 className="text-sm font-bold text-slate-900">{item.title}</h3>
                <p className="text-xs text-slate-600 leading-relaxed">
                  {item.description}
                </p>
              </div>

              {/* Four Essential Attributes per PS */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 p-3 bg-slate-50 rounded-xl border border-slate-200 text-xs">
                <div>
                  <span className="text-[10px] uppercase font-bold text-slate-400 block">
                    Action Required
                  </span>
                  <p className="font-semibold text-slate-800 mt-0.5">
                    {item.action_required}
                  </p>
                </div>
                <div>
                  <span className="text-[10px] uppercase font-bold text-slate-400 block">
                    Designated Owner
                  </span>
                  <p className="font-semibold text-slate-800 mt-0.5 flex items-center gap-1">
                    <User className="w-3.5 h-3.5 text-primary" />
                    <span>{item.owner}</span>
                  </p>
                </div>
                <div>
                  <span className="text-[10px] uppercase font-bold text-rose-500 block">
                    Consequence of Inaction
                  </span>
                  <p className="text-rose-800 font-medium mt-0.5">
                    {item.consequence}
                  </p>
                </div>
              </div>

              {/* Footer Actions */}
              <div className="flex items-center justify-between pt-1 text-xs">
                <div className="text-[11px] text-slate-400">
                  Logged via AICTE Notification Router · Idempotency enforced
                </div>

                <div className="flex items-center gap-2">
                  {!item.acknowledged ? (
                    <button
                      onClick={() => acknowledgeAlert(item.id)}
                      className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold rounded-lg transition-colors"
                    >
                      Acknowledge Receipt
                    </button>
                  ) : (
                    <span className="text-emerald-700 text-xs font-semibold flex items-center gap-1">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      <span>Acknowledged</span>
                    </span>
                  )}

                  <Link
                    href={
                      item.category === "DISCREPANCY"
                        ? "/scrutiny"
                        : item.category === "CLEARANCE"
                        ? "/release"
                        : `/repository?search=${item.fdr_number}`
                    }
                    className="px-3.5 py-1.5 bg-primary hover:bg-primary-900 text-white font-semibold rounded-lg flex items-center gap-1 shadow-sm transition-colors"
                  >
                    <span>Execute Action</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </Link>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
