import { useCallback, useRef } from "react";

/**
 * Wraps an action so that it cannot start again until the previous call has
 * settled. Unlike a `loading` prop this blocks double clicks that arrive before
 * React re-renders the disabled state.
 */
export function useSingleFlight(action: () => void | Promise<void>): () => void {
  const running = useRef(false);
  const latest = useRef(action);
  latest.current = action;

  return useCallback(() => {
    if (running.current) return;
    running.current = true;
    const release = () => {
      running.current = false;
    };
    let result: void | Promise<void>;
    try {
      result = latest.current();
    } catch (error) {
      release();
      throw error;
    }
    void Promise.resolve(result).then(release, release);
  }, []);
}
