import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";

export type ButtonVariant = "primary" | "secondary" | "danger" | "ghost" | "tonal";
export type ButtonSize = "md" | "sm";

// Figma "Buttons" (5:2): 36px high, 16px horizontal padding, 13px SemiBold, 120px wide samples.
// "tonal" + "sm" follow the table action "Xem" in Figma "Data Table" (9:41). Hover colours are PROPOSED (not in Figma).
const VARIANT_CLASS: Record<ButtonVariant, string> = {
  primary: "border border-brand bg-brand text-white hover:bg-brand-hover hover:border-brand-hover focus-visible:ring-brand/40",
  secondary: "border-[1.5px] border-line-strong bg-white text-ink-body hover:bg-slate-50 focus-visible:ring-brand/30",
  danger: "border border-danger bg-danger text-white hover:bg-danger-hover hover:border-danger-hover focus-visible:ring-danger/40",
  ghost: "border border-transparent bg-slate-100 text-ink-body hover:bg-slate-200 focus-visible:ring-brand/30",
  tonal: "border border-transparent bg-brand-subtle text-brand hover:bg-[#DDE5F7] focus-visible:ring-brand/30",
};

// md = Figma "Buttons" (5:2): 6px radius. sm = Figma table action "Xem" (9:72): 4px radius, 11px, px10.
const SIZE_CLASS: Record<ButtonSize, string> = {
  md: "h-control min-w-action gap-1.5 rounded-control px-4 text-[13px]",
  sm: "h-7 gap-1 rounded-action px-2.5 text-[11px]",
};

export function buttonClass(variant: ButtonVariant = "primary", size: ButtonSize = "md", fullWidth = false): string {
  return [
    "inline-flex shrink-0 items-center justify-center whitespace-nowrap font-semibold leading-none",
    "transition-colors duration-150 cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-1",
    "disabled:cursor-not-allowed disabled:opacity-50",
    SIZE_CLASS[size],
    VARIANT_CLASS[variant],
    fullWidth ? "w-full" : "",
  ].join(" ");
}

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  fullWidth?: boolean;
  loading?: boolean;
  icon?: ReactNode;
}

const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", size = "md", fullWidth = false, loading = false, icon, className = "", type = "button", disabled, children, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={`${buttonClass(variant, size, fullWidth)} ${className}`.trim()}
      {...rest}
    >
      {loading ? (
        <span className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-t-transparent" aria-hidden="true" />
      ) : (
        icon
      )}
      {children}
    </button>
  );
});

export default Button;
