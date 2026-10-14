/**
 * Button styles aligned with Figma "Nền tảng thiết kế" (brand color #3A5FC3, hover #2F4EA6).
 *   primary   #3A5FC3 fill, white text
 *   secondary #EBEFF9 fill, #3A5FC3 border/text
 *   danger    #E50000 fill, white text
 *   ghost     transparent, #3A5FC3 text, border on hover
 * Shared so every screen uses the same button variants.
 */
const BASE =
  "inline-flex min-h-10 items-center justify-center gap-1.5 whitespace-nowrap rounded-lg px-5 py-2 text-sm font-bold " +
  "transition-colors duration-150 cursor-pointer focus:outline-none focus-visible:ring-2 " +
  "focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50";

export const BUTTON_PRIMARY = `${BASE} border border-[#3A5FC3] bg-[#3A5FC3] text-white hover:bg-[#2F4EA6] focus-visible:ring-[#3A5FC3]/40`;
export const BUTTON_SECONDARY = `${BASE} border border-[#3A5FC3]/30 bg-[#EBEFF9] text-[#3A5FC3] hover:bg-[#dde5f7] focus-visible:ring-[#3A5FC3]/30`;
export const BUTTON_DANGER = `${BASE} border border-[#E50000] bg-[#E50000] text-white hover:bg-[#C70000] focus-visible:ring-[#E50000]/40`;
export const BUTTON_GHOST = `${BASE} border border-transparent bg-transparent text-[#3A5FC3] hover:bg-[#EBEFF9] hover:border-[#3A5FC3]/20 focus-visible:ring-[#3A5FC3]/30`;
