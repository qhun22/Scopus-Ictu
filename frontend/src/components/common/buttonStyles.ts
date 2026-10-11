/**
 * Button styles taken from the "Nút bấm" design spec (Figma):
 *   primary   #5B45D2 fill, white text
 *   secondary #ECEEFC fill, #E4E8F4 border, #5B45D2 text
 *   danger    #E50000 fill, white text
 * Shared so every screen can use the same three buttons.
 */
const BASE =
  "inline-flex min-h-10 items-center justify-center whitespace-nowrap rounded-lg px-5 py-2 text-sm font-bold " +
  "transition-colors duration-150 cursor-pointer focus:outline-none focus-visible:ring-2 " +
  "focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50";

export const BUTTON_PRIMARY = `${BASE} border border-[#5B45D2] bg-[#5B45D2] text-white hover:bg-[#4C38BF] focus-visible:ring-[#5B45D2]/40`;
export const BUTTON_SECONDARY = `${BASE} border border-[#E4E8F4] bg-[#ECEEFC] text-[#5B45D2] hover:bg-[#E0E4FA] focus-visible:ring-[#5B45D2]/30`;
export const BUTTON_DANGER = `${BASE} border border-[#E50000] bg-[#E50000] text-white hover:bg-[#C70000] focus-visible:ring-[#E50000]/40`;
