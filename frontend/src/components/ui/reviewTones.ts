import type { BadgeTone } from "./Badge";
import type { CandidateStatus, ReviewHistoryAction } from "../../types/review";

// Review-candidate status. ACCEPTED means "review accepted" — it is not an identity VERIFIED state.
export const CANDIDATE_STATUS_TONE: Record<CandidateStatus, BadgeTone> = {
  PENDING: "warning",
  ACCEPTED: "success",
  REJECTED: "danger",
  SUPERSEDED: "neutral",
};

// Reviewer action recorded in history (an action, not a resulting status).
export const REVIEW_ACTION_TONE: Record<ReviewHistoryAction, BadgeTone> = {
  ACCEPT: "success",
  REJECT: "danger",
  REOPEN: "warning",
};
