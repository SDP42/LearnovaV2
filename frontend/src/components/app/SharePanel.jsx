import { useEffect, useState } from "react";
import { BookOpenCheck, Copy, Link2, Trash2 } from "lucide-react";
import { toast } from "sonner";
import * as api from "@/api";
import { Button } from "@/components/ui/button";

const PACK = [
  ["flashcards", "Flashcards (CSV)", "csv"],
  ["flashcards_anki", "Anki deck (TXT)", "txt"],
  ["quiz_csv", "Quiz bank (CSV)", "csv"],
  ["quiz_json", "Quiz bank (JSON)", "json"],
  ["cheatsheet", "One-page cheat sheet", "html"],
  ["script", "Narration script", "md"],
];

/** Public read-only links for a deck, and the study pack built from it. */
export default function SharePanel({ deckId, name = "deck" }) {
  const [links, setLinks] = useState([]);
  const [busy, setBusy] = useState(false);

  const load = () => api.listShares(deckId).then((r) => setLinks((r.shares || []).filter((l) => !l.revoked))).catch(() => setLinks([]));
  useEffect(() => { load(); }, [deckId]); // eslint-disable-line react-hooks/exhaustive-deps

  const make = async () => {
    setBusy(true);
    try {
      const r = await api.createShare(deckId, 30);
      await navigator.clipboard?.writeText(r.url).catch(() => {});
      toast.success("Link created and copied — anyone with it can view the deck for 30 days");
      load();
    } catch (e) {
      toast.error(e.message || "Could not create a link (save the deck to your library first)");
    } finally {
      setBusy(false);
    }
  };
  const url = (t) => `${window.location.origin}/api/share/${t}`;
  const pack = async (kind, label, ext) => {
    try {
      await api.downloadArtifact(api.studyPackPath(deckId, kind), `${name}_${kind}.${ext}`);
    } catch (e) {
      toast.error(e.message || `Could not download ${label}`);
    }
  };

  return (
    <div className="grid w-full gap-4 text-left sm:grid-cols-2">
      <div className="lv-surface p-4">
        <p className="flex items-center gap-2 text-sm font-semibold"><Link2 className="size-4 text-[#8F3A18]" /> Share a view-only link</p>
        <p className="mt-1 text-xs leading-5 text-[#4F3A31]">No sign-in needed to watch. You can turn a link off at any time.</p>
        <Button size="sm" className="mt-3" onClick={make} disabled={busy}>{busy ? "Creating…" : "Create link"}</Button>
        <ul className="mt-3 space-y-2">
          {links.map((l) => (
            <li key={l.token} className="flex items-center gap-2 rounded-lg bg-white px-2 py-1.5 text-xs">
              <span className="min-w-0 flex-1 truncate">{url(l.token)}</span>
              <button type="button" aria-label="Copy link" onClick={() => navigator.clipboard?.writeText(url(l.token)).then(() => toast.success("Copied"))}><Copy className="size-3.5" /></button>
              <button type="button" aria-label="Turn link off" onClick={() => api.revokeShare(deckId, l.token).then(load).catch((e) => toast.error(e.message))}><Trash2 className="size-3.5" /></button>
            </li>
          ))}
        </ul>
      </div>
      <div className="lv-surface p-4">
        <p className="flex items-center gap-2 text-sm font-semibold"><BookOpenCheck className="size-4 text-[#8F3A18]" /> Study pack</p>
        <p className="mt-1 text-xs leading-5 text-[#4F3A31]">Built from this deck’s own content.</p>
        <div className="mt-3 flex flex-wrap gap-2">
          {PACK.map(([k, label, ext]) => (
            <Button key={k} size="sm" variant="outline" onClick={() => pack(k, label, ext)}>{label}</Button>
          ))}
        </div>
      </div>
    </div>
  );
}
