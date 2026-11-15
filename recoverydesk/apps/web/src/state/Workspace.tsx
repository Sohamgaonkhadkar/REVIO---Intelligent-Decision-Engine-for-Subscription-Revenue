import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  chronologicalEvents,
  clock,
  filterRange,
  ledgerAt,
  safeRead,
  safeWrite,
  type TimeRange,
} from "../data/workspace";
import { cases, type RecoveryCase } from "../data/simulation";

type Theme = "light" | "dark";
interface WorkspaceState {
  route: string;
  navigate: (route: string) => void;
  theme: Theme;
  toggleTheme: () => void;
  collapsed: boolean;
  setCollapsed: (value: boolean) => void;
  focusMode: boolean;
  setFocusMode: (value: boolean) => void;
  presentation: boolean;
  startPresentation: () => void;
  exitPresentation: () => void;
  range: TimeRange;
  setRange: (value: TimeRange) => void;
  commandOpen: boolean;
  setCommandOpen: (value: boolean) => void;
  toast: string | null;
  notify: (message: string) => void;
  clearToast: () => void;
  recent: string[];
  tour: number | null;
  startTour: () => void;
  nextTour: () => void;
  endTour: () => void;
  replay: boolean;
  playing: boolean;
  cursor: number;
  at: number;
  cohort: RecoveryCase[];
  startReplay: () => void;
  toggleReplay: () => void;
  restartReplay: () => void;
  stopReplay: () => void;
}
const Workspace = createContext<WorkspaceState | null>(null);
const getRoute = () => {
  const path = window.location.hash.replace(/^#\/?/, '') || window.location.pathname.replace(/^\//, '');
  if (path === 'system') return 'trust';
  if (path === 'decisions') return 'lab';
  if (path.startsWith('cases/')) return path.replace(/^cases\//, 'case/');
  return path || 'overview';
};

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [route, setRoute] = useState(getRoute);
  const [theme, setTheme] = useState<Theme>(() =>
    safeRead("revio-blue-theme", "light"),
  );
  const [collapsed, setCollapsed] = useState(() =>
    safeRead("revio-blue-sidebar", false),
  );
  const [focusMode, setFocusMode] = useState(() =>
    safeRead("revio-luminous-focus", false),
  );
  const [presentation, setPresentation] = useState(false);
  const [range, setRange] = useState<TimeRange>("ALL");
  const [commandOpen, setCommandOpen] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [recent, setRecent] = useState<string[]>(() =>
    safeRead("revio-blue-recent", []),
  );
  const [tour, setTour] = useState<number | null>(null);
  const [replay, setReplay] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [cursor, setCursor] = useState(chronologicalEvents.length - 1);
  const at = replay
    ? new Date(chronologicalEvents[cursor].at).getTime()
    : clock;
  const cohort = useMemo(
    () => filterRange(replay ? ledgerAt(at) : cases, range),
    [replay, at, range],
  );
  const navigate = useCallback((path: string) => {
    window.location.hash = `/${path || "overview"}`;
    setCommandOpen(false);
  }, []);
  const notify = useCallback((message: string) => setToast(message), []);
  const clearToast = useCallback(() => setToast(null), []);
  useEffect(() => {
    const onHash = () => setRoute(getRoute());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    safeWrite("revio-blue-theme", theme);
  }, [theme]);
  useEffect(() => {
    safeWrite("revio-blue-sidebar", collapsed);
  }, [collapsed]);
  useEffect(() => {
    safeWrite("revio-luminous-focus", focusMode);
  }, [focusMode]);
  useEffect(() => {
    if (!presentation) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setPresentation(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [presentation]);
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "instant" });
    if (route !== "overview") {
      setPlaying(false);
      setReplay(false);
      setPresentation(false);
    }
    document.title = `REVIO | ${route.startsWith("case/") ? "Case Investigation" : route.startsWith("lab") ? "Decision Studio" : route.split("/")[0].replace(/^./, (s) => s.toUpperCase())}`;
    if (route.startsWith("case/")) {
      const id = route.split("/")[1];
      setRecent((r) => {
        const next = [id, ...r.filter((v) => v !== id)].slice(0, 4);
        safeWrite("revio-blue-recent", next);
        return next;
      });
    }
  }, [route]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setCommandOpen((s) => !s);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(clearToast, 4000);
    return () => clearTimeout(t);
  }, [toast, clearToast]);
  useEffect(() => {
    if (!replay || !playing) return;
    const t = setInterval(
      () =>
        setCursor((c) => {
          if (c >= chronologicalEvents.length - 1) {
            setPlaying(false);
            return c;
          }
          return c + 1;
        }),
      700,
    );
    return () => clearInterval(t);
  }, [replay, playing]);
  const tourRoutes = ["overview", "cases", "lab", "outcomes"];
  return (
    <Workspace.Provider
      value={{
        route,
        navigate,
        theme,
        toggleTheme: () => setTheme((t) => (t === "light" ? "dark" : "light")),
        collapsed,
        setCollapsed,
        focusMode,
        setFocusMode,
        presentation,
        startPresentation: () => {
          setPresentation(true);
          navigate("overview");
        },
        exitPresentation: () => setPresentation(false),
        range,
        setRange,
        commandOpen,
        setCommandOpen,
        toast,
        notify,
        clearToast,
        recent,
        tour,
        startTour: () => {
          setTour(0);
          navigate("overview");
        },
        nextTour: () => {
          if (tour === null || tour >= 3) setTour(null);
          else {
            setTour(tour + 1);
            navigate(tourRoutes[tour + 1]);
          }
        },
        endTour: () => setTour(null),
        replay,
        playing,
        cursor,
        at,
        cohort,
        startReplay: () => {
          setReplay(true);
          setCursor(0);
          setPlaying(true);
          setRange("ALL");
        },
        toggleReplay: () => {
          if (cursor === chronologicalEvents.length - 1) setCursor(0);
          setPlaying((p) => !p);
        },
        restartReplay: () => {
          setCursor(0);
          setPlaying(true);
        },
        stopReplay: () => {
          setReplay(false);
          setPlaying(false);
        },
      }}
    >
      {children}
    </Workspace.Provider>
  );
}

export function useWorkspace() {
  const ctx = useContext(Workspace);
  if (!ctx) throw new Error("Workspace provider is required");
  return ctx;
}
