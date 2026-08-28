import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { SignedIn, SignedOut, UserButton } from "../auth.jsx";

const SECTIONS = ["hero", "intro", "features", "stats", "contact"];

export default function Navbar({ variant = "auto" }) {
  const [atTop, setAtTop] = useState(true);
  const location = useLocation();
  const navigate = useNavigate();
  const onLanding = location.pathname === "/";

  useEffect(() => {
    if (!onLanding) return undefined;
    const onScroll = () => setAtTop(window.scrollY < 40);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, [onLanding]);

  // Transparent over the hero, solid dark once scrolled or off the landing page.
  const isTop = variant === "auto" && onLanding && atTop;

  return (
    <nav className={`nav${isTop ? " is-top" : ""}`}>
      <Link to="/" className="nav-logo">LEARNOVA</Link>

      {onLanding ? (
        <div className="nav-links">
          {SECTIONS.map((id) => (
            <a key={id} href={`#${id}`}>
              {id}
            </a>
          ))}
        </div>
      ) : (
        <div className="nav-links">
          <Link to="/studio">Studio</Link>
          <Link to="/decks">My Decks</Link>
          <Link to="/">Home</Link>
        </div>
      )}

      <div className="nav-right">
        <SignedOut>
          <Link to="/sign-in" className="nav-login">Login
          </Link>
        </SignedOut>
        <SignedIn>
          <button
            type="button"
            className="nav-login"
            style={{ background: "none", cursor: "pointer" }}
            onClick={() => navigate("/studio")}
          >Studio
          </button>
          <UserButton afterSignOutUrl="/" />
        </SignedIn>
        <button className="burger" aria-label="Menu" type="button">
          <span />
          <span />
          <span />
        </button>
      </div>
    </nav>
  );
}
