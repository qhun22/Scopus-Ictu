/**
 * R4-A PageHeader pilot (PROMPT 11.5).
 * Shared layout for pages that have a title/subtitle block and an optional
 * action slot on the right. Used initially for ReviewHistory and AuditLogs
 * which share the identical header structure.
 *
 * Scope: layout only. No routing, auth, or business logic.
 */
import React from "react";

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  /** Right-side action area (e.g. a Refresh button). */
  action?: React.ReactNode;
}

export function PageHeader({ title, subtitle, action }: PageHeaderProps) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h1 className="text-xl font-bold text-slate-800 sm:text-2xl">{title}</h1>
        {subtitle && (
          <p className="mt-0.5 text-xs text-slate-500 sm:text-sm">{subtitle}</p>
        )}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}
