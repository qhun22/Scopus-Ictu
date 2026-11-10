import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "../../api/client";
import { getApiErrorMessage } from "../../api/errors";
import { getMyLecturerPublications } from "../../api/lecturerScopus";
import type { LecturerPublicationsResponse } from "../../types/lecturerScopus";

export default function useMyPublications(loadError: string) {
  const [response, setResponse] = useState<LecturerPublicationsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notLinked, setNotLinked] = useState(false);
  const controllerRef = useRef<AbortController | null>(null);
  const errorMessageRef = useRef(loadError);
  errorMessageRef.current = loadError;

  const reload = useCallback(async () => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    setLoading(true);
    setError(null);
    setNotLinked(false);
    setResponse(null);
    try {
      // Keep the existing authorized, read-only endpoint. Load every page before
      // exposing filters so a match on a later page is never silently omitted.
      const first = await getMyLecturerPublications({ page: 1, page_size: 100 }, { signal: controller.signal });
      const items = [...first.items];
      const totalPages = Math.ceil(first.total / Math.max(1, first.page_size));
      for (let page = 2; page <= totalPages; page += 1) {
        if (controller.signal.aborted) return;
        const next = await getMyLecturerPublications({ page, page_size: first.page_size }, { signal: controller.signal });
        items.push(...next.items);
      }
      if (!controller.signal.aborted) {
        setResponse({ ...first, items: [...new Map(items.map((item) => [item.eid, item])).values()] });
      }
    } catch (requestError) {
      if (controller.signal.aborted) return;
      if (requestError instanceof ApiError && requestError.code === "LECTURER_NOT_LINKED") setNotLinked(true);
      else setError(getApiErrorMessage(requestError, errorMessageRef.current));
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
    return () => controllerRef.current?.abort();
  }, [reload]);

  return { response, loading, error, notLinked, reload };
}
