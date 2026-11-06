import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { getFeedbackUnread, markFeedbackSeen } from "../api/feedback";
import { useAuth } from "./AuthContext";

const POLL_INTERVAL_MS = 15_000;

interface FeedbackUnreadContextType {
  hasUnread: boolean;
  markSeen: () => Promise<void>;
}

const FeedbackUnreadContext = createContext<FeedbackUnreadContextType | undefined>(undefined);

export function FeedbackUnreadProvider({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth();
  const [hasUnread, setHasUnread] = useState(false);
  const inFlightRef = useRef(false);

  const refresh = useCallback(async () => {
    if (inFlightRef.current) return;
    inFlightRef.current = true;
    try {
      const res = await getFeedbackUnread();
      setHasUnread(res.has_unread);
    } catch {
      // A transient failure just keeps the previous (possibly stale) dot state.
    } finally {
      inFlightRef.current = false;
    }
  }, []);

  useEffect(() => {
    if (!isAuthenticated) {
      setHasUnread(false);
      return;
    }
    void refresh();
    const id = window.setInterval(() => {
      if (document.visibilityState === "visible") void refresh();
    }, POLL_INTERVAL_MS);
    return () => window.clearInterval(id);
  }, [isAuthenticated, refresh]);

  const markSeen = useCallback(async () => {
    try {
      await markFeedbackSeen();
      setHasUnread(false);
    } catch {
      // Next poll will retry; the dot just stays visible until then.
    }
  }, []);

  return (
    <FeedbackUnreadContext.Provider value={{ hasUnread, markSeen }}>
      {children}
    </FeedbackUnreadContext.Provider>
  );
}

export function useFeedbackUnread(): FeedbackUnreadContextType {
  const ctx = useContext(FeedbackUnreadContext);
  if (!ctx) throw new Error("useFeedbackUnread must be used within a FeedbackUnreadProvider");
  return ctx;
}
