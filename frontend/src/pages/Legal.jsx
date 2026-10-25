import { Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import "./auth.css";

const DOCS = {
  privacy: {
    title: "Privacy Policy",
    sections: [
      ["What we collect", "Your mobile number (to sign you in), the profile details you choose to add (name, optional email, role, organisation), the documents and decks you create, and basic first-party usage events such as which pages you open."],
      ["How we use it", "To authenticate you, store and render your decks, keep the service secure and reliable, and understand which features are used. We do not sell your data and we do not use third-party advertising trackers."],
      ["Verification codes", "One-time codes are stored only as a salted hash, expire after five minutes, and can be used once. Your number is sent to an SMS provider solely to deliver the code."],
      ["Retention & deletion", "You can delete your account at any time from Settings → Account. This permanently erases your profile, sessions and saved decks. Backups are rotated and older copies are removed automatically."],
      ["Security", "Sessions use random tokens stored hashed, requests are rate-limited, and every deck is scoped to its owner. No system is perfectly secure; report problems to the contact below."],
      ["Contact", "Questions or requests: privacy@learnova.example (replace with your real address before launch)."],
    ],
  },
  terms: {
    title: "Terms of Service",
    sections: [
      ["Using Learnova", "You may use Learnova to turn your own content into presentations. You are responsible for having the right to upload and process the content you provide."],
      ["Your content", "You keep ownership of what you upload and generate. You grant us permission to process it only to operate the service for you."],
      ["Acceptable use", "No unlawful content, no attempts to break, probe or overload the service, and no sharing of your account."],
      ["AI output", "Generated slides and quizzes may contain mistakes. Review them before presenting or publishing."],
      ["Availability", "The service is provided as is, without warranty, and may change or be interrupted. We may suspend accounts that abuse it."],
      ["Termination", "You can delete your account at any time. These terms are a template and should be reviewed by a lawyer before launch."],
    ],
  },
};

export default function Legal({ kind }) {
  const d = DOCS[kind];
  return (
    <div data-learnova-app className="au" style={{ placeItems: "start center", paddingTop: 70 }}>
      <div className="au-aurora" />
      <Link to="/" className="au-logo"><ArrowLeft size={16} /> Learnova</Link>
      <article className="au-card" style={{ maxWidth: 720, gap: 22 }}>
        <h1 style={{ fontSize: 34 }}>{d.title}</h1>
        <p>Last updated 25 October 2026</p>
        {d.sections.map(([h, b]) => (
          <section key={h}><h2 style={{ fontSize: 18, margin: "0 0 6px" }}>{h}</h2><p>{b}</p></section>
        ))}
      </article>
    </div>
  );
}
