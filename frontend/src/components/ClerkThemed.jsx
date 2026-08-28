import { ClerkProvider } from "@/auth";
import { dark } from "@clerk/themes";
import { useTheme } from "@/components/theme.jsx";

/**
 * ClerkProvider wired to Learnova's design tokens. Clerk renders in its own
 * tree and cannot read our CSS variables, so the palette is mapped to literal
 * values here and switched with the app theme.
 */
const VIOLET = "#7c6cf0";
const VIOLET_LIGHT = "#8b7bf5";

function appearance(theme) {
  const isDark = theme === "dark";
  return {
    baseTheme: isDark ? dark : undefined,
    variables: {
      colorPrimary: isDark ? VIOLET_LIGHT : VIOLET,
      colorText: isDark ? "#f4f3f8" : "#1b1a25",
      colorTextSecondary: isDark ? "#a5a3b5" : "#5a5866",
      colorBackground: isDark ? "#22212e" : "#ffffff",
      colorInputBackground: isDark ? "#2c2b3a" : "#ffffff",
      colorInputText: isDark ? "#f4f3f8" : "#1b1a25",
      borderRadius: "0.6rem",
      fontFamily: "Inter, system-ui, sans-serif",
    },
    elements: {
      rootBox: { width: "100%" },
      cardBox: {
        boxShadow: "0 20px 60px -20px rgba(0,0,0,.5)",
        borderRadius: "0.9rem",
      },
      card: {
        border: isDark ? "1px solid rgba(255,255,255,.09)" : "1px solid rgba(0,0,0,.08)",
        borderRadius: "0.9rem",
      },
      headerTitle: { fontWeight: 600, letterSpacing: "-0.01em" },
      formButtonPrimary: {
        textTransform: "none",
        fontWeight: 600,
        boxShadow: "none",
      },
      formFieldInput: {
        borderColor: isDark ? "rgba(255,255,255,.12)" : "rgba(0,0,0,.12)",
      },
      socialButtonsBlockButton: {
        fontWeight: 500,
        borderColor: isDark ? "rgba(255,255,255,.12)" : "rgba(0,0,0,.12)",
      },
      footerActionLink: { fontWeight: 600 },
    },
  };
}

export default function ClerkThemed({ publishableKey, children }) {
  const { theme } = useTheme();
  return (
    <ClerkProvider
      publishableKey={publishableKey}
      afterSignOutUrl="/"
      appearance={appearance(theme)}
    >
      {children}
    </ClerkProvider>
  );
}
