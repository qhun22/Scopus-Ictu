import {
  createContext,
  useCallback,
  useContext,
  useRef,
  type ReactNode,
} from "react";

type PageVisitContextValue = {
  hasVisited: (pageKey: string) => boolean;
  markVisited: (pageKey: string) => void;
};

const PageVisitContext = createContext<PageVisitContextValue | null>(null);

export function PageVisitProvider({ children }: { children: ReactNode }) {
  const visitedPages = useRef(new Set<string>());

  const hasVisited = useCallback(
    (pageKey: string) => visitedPages.current.has(pageKey),
    [],
  );

  const markVisited = useCallback((pageKey: string) => {
    visitedPages.current.add(pageKey);
  }, []);

  return (
    <PageVisitContext.Provider value={{ hasVisited, markVisited }}>
      {children}
    </PageVisitContext.Provider>
  );
}

export function usePageVisit() {
  const context = useContext(PageVisitContext);
  if (!context) {
    throw new Error("usePageVisit must be used within PageVisitProvider");
  }
  return context;
}
