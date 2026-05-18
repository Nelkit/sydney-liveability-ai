"use client";

import { createContext, useContext, useState } from "react";
import type { Citation } from "@/types/api";

type CitationHoverContextValue = {
  hoveredCite: Citation | null;
  setHoveredCite: (cite: Citation | null) => void;
};

const CitationHoverContext = createContext<CitationHoverContextValue>({
  hoveredCite: null,
  setHoveredCite: () => {},
});

export function CitationHoverProvider({ children }: { children: React.ReactNode }) {
  const [hoveredCite, setHoveredCite] = useState<Citation | null>(null);
  return (
    <CitationHoverContext.Provider value={{ hoveredCite, setHoveredCite }}>
      {children}
    </CitationHoverContext.Provider>
  );
}

export function useCitationHover() {
  return useContext(CitationHoverContext);
}
