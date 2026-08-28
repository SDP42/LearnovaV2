import { SignIn, SignUp } from "@/auth";
import Footer from "../components/Footer.jsx";
import Navbar from "../components/Navbar.jsx";

// Clerk's card is restyled to match the brutalist shell: square corners,
// black borders, amber primary button. Clerk renders in its own tree and
// takes plain values, not CSS custom properties — these must stay literals and
// be kept in step with the --accent tokens in styles.css.
const clerkAppearance = {
  variables: {
    colorPrimary: "#000000",
    colorText: "#000000",
    colorBackground: "#ffffff",
    borderRadius: "0px",
    fontFamily: "Archivo, system-ui, sans-serif",
  },
  elements: {
    rootBox: { width: "100%" },
    cardBox: { boxShadow: "none", borderRadius: 0 },
    card: { boxShadow: "none", borderRadius: 0, border: "none" },
    headerTitle: {
      fontFamily: "Oswald, sans-serif",
      textTransform: "uppercase",
      letterSpacing: "0.06em",
    },
    formButtonPrimary: {
      background: "#ffbd00",
      color: "#000",
      border: "3px solid #000",
      borderRadius: 0,
      fontFamily: "Oswald, sans-serif",
      textTransform: "uppercase",
      letterSpacing: "0.12em",
      fontWeight: 600,
      boxShadow: "none",
      "&:hover": { background: "#cc9700" },
    },
    socialButtonsBlockButton: { borderRadius: 0, border: "2px solid #000" },
    formFieldInput: { borderRadius: 0, border: "2px solid #000" },
    footerActionLink: { color: "#000", fontWeight: 700 },
  },
};

export default function AuthPage({ mode = "sign-in" }) {
  const isSignIn = mode === "sign-in";

  return (
    <>
      <Navbar variant="solid" />

      <section className="auth-wrap dotgrid" style={{ paddingTop: 110 }}>
        <div className="watermark auth-watermark">LEARNOVA</div>

        <div className="auth-head">
          <div className="hero-badge">
            <span className="dot" />
            <span className="eyebrow">SECURE {isSignIn ? "LOGIN" : "SIGN UP"}</span>
          </div>

          <h1 className="display auth-title">
            {isSignIn ? "SIGN" : "CREATE"}
            <br />
            <span className="outline-word">{isSignIn ? "IN." : "ACCOUNT."}</span>
          </h1>

          <p className="auth-sub">Access your <b>Learnova</b> studio and deck library.
            <br />Build smarter. Present better.
          </p>
        </div>

        <div className="auth-card">
          {isSignIn ? (
            <SignIn
              routing="path"
              path="/sign-in"
              signUpUrl="/sign-up"
              forceRedirectUrl="/studio"
              appearance={clerkAppearance}
            />
          ) : (
            <SignUp
              routing="path"
              path="/sign-up"
              signInUrl="/sign-in"
              forceRedirectUrl="/studio"
              appearance={clerkAppearance}
            />
          )}
        </div>
      </section>

      <Footer />
    </>
  );
}
