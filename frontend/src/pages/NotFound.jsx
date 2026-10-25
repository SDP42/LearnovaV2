import { Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { Blobs } from "@/components/fx/Haikei";
import "./auth.css";

export default function NotFound() {
  return (
    <div data-learnova-app className="au">
      <div className="au-aurora" />
      <Blobs />
      <div className="au-card" style={{ textAlign: "center", alignItems: "center" }}>
        <b style={{ fontSize: 88, lineHeight: 1, fontFamily: "Bricolage Grotesque", background: "linear-gradient(135deg,#2563EB,#12C99B)", WebkitBackgroundClip: "text", color: "transparent" }}>404</b>
        <h1>This slide doesn't exist</h1>
        <p>The page you're after was moved, deleted, or never made it into the deck.</p>
        <Link to="/" className="au-btn" style={{ textDecoration: "none", padding: "12px 22px" }}><ArrowLeft size={16} /> Back to Learnova</Link>
      </div>
    </div>
  );
}
