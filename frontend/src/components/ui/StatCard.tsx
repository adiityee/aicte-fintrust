import React from "react";
import { LucideIcon } from "lucide-react";

interface StatCardProps {
  title: string;
  value: string;
  subtitle?: string;
  icon: LucideIcon;
  badge?: string;
  badgeType?: "success" | "warning" | "danger" | "neutral" | "info";
  className?: string;
  actionText?: string;
  onAction?: () => void;
}

export const StatCard: React.FC<StatCardProps> = ({
  title,
  value,
  subtitle,
  icon: Icon,
  badge,
  badgeType = "neutral",
  className = "",
  actionText,
  onAction,
}) => {
  const badgeStyles = {
    success: "bg-emerald-50 text-emerald-700 border-emerald-200",
    warning: "bg-amber-50 text-amber-800 border-amber-200",
    danger: "bg-rose-50 text-rose-700 border-rose-200",
    info: "bg-blue-50 text-blue-700 border-blue-200",
    neutral: "bg-slate-50 text-slate-700 border-slate-200",
  }[badgeType];

  return (
    <div
      className={`bg-white rounded-xl border border-slate-200/90 p-5 shadow-subtle hover:shadow-card transition-all duration-200 ${className}`}
    >
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
            {title}
          </p>
          <h3 className="text-2xl font-bold tracking-tight text-slate-900">
            {value}
          </h3>
        </div>
        <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-100 text-slate-700">
          <Icon className="w-5 h-5 text-primary" />
        </div>
      </div>

      {(subtitle || badge || actionText) && (
        <div className="mt-3.5 pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
          <div className="truncate pr-2">{subtitle}</div>
          {badge && (
            <span
              className={`inline-flex items-center px-2 py-0.5 rounded-full border text-[11px] font-medium shrink-0 ${badgeStyles}`}
            >
              {badge}
            </span>
          )}
          {actionText && onAction && (
            <button
              onClick={onAction}
              className="text-primary font-medium hover:underline shrink-0"
            >
              {actionText} →
            </button>
          )}
        </div>
      )}
    </div>
  );
};
