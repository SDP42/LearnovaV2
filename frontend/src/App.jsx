import { useEffect } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { SignedIn, SignedOut, useAuth } from "@/auth";
import * as api from "./api";
import Cursor from "./components/Cursor.jsx";
import ErrorBoundary from "./components/ErrorBoundary.jsx";
import AuthPage from "./pages/AuthPage.jsx";
import Analytics from "./pages/Analytics.jsx";
import Audience from "./pages/Audience.jsx";
import Create from "./pages/Create.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import DeckLibrary from "./pages/DeckLibrary.jsx";
import DiagramView from "./pages/DiagramView.jsx";
import Docs from "./pages/Docs.jsx";
import Export from "./pages/Export.jsx";
import Landing from "./pages/Landing.jsx";
import Library from "./pages/Library.jsx";
import Gallery from "./pages/Gallery.jsx";
import Present from "./pages/Present.jsx";
import Presentations from "./pages/Presentations.jsx";
import Preview from "./pages/Preview.jsx";
import Projects from "./pages/Projects.jsx";
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

  if (!isLoaded) return null;
  return children;
}

/** Sends signed-out visitors to /sign-in, remembering where they were headed. */
function Protected({ children }) {
  const location = useLocation();
  return (
    <>
      <SignedIn>{children}</SignedIn>
      <SignedOut>
        <Navigate to="/sign-in" replace state={{ from: location.pathname }} />
      </SignedOut>
    </>
  );
}

export default function App() {
  return (
    <AuthBridge>
      <Cursor />
      <ErrorBoundary>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/sign-in/*" element={<AuthPage mode="sign-in" />} />
        <Route path="/sign-up/*" element={<AuthPage mode="sign-up" />} />
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

        {/* New app shell (shadcn design system) */}
        <Route path="/app" element={<Protected><Dashboard /></Protected>} />
        <Route path="/app/create" element={<Protected><Create /></Protected>} />
        <Route path="/app/preview/:jobId" element={<Protected><Preview /></Protected>} />
        <Route path="/app/present/:jobId" element={<Protected><Present /></Protected>} />
        <Route path="/app/audience/:jobId" element={<Protected><Audience /></Protected>} />
        <Route path="/app/export/:jobId" element={<Protected><Export /></Protected>} />
        <Route path="/app/diagram/:jobId/:slide" element={<Protected><DiagramView /></Protected>} />
        <Route path="/app/projects" element={<Protected><Projects /></Protected>} />
        <Route path="/app/presentations" element={<Protected><Presentations /></Protected>} />
        <Route path="/app/quizzes" element={<Protected><Quizzes /></Protected>} />
        <Route path="/app/analytics" element={<Protected><Analytics /></Protected>} />
        <Route path="/app/library" element={<Protected><Library /></Protected>} />
        <Route path="/app/gallery" element={<Protected><Gallery /></Protected>} />
        <Route path="/app/docs" element={<Protected><Docs /></Protected>} />
        <Route path="/app/settings" element={<Protected><Settings /></Protected>} />

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      </ErrorBoundary>
    </AuthBridge>
  );
}
