import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { ClerkProvider } from "@clerk/clerk-react";
import { DEMO } from "./auth.jsx";
import { ThemeProvider } from "./components/theme.jsx";
import App from "./App.jsx";
import "./styles.css";
import "./index.css";

const PUBLISHABLE_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY;
const root = ReactDOM.createRoot(document.getElementById("root"));

const Shell = ({ children }) => (
  <React.StrictMode>
    <ThemeProvider defaultTheme="dark">
      <BrowserRouter>{children}</BrowserRouter>
    </ThemeProvider>
  </React.StrictMode>
);

if (DEMO) {
  // Run with `VITE_DEMO=1` — no Clerk, auth stubs from auth.jsx, backend in
  // anonymous single-user mode. For viewing the UI only.
  root.render(
    <Shell>
      <App />
    </Shell>
  );
} else if (!PUBLISHABLE_KEY) {
  root.render(
    <div style={{ padding: 40, fontFamily: "system-ui, sans-serif" }}>
      <h1>Missing Clerk key</h1>
      <p>
        Set <code>VITE_CLERK_PUBLISHABLE_KEY</code> in <code>frontend/.env</code>, then restart the
        dev server — or run <code>VITE_DEMO=1 npm run dev</code> to preview the UI without auth.
      </p>
    </div>
  );
} else {
  root.render(
    <Shell>
      <ClerkProvider publishableKey={PUBLISHABLE_KEY} afterSignOutUrl="/">
        <App />
      </ClerkProvider>
    </Shell>
  );
}
