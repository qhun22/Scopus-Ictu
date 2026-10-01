/** Review types — M0 scaffold. */

import { MilestonePing } from "./index";

export interface MappingReview {
  id: number;
  identity_id: number;
  decision?: string;
  reason?: string;
}

export type ReviewPing = MilestonePing;