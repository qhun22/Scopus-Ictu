import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";

export type ButtonVariant = "primary" | "secondary" | "danger" | "ghost" | "tonal";
export type ButtonSize = "md" | "sm";

// Figma "Buttons" (5:2): 36px high, 16px horizontal padding, 13px SemiBold, 120px wide samples.
// "tonal" + "sm" follow the table action "Xem" in Figma "Data Table" (9:41). Hover colours are PROPOSED (not in Figma).
const VARIANT_CLASS: Record<ButtonVariant, string> = {
  primary: "border border-brand bg-brand text-white hover:bg-brand-hover hover:border-brand-hover focus-visible:outline-brand",
  secondary: "border-[1.5px] border-line-strong bg-white text-ink-body hover:bg-slate-50 focus-visible:outline-brand",
  danger: "border border-danger bg-danger text-white hover:bg-danger-hover hover:border-danger-hover focus-visible:outline-danger",
  ghost: "border border-transparent bg-slate-100 text-ink-body hover:bg-slate-200 focus-visible:outline-brand",
  tonal: "border border-transparent bg-brand-subtle text-brand hover:bg-[#DDE5F7] focus-visible:outline-brand",
};

// md = Figma "Buttons" (5:2): 6px radius. sm = Figma table action "Xem" (9:72): 4px radius, 11px, px10.
const SIZE_CLASS: Record<ButtonSize, string> = {
  md: "h-control min-w-action gap-1.5 rounded-control px-4 text-[13px]",
  sm: "h-7 gap-1 rounded-action px-2.5 text-[11px]",
};

export function buttonClass(variant: ButtonVariant = "primary", size: ButtonSize = "md", fullWidth = false): string {
  return [
    "inline-flex shrink-0 items-center justify-center whitespace-nowrap font-semibold leading-none",
    // Plain solid-colour outline on focus — no blurred/translucent ring glow.
    "transition-colors duration-150 cursor-pointer focus:outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1",
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
