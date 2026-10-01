/** Publication types — M0 scaffold. */

import { MilestonePing } from "./index";

export interface Publication {
  id: number;
  eid?: string;
  doi?: string;
  title?: string;
}

export type PublicationPing = MilestonePing;