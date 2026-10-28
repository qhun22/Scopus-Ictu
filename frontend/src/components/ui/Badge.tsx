import type { HTMLAttributes, ReactNode } from "react";

// Tones are the background/text pairs of Figma "Status Badges" (5:34). The caller maps business meaning to a tone;
// two statuses sharing a tone does not make them the same status.
export type BadgeTone = "success" | "warning" | "danger" | "info" | "indigo" | "neutral" | "violet" | "brand";

// PROPOSED (not in Figma 5:34): "outline" marks attributes / context / evidence (e.g. "1 other candidate")
// so they read differently from a status pill (e.g. "Pending") that uses the same tone. Same height and padding;
// the 1px border sits inside the 23px box, white background, the tone's text colour.
const OUTLINE_CLASS: Record<BadgeTone, string> = {
  success: "border border-[#A7F3D0] bg-white text-[#047857]",
  warning: "border border-[#FCD34D] bg-white text-[#B45309]",
  danger: "border border-[#FECDD3] bg-white text-[#BE123C]",
  info: "border border-[#A5F3FC] bg-white text-[#0E7490]",
  indigo: "border border-[#C7D2FE] bg-white text-[#4338CA]",
  neutral: "border border-[#CBD5E1] bg-white text-[#475569]",
  violet: "border border-[#DDD6FE] bg-white text-[#6D28D9]",
  brand: "border border-[#BFDBFE] bg-white text-brand",
};

const TONE_CLASS: Record<BadgeTone, string> = {
  success: "bg-[#ECFDF5] text-[#047857]",
  warning: "bg-[#FFFBEB] text-[#B45309]",
  danger: "bg-[#FFF1F2] text-[#BE123C]",
  info: "bg-[#ECFEFF] text-[#0E7490]",
  indigo: "bg-[#EEF2FF] text-[#4338CA]",
  neutral: "bg-[#F1F5F9] text-[#475569]",
  violet: "bg-[#F5F3FF] text-[#6D28D9]",
  brand: "bg-[#EFF6FF] text-brand",
};

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: BadgeTone;
  appearance?: "solid" | "outline";
  size?: "sm" | "md";
  children: ReactNode;
}

export default function Badge({ tone = "neutral", appearance = "solid", size = "sm", className = "", children, ...rest }: BadgeProps) {
  const toneClass = appearance === "outline" ? OUTLINE_CLASS[tone] : TONE_CLASS[tone];
  const sizeClass = size === "md" ? "h-[26px] px-3 text-[13px]" : "h-badge px-2.5 text-[11px]";
  return (
    <span
      className={`box-border inline-flex shrink-0 items-center whitespace-nowrap rounded-full font-bold leading-none ${sizeClass} ${toneClass} ${className}`.trim()}
      {...rest}
    >
      {children}
    </span>
  );
}
