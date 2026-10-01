/** Lecturer types — M0 scaffold. */

import { MilestonePing } from "./index";

export interface Lecturer {
  id: number;
  full_name?: string;
  email?: string;
}

export type LecturerPing = MilestonePing;