import React from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import App from "./App";
import Overview from "./pages/Overview";
import Cases from "./pages/Cases";
import CaseDetail from "./pages/CaseDetail";
import Outcomes from "./pages/Outcomes";
import Knowledge from "./pages/Knowledge";
import Audit from "./pages/Audit";
import System from "./pages/System";
import { Link } from "react-router-dom";
import "./styles.css";

function NotFound() {
  return (
    <div className="state-empty" style={{ padding: 80 }}>
      <div style={{ fontSize: 40, fontWeight: 800 }}>404</div>
      <p>That page doesn't exist.</p>
      <p><Link className="plain" to="/">← Back to Overview</Link></p>
    </div>
  );
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { refetchOnWindowFocus: true, staleTime: 2_000, retry: 1 },
  },
});

const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
    children: [
      { index: true, element: <Overview /> },
      { path: "cases", element: <Cases /> },
      { path: "cases/:caseId", element: <CaseDetail /> },
      { path: "outcomes", element: <Outcomes /> },
      { path: "knowledge", element: <Knowledge /> },
      { path: "audit", element: <Audit /> },
      { path: "system", element: <System /> },
      { path: "*", element: <NotFound /> },
    ],
  },
]);

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </React.StrictMode>,
);
