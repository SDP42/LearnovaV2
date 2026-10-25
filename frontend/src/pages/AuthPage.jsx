import { useEffect, useRef, useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowLeft, ArrowRight, Loader2, ShieldCheck, Smartphone, Sparkles } from "lucide-react";
import { toast } from "sonner";
import * as api from "@/api";
import { useAuth } from "@/auth";
import { Blobs } from "@/components/fx/Haikei";
import "./auth.css";

const LEN = 6;
const COUNTRIES = [["+91", "🇮🇳 IN"], ["+1", "🇺🇸 US"], ["+44", "🇬🇧 UK"], ["+61", "🇦🇺 AU"], ["+971", "🇦🇪 AE"], ["+65", "🇸🇬 SG"]];

function OtpBoxes({ value, onChange, onDone, disabled }) {
  const refs = useRef([]);
  useEffect(() => refs.current[0]?.focus(), []);
  const set = (digits) => {
    const v = digits.slice(0, LEN);
    onChange(v);
    if (v.length === LEN) onDone(v);
  };
  return (
    <div className="au-otp" onPaste={(e) => { e.preventDefault(); set(e.clipboardData.getData("text").replace(/\D/g, "")); }}>
      {Array.from({ length: LEN }, (_, i) => (
        <input
          key={i}
          ref={(el) => (refs.current[i] = el)}
          inputMode="numeric"
          autoComplete={i === 0 ? "one-time-code" : "off"}
                    disabled={disabled}
          value={value[i] || ""}
          aria-label={`Digit ${i + 1}`}
          onChange={(e) => {
            const d = e.target.value.replace(/\D/g, "");
            if (!d) return;
            const next = (value.slice(0, i) + d).slice(0, LEN);
            set(next);
            refs.current[Math.min(next.length, LEN - 1)]?.focus();
          }}
          onKeyDown={(e) => {
            if (e.key === "Backspace") {
              if (value[i]) onChange(value.slice(0, i) + value.slice(i + 1));
              else refs.current[Math.max(i - 1, 0)]?.focus();
            }
            if (e.key === "ArrowLeft") refs.current[Math.max(i - 1, 0)]?.focus();
            if (e.key === "ArrowRight") refs.current[Math.min(i + 1, LEN - 1)]?.focus();
          }}
        />
      ))}
    </div>
  );
}

export default function AuthPage() {
  const { isSignedIn, user, setSession } = useAuth();
  const navigate = useNavigate();
  const from = useLocation().state?.from || "/app";
  const [step, setStep] = useState("phone");
  const [cc, setCc] = useState("+91");
  const [num, setNum] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [cool, setCool] = useState(0);
  const [devOtp, setDevOtp] = useState("");
  const phone = cc + num.replace(/\D/g, "");

  useEffect(() => {
    if (cool <= 0) return;
    const t = setTimeout(() => setCool((c) => c - 1), 1000);
    return () => clearTimeout(t);
  }, [cool]);

  if (isSignedIn) return <Navigate to={user?.completed ? from : "/welcome"} replace />;

  async function send(e) {
    e?.preventDefault();
    setErr("");
    setBusy(true);
    try {
      const r = await api.requestOtp(phone);
      setDevOtp(r.dev_otp || "");
      setCool(r.resend_in);
      setCode("");
      setStep("otp");
    } catch (x) {
      setErr(x.message);
    } finally {
      setBusy(false);
    }
  }

  async function verify(c) {
    setErr("");
    setBusy(true);
    try {
      const r = await api.verifyOtp(phone, c);
      setSession(r.token, r.user);
      toast.success(r.is_new ? "Welcome to Learnova!" : "Welcome back!");
      navigate(r.user.completed ? from : "/welcome", { replace: true });
    } catch (x) {
      setErr(x.message);
      setCode("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div data-learnova-app className="au">
      <div className="au-aurora" />
      <Blobs />
      <Link to="/" className="au-logo"><Sparkles size={18} /> Learnova</Link>
      <motion.div className="au-card" initial={{ opacity: 0, y: 30, rotateX: 8 }} animate={{ opacity: 1, y: 0, rotateX: 0 }} transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}>
        <AnimatePresence mode="wait">
          {step === "phone" ? (
            <motion.form key="p" onSubmit={send} initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}>
              <span className="au-badge"><Smartphone size={22} /></span>
              <h1>Sign in with your mobile</h1>
              <p>We'll text you a 6-digit code. New here? An account is created automatically.</p>
              <div className="au-phone">
                <select value={cc} onChange={(e) => setCc(e.target.value)} aria-label="Country code">
                  {COUNTRIES.map(([c, l]) => <option key={c} value={c}>{l} {c}</option>)}
                </select>
                <input type="tel" inputMode="tel" autoFocus placeholder="98765 43210" value={num} onChange={(e) => setNum(e.target.value)} aria-label="Mobile number" />
              </div>
              {err && <div className="au-err" role="alert">{err}</div>}
              <button className="au-btn" disabled={busy || num.replace(/\D/g, "").length < 7}>
                {busy ? <Loader2 className="spin" size={18} /> : <>Send code <ArrowRight size={18} /></>}
              </button>
            </motion.form>
          ) : (
            <motion.div key="o" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 20 }}>
              <button className="au-back" onClick={() => { setStep("phone"); setErr(""); }}><ArrowLeft size={16} /> Change number</button>
              <span className="au-badge"><ShieldCheck size={22} /></span>
              <h1>Enter the code</h1>
              <p>Sent to <b>{phone}</b></p>
              <OtpBoxes value={code} onChange={setCode} onDone={verify} disabled={busy} />
              {devOtp && (
                <button className="au-dev" onClick={() => { setCode(devOtp); verify(devOtp); }}>
                  Dev mode: tap to autofill <b>{devOtp}</b>
                </button>
              )}
              {err && <div className="au-err" role="alert">{err}</div>}
              <button className="au-btn" disabled={busy || code.length < LEN} onClick={() => verify(code)}>
                {busy ? <Loader2 className="spin" size={18} /> : "Verify & continue"}
              </button>
              <button className="au-link" disabled={cool > 0 || busy} onClick={send}>
                {cool > 0 ? `Resend code in ${cool}s` : "Resend code"}
              </button>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
    </div>
  );
}
