import { useState, createContext, useContext, ReactNode } from 'react';

interface ViewerModeContextType {
  isViewerMode: boolean;
  setViewerMode: (mode: boolean) => void;
}

const ViewerModeContext = createContext<ViewerModeContextType | undefined>(undefined);

export function ViewerModeProvider({ children }: { children: ReactNode }) {
  const [isViewerMode, setViewerMode] = useState(false);
  return (
    <ViewerModeContext.Provider value={{ isViewerMode, setViewerMode }}>
      {children}
    </ViewerModeContext.Provider>
  );
}

export function useViewerMode() {
  const context = useContext(ViewerModeContext);
  if (!context) {
    throw new Error('useViewerMode must be used within ViewerModeProvider');
  }
  return context;
}
