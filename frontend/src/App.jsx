import { useEffect } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useAuth } from "@/auth";
import * as api from "./api";
import ErrorBoundary from "./components/ErrorBoundary.jsx";
import AuthPage from "./pages/AuthPage.jsx";
import Onboarding from "./pages/Onboarding.jsx";
import NotFound from "./pages/NotFound.jsx";
import Legal from "./pages/Legal.jsx";
import Analytics from "./pages/Analytics.jsx";
import Audience from "./pages/Audience.jsx";
import Compare from "./pages/Compare.jsx";
import Create from "./pages/Create.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import DeckLibrary from "./pages/DeckLibrary.jsx";
import DiagramView from "./pages/DiagramView.jsx";
import Docs from "./pages/Docs.jsx";
import Export from "./pages/Export.jsx";
import Landing from "./pages/Landing.jsx";
import Templates from "./pages/Templates.jsx";
import Present from "./pages/Present.jsx";
import Presentations from "./pages/Presentations.jsx";
import Preview from "./pages/Preview.jsx";
import Generate from "./pages/Generate.jsx";
import AppShell from "./components/app/AppShell.jsx";
import Quizzes from "./pages/Quizzes.jsx";
import Settings from "./pages/Settings.jsx";
import Studio from "./pages/Studio.jsx";

/**
 * Hands Clerk's `getToken` to the API client once, so every request carries a
 * fresh session JWT without each caller threading a token through.
 */
function AuthBridge({ children }) {
  const { getToken, isLoaded } = useAuth();

  useEffect(() => {
    api.setTokenGetter(async () => {
      try {
        return await getToken();
      } catch {
        return null;
      }
    });
  }, [getToken]);

  useEffect(() => {
    const onErr = (e) => api.reportError(e.message, e.error?.stack, "window");
    const onRej = (e) => api.reportError(e.reason?.message || e.reason, e.reason?.stack, "promise");
    window.addEventListener("error", onErr);
    window.addEventListener("unhandledrejection", onRej);
    return () => {
      window.removeEventListener("error", onErr);
      window.removeEventListener("unhandledrejection", onRej);
    };
  }, []);

  const { pathname } = useLocation();
  useEffect(() => api.track("page_view"), [pathname]);

  if (!isLoaded)
    return (
      <div className="grid min-h-svh place-items-center" role="status" aria-label="Loading">
        <div className="size-9 animate-spin rounded-full border-2 border-primary/20 border-t-primary" />
      </div>
    );
  return children;
}

/** Signed-out → /sign-in (remembering the target); signed-in without a profile → /welcome. */
function Protected({ children }) {
  const location = useLocation();
  const { isSignedIn, user } = useAuth();
  if (!isSignedIn) return <Navigate to="/sign-in" replace state={{ from: location.pathname }} />;
  if (user && user.completed === false) return <Navigate to="/welcome" replace />;
  return children;
}

function Welcome() {
  const { isSignedIn } = useAuth();
  return isSignedIn ? <Onboarding /> : <Navigate to="/sign-in" replace />;
}

export default function App() {
  return (
    <AuthBridge>
      <ErrorBoundary>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/sign-in" element={<AuthPage />} />
        <Route path="/sign-up" element={<Navigate to="/sign-in" replace />} />
        <Route path="/welcome" element={<Welcome />} />
        <Route
          path="/studio"
          element={
            <Protected>
              <Studio />
            </Protected>
          }
        />
        <Route
          path="/decks"
          element={
            <Protected>
              <DeckLibrary />
            </Protected>
          }
        />

        {/* App shell: persistent sidebar + header, pages render in the Outlet */}
        <Route element={<Protected><AppShell /></Protected>}>
          <Route path="/app" element={<Dashboard />} />
          <Route path="/app/create" element={<Create />} />
          <Route path="/app/generate/:jobId" element={<Generate />} />
          <Route path="/app/presentations" element={<Presentations />} />
          <Route path="/app/projects" element={<Navigate to="/app/presentations" replace />} />
          <Route path="/app/gallery" element={<Templates />} />
          <Route path="/app/library" element={<Navigate to="/app/gallery?tab=lessons" replace />} />
          <Route path="/app/quizzes" element={<Quizzes />} />
          <Route path="/app/analytics" element={<Analytics />} />
          <Route path="/app/docs" element={<Docs />} />
          <Route path="/app/settings" element={<Settings />} />
        </Route>
        <Route path="/app/preview/:jobId" element={<Protected><Preview /></Protected>} />
        <Route path="/app/compare/:jobId" element={<Protected><Compare /></Protected>} />
        <Route path="/app/present/:jobId" element={<Protected><Present /></Protected>} />
        <Route path="/app/audience/:jobId" element={<Protected><Audience /></Protected>} />
        <Route path="/app/export/:jobId" element={<Protected><Export /></Protected>} />
        <Route path="/app/diagram/:jobId/:slide" element={<Protected><DiagramView /></Protected>} />

        <Route path="/privacy" element={<Legal kind="privacy" />} />
        <Route path="/terms" element={<Legal kind="terms" />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
      </ErrorBoundary>
    </AuthBridge>
  );
}
