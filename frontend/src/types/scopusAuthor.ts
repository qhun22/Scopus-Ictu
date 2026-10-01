/** Scopus author types — M0 scaffold. */

import { MilestonePing } from "./index";

export interface ScopusAuthor {
  id: number;
  scopus_author_id?: string;
  name?: string;
}

export type ScopusAuthorPing = MilestonePing;