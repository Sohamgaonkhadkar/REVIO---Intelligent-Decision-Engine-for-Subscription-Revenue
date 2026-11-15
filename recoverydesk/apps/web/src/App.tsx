import { AnimatePresence, MotionConfig, motion } from "motion/react";
import { Component, type ErrorInfo, type ReactNode } from "react";
import { ConsoleShell } from "./components/ConsoleShell";
import { EmptyState, Toast } from "./components/ui";
import { WorkspaceProvider, useWorkspace } from "./state/Workspace";
import Overview from "./pages/Overview";
import Cases from "./pages/Cases";
import CaseDetail from "./pages/CaseDetail";
import DecisionLab from "./pages/DecisionLab";
import Outcomes from "./pages/Outcomes";
import Knowledge from "./pages/Knowledge";
import Audit from "./pages/Audit";
import Trust from "./pages/Trust";
import LiveWorkspace from './pages/LiveWorkspace';
import { connected } from './api/runtime';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const queryClient = new QueryClient();

function Application() {
  const w = useWorkspace();
  const section = w.route.split(/[/?]/)[0];
  const page = connected ? <LiveWorkspace section={section} /> :
    section === "overview" ? (
      <Overview />
    ) : section === "cases" ? (
      <Cases />
    ) : section === "case" ? (
      <CaseDetail />
    ) : section === "lab" ? (
      <DecisionLab />
    ) : section === "outcomes" ? (
      <Outcomes />
    ) : section === "knowledge" ? (
      <Knowledge />
    ) : section === "audit" ? (
      <Audit />
    ) : section === "trust" ? (
      <Trust />
    ) : (
      <EmptyState
        title="This view is not available"
        body="The route does not match a REVIO workspace. Return to the overview to continue exploring the synthetic ledger."
        action={
          <button
            className="btn primary"
            onClick={() => w.navigate("overview")}
          >
            Back to overview
          </button>
        }
      />
    );
  return (
    <MotionConfig
      reducedMotion="user"
      transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
    >
      <a
        className="skip-link"
        href="#main-content"
        onClick={(e) => {
          e.preventDefault();
          document.getElementById("main-content")?.focus();
        }}
      >
        Skip to main content
      </a>
      <ConsoleShell>
        <div className="data-boundary" role="status">
          <strong>SIM · {connected ? 'Backend API evidence' : 'Standalone educational simulation'}</strong>
          <span>{connected ? 'Read-only recorded evidence · no payment actions from this workspace' : 'Synthetic fixtures · FastAPI, PostgreSQL and the model are not connected'}</span>
        </div>
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={connected ? 'api-workspace' : w.route}
            className="page-transition"
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.18 }}
          >
            {page}
          </motion.div>
        </AnimatePresence>
      </ConsoleShell>
      <AnimatePresence>
        {w.toast && <Toast message={w.toast} onClose={w.clearToast} />}
      </AnimatePresence>
    </MotionConfig>
  );
}

class AppBoundary extends Component<
  { children: ReactNode },
  { error: boolean }
> {
  state = { error: false };
  static getDerivedStateFromError() {
    return { error: true };
  }
  componentDidCatch(_error: Error, _info: ErrorInfo) {
    /* Keep the local workspace recoverable without exposing technical internals. */
  }
  render() {
    return this.state.error ? (
      <div className="app-error">
        <EmptyState
          title="The workspace needs a fresh start"
          body={connected ? 'The API workspace could not render this response. Reload to retry the backend connection.' : 'Your financial data is a read-only local fixture. Reload the workspace to restore the latest simulation snapshot.'}
          action={
            <button
              className="btn primary"
              onClick={() => window.location.reload()}
            >
              Reload workspace
            </button>
          }
        />
      </div>
    ) : (
      this.props.children
    );
  }
}
export default function App() {
  return (
    <QueryClientProvider client={queryClient}><AppBoundary>
      <WorkspaceProvider>
        <Application />
      </WorkspaceProvider>
    </AppBoundary></QueryClientProvider>
  );
}
