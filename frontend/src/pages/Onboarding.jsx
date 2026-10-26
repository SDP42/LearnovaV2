import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Loader2, Sparkles } from "lucide-react";
import { toast } from "sonner";
import * as api from "@/api";
import { useAuth } from "@/auth";
import { Blobs } from "@/components/fx/Haikei";
import "./auth.css";

const ROLES = [["educator", "Educator"], ["student", "Student"], ["trainer", "Trainer"], ["researcher", "Researcher"], ["other", "Other"]];
const COLORS = ["#F47B45", "#E3A66B", "#FFC93C", "#4ade80", "#fbbf24"];

export default function Onboarding() {
  const { user, setUser } = useAuth();
  const navigate = useNavigate();
  const [f, setF] = useState({ full_name: user?.full_name || "", email: user?.email || "", role: user?.role || "", organization: user?.organization || "", avatar_color: user?.avatar_color || COLORS[0] });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try {
      setUser(await api.saveProfile(f));
      toast.success("Profile saved");
      navigate("/app", { replace: true });
    } catch (x) {
      setErr(x.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div data-learnova-app className="au">
      <div className="au-aurora" />
      <Blobs />
      <motion.form className="au-card wide" onSubmit={submit} initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7 }}>
        <span className="au-avatar" style={{ background: f.avatar_color }}>{(f.full_name || "?").charAt(0).toUpperCase()}</span>
        <h1>Set up your profile</h1>
        <p>Verified: <b>{user?.phone}</b>. Tell us a little about you.</p>
        <label>Full name<input required minLength={2} value={f.full_name} onChange={set("full_name")} placeholder="Asha Rao" autoFocus /></label>
        <label>Email <small>(optional)</small><input type="email" value={f.email} onChange={set("email")} placeholder="you@school.edu" /></label>
        <label>I am a…
          <div className="au-chips">
            {ROLES.map(([v, l]) => <button type="button" key={v} className={f.role === v ? "on" : ""} onClick={() => setF({ ...f, role: v })}>{l}</button>)}
          </div>
        </label>
        <label>Organisation <small>(optional)</small><input value={f.organization} onChange={set("organization")} placeholder="School, university or company" /></label>
        <label>Avatar colour
          <div className="au-chips">
            {COLORS.map((c) => <button type="button" key={c} aria-label={c} className={`sw ${f.avatar_color === c ? "on" : ""}`} style={{ background: c }} onClick={() => setF({ ...f, avatar_color: c })} />)}
          </div>
        </label>
        {err && <div className="au-err" role="alert">{err}</div>}
        <button className="au-btn" disabled={busy}>{busy ? <Loader2 className="spin" size={18} /> : <>Finish <Sparkles size={18} /></>}</button>
      </motion.form>
    </div>
  );
}
