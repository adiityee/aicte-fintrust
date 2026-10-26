import React from "react";
import { FDRStatus } from "@/types";

interface BadgeStatusProps {
  status: FDRStatus;
  size?: "sm" | "md";
}

const STATUS_CONFIG: Record<
  FDRStatus,
  { label: string; bg: string; text: string; border: string; dot: string }
> = {
  DRAFT: {
    label: "Draft",
    bg: "bg-slate-50",
    text: "text-slate-700",
    border: "border-slate-200",
    dot: "bg-slate-400",
  },
  SUBMITTED: {
    label: "Submitted",
    bg: "bg-blue-50",
    text: "text-blue-700",
    border: "border-blue-200",
    dot: "bg-blue-500",
  },
  UNDER_SCRUTINY: {
    label: "Under Scrutiny",
    bg: "bg-amber-50",
    text: "text-amber-800",
    border: "border-amber-200",
    dot: "bg-amber-500",
  },
  QUERY_RAISED: {
    label: "Query Raised",
    bg: "bg-rose-50",
    text: "text-rose-700",
    border: "border-rose-200",
    dot: "bg-rose-500",
  },
  BANK_VERIFICATION_PENDING: {
    label: "Bank Verification Pending",
    bg: "bg-purple-50",
    text: "text-purple-700",
    border: "border-purple-200",
    dot: "bg-purple-500",
  },
  BANK_VERIFIED: {
    label: "Bank Verified & Lien Affirmed",
    bg: "bg-teal-50",
    text: "text-teal-800",
    border: "border-teal-200",
    dot: "bg-teal-500",
  },
  ACTIVE: {
    label: "Active (Lien Locked)",
    bg: "bg-emerald-50",
    text: "text-emerald-800",
    border: "border-emerald-200",
    dot: "bg-emerald-500",
  },
  MATURED: {
    label: "Matured (Renewal Required)",
    bg: "bg-orange-50",
    text: "text-orange-800",
    border: "border-orange-200",
    dot: "bg-orange-500",
  },
  RENEWED: {
    label: "Renewed",
    bg: "bg-indigo-50",
    text: "text-indigo-800",
    border: "border-indigo-200",
    dot: "bg-indigo-500",
  },
  RELEASE_REQUESTED: {
    label: "Release Requested (Clearances In Progress)",
    bg: "bg-sky-50",
    text: "text-sky-800",
    border: "border-sky-200",
    dot: "bg-sky-500",
  },
  CLEARANCES_APPROVED: {
    label: "All 5 Clearances Passed (Ready for Sign-off)",
    bg: "bg-emerald-100",
    text: "text-emerald-900",
    border: "border-emerald-300",
    dot: "bg-emerald-600",
  },
  RELEASED: {
    label: "Released (NOC Issued)",
    bg: "bg-slate-100",
    text: "text-slate-800",
    border: "border-slate-300",
    dot: "bg-slate-500",
  },
  ENCASHMENT_NOTICE_DRAFTED: {
    label: "Encashment Notice Drafted",
    bg: "bg-red-50",
    text: "text-red-800",
    border: "border-red-200",
    dot: "bg-red-500",
  },
};

export const BadgeStatus: React.FC<BadgeStatusProps> = ({
  status,
  size = "md",
}) => {
  const cfg = STATUS_CONFIG[status] || {
    label: status,
    bg: "bg-slate-50",
    text: "text-slate-700",
    border: "border-slate-200",
    dot: "bg-slate-400",
  };

  return (
    <span
      className={`inline-flex items-center gap-1.5 font-medium rounded-full border ${
        cfg.bg
      } ${cfg.text} ${cfg.border} ${
        size === "sm" ? "px-2 py-0.5 text-xs" : "px-2.5 py-1 text-xs"
      }`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />
      <span>{cfg.label}</span>
    </span>
  );
};
