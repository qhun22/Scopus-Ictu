import { useEffect, useRef, useState, type ChangeEvent, type CompositionEvent } from "react";

const SEARCH_DELAY_MS = 300;

/** Let the browser own text and caret while Vietnamese/IME input is in progress. */
export default function useDebouncedSearch(query: string, onQueryChange: (value: string) => void) {
  const inputRef = useRef<HTMLInputElement>(null);
  const initialQueryRef = useRef(query);
  const [draft, setDraft] = useState(query);
  const [composing, setComposing] = useState(false);
  const composingRef = useRef(false);
  const timerRef = useRef<number | null>(null);
  const submittedQueryRef = useRef<string | null>(null);
  const onQueryChangeRef = useRef(onQueryChange);
  onQueryChangeRef.current = onQueryChange;

  function cancelPending() {
    if (timerRef.current !== null) window.clearTimeout(timerRef.current);
    timerRef.current = null;
  }

  useEffect(() => {
    // Our own URL update must not overwrite newer typing or move the caret.
    if (query === submittedQueryRef.current) {
      submittedQueryRef.current = null;
      return;
    }
    cancelPending();
    setDraft(query);
    if (inputRef.current && inputRef.current.value !== query) inputRef.current.value = query;
  }, [query]);

  useEffect(() => {
    if (composing || draft === query) return;
    timerRef.current = window.setTimeout(() => {
      timerRef.current = null;
      if (composingRef.current) return;
      submittedQueryRef.current = draft;
      onQueryChangeRef.current(draft);
    }, SEARCH_DELAY_MS);
    return cancelPending;
  }, [draft, composing, query]);

  function clear() {
    cancelPending();
    submittedQueryRef.current = null;
    composingRef.current = false;
    setComposing(false);
    setDraft("");
    if (inputRef.current) inputRef.current.value = "";
  }

  return {
    draft,
    clear,
    inputProps: {
      ref: inputRef,
      defaultValue: initialQueryRef.current,
      onChange: (event: ChangeEvent<HTMLInputElement>) => {
        if (event.currentTarget.value === draft) return;
        cancelPending();
        setDraft(event.currentTarget.value);
      },
      onCompositionStart: () => {
        cancelPending();
        composingRef.current = true;
        setComposing(true);
      },
      onCompositionEnd: (event: CompositionEvent<HTMLInputElement>) => {
        composingRef.current = false;
        setComposing(false);
        setDraft(event.currentTarget.value);
      },
    },
  };
}
