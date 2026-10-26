"use client";

import React, { useState, useMemo } from "react";
import { useApp } from "@/context/AppContext";
import { formatINR, formatDate, truncateHash } from "@/lib/utils";
import { BadgeStatus } from "@/components/ui/BadgeStatus";
import { BadgeProvenance } from "@/components/ui/BadgeProvenance";
import { FDRInstrument, FDRStatus } from "@/types";
import {
  Search,
  Filter,
  Download,
  Eye,
  X,
  FileText,
  Building,
  Landmark,
  ShieldAlert,
  ShieldCheck,
  CheckCircle2,
  Calendar,
  Lock,
  ArrowUpDown,
} from "lucide-react";

export default function RepositoryPage() {
  const { fdrs } = useApp();

  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [bankFilter, setBankFilter] = useState<string>("ALL");
  const [sortField, setSortField] = useState<"amount" | "maturity" | "created">("created");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");
  const [selectedFdr, setSelectedFdr] = useState<FDRInstrument | null>(null);

  // Extract unique banks for dropdown
  const uniqueBanks = useMemo(() => {
    const set = new Set<string>();
    fdrs.forEach((f) => {
      if (f.bank_name) set.add(f.bank_name);
    });
    return Array.from(set);
  }, [fdrs]);

  // Filtered and sorted dataset
  const filteredFdrs = useMemo(() => {
    return fdrs
      .filter((item) => {
        const matchesSearch =
          item.fdr_number.toLowerCase().includes(searchQuery.toLowerCase()) ||
          item.institution_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
          item.aicte_permanent_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
          item.bank_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
          item.ifsc_code.toLowerCase().includes(searchQuery.toLowerCase());

        const matchesStatus =
          statusFilter === "ALL" || item.status === statusFilter;
        const matchesBank =
          bankFilter === "ALL" || item.bank_name === bankFilter;

        return matchesSearch && matchesStatus && matchesBank;
      })
      .sort((a, b) => {
        let valA: any = a.created_at;
        let valB: any = b.created_at;

        if (sortField === "amount") {
          valA = a.principal_amount;
          valB = b.principal_amount;
        } else if (sortField === "maturity") {
          valA = new Date(a.maturity_date).getTime();
          valB = new Date(b.maturity_date).getTime();
        }

        if (sortOrder === "asc") {
          return valA > valB ? 1 : -1;
        } else {
          return valA < valB ? 1 : -1;
        }
      });
  }, [fdrs, searchQuery, statusFilter, bankFilter, sortField, sortOrder]);

  // Export CSV handler
  const handleExportCSV = () => {
    const headers = [
      "FDR Number",
      "Institution Name",
      "AICTE ID",
      "State",
      "Bank Name",
      "IFSC Code",
      "Principal (INR)",
      "Interest Rate (%)",
      "Issue Date",
      "Maturity Date",
      "Lien Holder",
      "Status",
      "SHA256 File Hash",
      "NOC Reference",
    ];

    const rows = filteredFdrs.map((f) => [
      f.fdr_number,
      `"${f.institution_name.replace(/"/g, '""')}"`,
      f.aicte_permanent_id,
      f.state,
      `"${f.bank_name}"`,
      f.ifsc_code,
      f.principal_amount,
      f.interest_rate,
      f.issue_date,
      f.maturity_date,
      `"${f.lien_holder}"`,
      f.status,
      f.document_hash || "",
      f.noc_number || "N/A",
    ]);

    const csvContent =
      "data:text/csv;charset=utf-8," +
      [headers.join(","), ...rows.map((e) => e.join(","))].join("\n");

    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute(
      "download",
      `AICTE_FinTrust_Repository_${new Date().toISOString().split("T")[0]}.csv`
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
          <h1 className="text-xl sm:text-2xl font-bold text-slate-900 tracking-tight">
            Central Instrument & FDR Repository
          </h1>
          <p className="text-xs text-slate-500">
            Immutable register of institutional fixed deposits, bank liens, and digital NOC references
          </p>
        </div>
        <button
          onClick={handleExportCSV}
          className="inline-flex items-center gap-2 px-3.5 py-2 bg-white hover:bg-slate-50 border border-slate-200 text-slate-700 text-xs font-semibold rounded-lg shadow-subtle transition-all self-start sm:self-auto"
        >
          <Download className="w-4 h-4 text-primary" />
          <span>Export CSV Register</span>
        </button>
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-subtle space-y-3">
        <div className="flex flex-col md:flex-row items-center gap-3">
          {/* Search Input */}
          <div className="relative flex-1 w-full">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by FDR #, Institution Name, AICTE Permanent ID, Bank or IFSC..."
              className="w-full pl-9 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary text-slate-900"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery("")}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          {/* Status Dropdown Filter */}
          <div className="flex items-center gap-2 w-full md:w-auto">
            <Filter className="w-4 h-4 text-slate-400 hidden sm:block shrink-0" />
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-xs font-medium text-slate-700 focus:outline-none focus:ring-2 focus:ring-primary/20"
            >
              <option value="ALL">All Lifecycle Statuses</option>
              <option value="DRAFT">Draft</option>
              <option value="SUBMITTED">Submitted</option>
              <option value="UNDER_SCRUTINY">Under Scrutiny</option>
              <option value="QUERY_RAISED">Query Raised</option>
              <option value="BANK_VERIFICATION_PENDING">Bank Verification Pending</option>
              <option value="BANK_VERIFIED">Bank Verified & Lien Affirmed</option>
              <option value="ACTIVE">Active (Lien Locked)</option>
              <option value="MATURED">Matured (Renewal Required)</option>
              <option value="RELEASE_REQUESTED">Release Requested</option>
              <option value="CLEARANCES_APPROVED">Clearances Approved</option>
              <option value="RELEASED">Released (NOC Issued)</option>
            </select>

            {/* Bank Dropdown Filter */}
            <select
              value={bankFilter}
              onChange={(e) => setBankFilter(e.target.value)}
              className="px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-xs font-medium text-slate-700 focus:outline-none focus:ring-2 focus:ring-primary/20"
            >
              <option value="ALL">All Issuing Banks</option>
              {uniqueBanks.map((b) => (
                <option key={b} value={b}>
                  {b}
                </option>
              ))}
            </select>

            {/* Sort Toggle */}
            <button
              onClick={() => {
                if (sortField === "created") setSortField("amount");
                else if (sortField === "amount") setSortField("maturity");
                else setSortField("created");
              }}
              className="px-3 py-2 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-lg text-xs font-medium text-slate-700 flex items-center gap-1.5 shrink-0"
              title="Click to switch sort field"
            >
              <ArrowUpDown className="w-3.5 h-3.5 text-primary" />
              <span>Sort: {sortField.toUpperCase()}</span>
            </button>
          </div>
        </div>

        {/* Counter Pill */}
        <div className="flex items-center justify-between text-[11px] text-slate-500 pt-1">
          <span>
            Showing <strong>{filteredFdrs.length}</strong> of <strong>{fdrs.length}</strong> instruments
          </span>
          {(statusFilter !== "ALL" || bankFilter !== "ALL" || searchQuery) && (
            <button
              onClick={() => {
                setStatusFilter("ALL");
                setBankFilter("ALL");
                setSearchQuery("");
              }}
              className="text-primary hover:underline font-semibold"
            >
              Clear all filters
            </button>
          )}
        </div>
      </div>

      {/* Main Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-subtle overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-700">
            <thead className="bg-slate-50 text-slate-600 uppercase text-[10px] font-bold tracking-wider border-b border-slate-200">
              <tr>
                <th className="py-3 px-4">Instrument / FDR #</th>
                <th className="py-3 px-4">Institution Particulars</th>
                <th className="py-3 px-4">Bank & IFSC</th>
                <th className="py-3 px-4">Principal Amount</th>
                <th className="py-3 px-4">Maturity Date</th>
                <th className="py-3 px-4">Provenance Tag</th>
                <th className="py-3 px-4">Lifecycle State</th>
                <th className="py-3 px-4 text-center">Inspect</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filteredFdrs.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-slate-400">
                    No matching fixed deposit records found.
                  </td>
                </tr>
              ) : (
                filteredFdrs.map((f) => {
                  const provSource =
                    f.provenance_records[0]?.source_type || "INSTITUTION_ENTERED";
                  const provScore = f.provenance_records[0]?.confidence_score;

                  return (
                    <tr
                      key={f.id}
                      onClick={() => setSelectedFdr(f)}
                      className="hover:bg-slate-50/80 cursor-pointer transition-colors"
                    >
                      <td className="py-3.5 px-4 font-mono font-bold text-primary">
                        {f.fdr_number}
                        {f.noc_number && (
                          <div className="text-[10px] text-emerald-700 font-sans font-medium flex items-center gap-0.5 mt-0.5">
                            <CheckCircle2 className="w-3 h-3" />
                            <span>NOC Issued</span>
                          </div>
                        )}
                      </td>
                      <td className="py-3.5 px-4 max-w-xs">
                        <div className="font-semibold text-slate-900 truncate">
                          {f.institution_name}
                        </div>
                        <div className="text-[10px] text-slate-400 font-mono mt-0.5">
                          {f.aicte_permanent_id} · {f.state}
                        </div>
                      </td>
                      <td className="py-3.5 px-4">
                        <div className="font-medium text-slate-800">
                          {f.bank_name}
                        </div>
                        <div className="text-[10px] text-slate-400 font-mono mt-0.5">
                          {f.ifsc_code}
                        </div>
                      </td>
                      <td className="py-3.5 px-4 font-bold font-mono text-slate-900">
                        {formatINR(f.principal_amount)}
                        <span className="block text-[10px] text-slate-400 font-sans font-normal">
                          @ {f.interest_rate}% p.a.
                        </span>
                      </td>
                      <td className="py-3.5 px-4 whitespace-nowrap text-slate-700">
                        {formatDate(f.maturity_date)}
                      </td>
                      <td className="py-3.5 px-4">
                        <BadgeProvenance
                          sourceType={provSource}
                          confidenceScore={provScore}
                          size="sm"
                        />
                      </td>
                      <td className="py-3.5 px-4">
                        <BadgeStatus status={f.status} size="sm" />
                      </td>
                      <td className="py-3.5 px-4 text-center">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedFdr(f);
                          }}
                          className="p-1.5 text-slate-400 hover:text-primary hover:bg-slate-100 rounded-lg transition-colors"
                          title="View complete record details"
                        >
                          <Eye className="w-4 h-4" />
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Detail Slide-out Sheet / Modal */}
      {selectedFdr && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm animate-fade-in">
          <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-2xl max-h-[90vh] flex flex-col overflow-hidden">
            {/* Header */}
            <div className="px-6 py-4 bg-primary text-white flex items-center justify-between">
              <div className="space-y-0.5">
                <div className="flex items-center gap-2">
                  <h2 className="text-base font-bold font-mono">
                    {selectedFdr.fdr_number}
                  </h2>
                  <BadgeStatus status={selectedFdr.status} size="sm" />
                </div>
                <p className="text-xs text-slate-300">
                  {selectedFdr.institution_name} ({selectedFdr.aicte_permanent_id})
                </p>
              </div>
              <button
                onClick={() => setSelectedFdr(null)}
                className="p-1 text-slate-300 hover:text-white rounded-lg"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Content Body */}
            <div className="p-6 overflow-y-auto space-y-6 text-xs text-slate-700">
              {/* Financial Snapshot */}
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 p-4 bg-slate-50 rounded-xl border border-slate-200">
                <div>
                  <span className="text-[10px] uppercase font-bold text-slate-400">
                    Principal Amount
                  </span>
                  <p className="text-base font-bold font-mono text-slate-900 mt-0.5">
                    {formatINR(selectedFdr.principal_amount)}
                  </p>
                </div>
                <div>
                  <span className="text-[10px] uppercase font-bold text-slate-400">
                    Interest Rate
                  </span>
                  <p className="text-base font-bold font-mono text-slate-900 mt-0.5">
                    {selectedFdr.interest_rate}% p.a.
                  </p>
                </div>
                <div>
                  <span className="text-[10px] uppercase font-bold text-slate-400">
                    Maturity Date
                  </span>
                  <p className="text-base font-bold text-slate-900 mt-0.5">
                    {formatDate(selectedFdr.maturity_date)}
                  </p>
                </div>
              </div>

              {/* Banking & Lien Details */}
              <div className="space-y-3">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 border-b border-slate-100 pb-1 flex items-center gap-1.5">
                  <Landmark className="w-3.5 h-3.5 text-primary" />
                  <span>Issuing Bank & Lien Designation</span>
                </h4>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <span className="text-[10px] text-slate-400">Issuing Bank</span>
                    <p className="font-semibold text-slate-900">{selectedFdr.bank_name}</p>
                    <p className="text-slate-500 text-[11px]">{selectedFdr.branch || "Designated Branch"}</p>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-400">IFSC Code</span>
                    <p className="font-mono font-semibold text-slate-900">{selectedFdr.ifsc_code}</p>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-400">Lien Holder</span>
                    <p className="font-semibold text-slate-900">{selectedFdr.lien_holder}</p>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-400">Issue Date</span>
                    <p className="font-medium text-slate-900">{formatDate(selectedFdr.issue_date)}</p>
                  </div>
                </div>
              </div>

              {/* Field Provenance Table */}
              <div className="space-y-3">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 border-b border-slate-100 pb-1 flex items-center gap-1.5">
                  <ShieldCheck className="w-3.5 h-3.5 text-primary" />
                  <span>Field-Level Provenance & Source Attributions</span>
                </h4>
                <div className="border border-slate-200 rounded-lg overflow-hidden">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-50 text-slate-600 font-semibold text-[10px] uppercase">
                      <tr>
                        <th className="py-2 px-3">Field</th>
                        <th className="py-2 px-3">Recorded Value</th>
                        <th className="py-2 px-3">Source Tier</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {selectedFdr.provenance_records.map((p, idx) => (
                        <tr key={idx}>
                          <td className="py-2 px-3 font-mono text-slate-600">
                            {p.field_name}
                          </td>
                          <td className="py-2 px-3 font-medium text-slate-900">
                            {p.extracted_value || "—"}
                          </td>
                          <td className="py-2 px-3">
                            <BadgeProvenance
                              sourceType={p.source_type}
                              confidenceScore={p.confidence_score}
                              size="sm"
                            />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Cryptographic & Forensics Metadata */}
              <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 space-y-1.5 font-mono text-[11px]">
                <div className="flex items-center justify-between text-slate-500">
                  <span>SHA-256 Document Hash:</span>
                  <span className="text-slate-800">
                    {truncateHash(selectedFdr.document_hash, 10)}
                  </span>
                </div>
                <div className="flex items-center justify-between text-slate-500">
                  <span>MinIO Storage Key:</span>
                  <span className="text-slate-800">{selectedFdr.document_path || "Presigned S3 Object"}</span>
                </div>
                {selectedFdr.noc_number && (
                  <div className="flex items-center justify-between text-emerald-700 font-sans font-semibold pt-1 border-t border-slate-200">
                    <span>Statutory NOC Number:</span>
                    <span className="font-mono">{selectedFdr.noc_number}</span>
                  </div>
                )}
              </div>
            </div>

            {/* Footer */}
            <div className="px-6 py-3 bg-slate-50 border-t border-slate-200 flex items-center justify-end">
              <button
                onClick={() => setSelectedFdr(null)}
                className="px-4 py-2 bg-slate-200 hover:bg-slate-300 text-slate-800 font-semibold rounded-lg text-xs transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
