import { useEffect, useState } from "react";
import { KeyRound } from "lucide-react";
import { toast } from "sonner";
import * as api from "@/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

/** Add or remove AI provider keys. Keys are stored on the server and never shown again. */
export default function ProviderKeys() {
  const [st, setSt] = useState(null);
  const [draft, setDraft] = useState({});
  const [busy, setBusy] = useState("");

  useEffect(() => {
    api.providersStatus().then(setSt).catch(() => setSt({ providers: [], editable: false }));
  }, []);

  const save = async (id) => {
    setBusy(id);
    try {
      const next = await api.saveProviderKey(id, (draft[id] || "").trim());
      setSt(next);
      setDraft((d) => ({ ...d, [id]: "" }));
      toast.success(next.verified === false ? "Saved, but the provider could not confirm it" : "Key saved");
    } catch (e) {
      toast.error(e.message || "Could not save the key");
    } finally {
      setBusy("");
    }
  };
  const remove = async (id) => {
    setBusy(id);
    try {
      setSt(await api.removeProviderKey(id));
      toast.success("Key removed");
    } catch (e) {
      toast.error(e.message || "Could not remove the key");
    } finally {
      setBusy("");
    }
  };

  if (!st) return <div className="lv-skel h-24" />;
  return (
    <div className="space-y-3">
      <p className="text-xs leading-5 text-[#715A4E]">
        AI rewriting: <b>{st.llm ? "on" : "off"}</b> · Picture generation: <b>{st.image_ai ? `on (${st.image_model || st.image_provider})` : "off — drawn illustrations are used"}</b>
      </p>
      {st.providers.map((p) => (
        <div key={p.id} className="rounded-xl border border-[#E8D8C9] bg-white p-3">
          <div className="flex items-center gap-2">
            <KeyRound className="size-4 text-[#8F3A18]" />
            <span className="text-sm font-semibold">{p.name}</span>
            <span className={`ml-auto rounded-full px-2 py-0.5 text-[11px] font-semibold ${p.configured ? "bg-[#E3F4E6] text-[#1E6B34]" : "bg-[#F3E6DA] text-[#664F44]"}`}>
              {p.configured ? "Connected" : "Not set"}
            </span>
          </div>
          <p className="mt-1 text-xs leading-5 text-[#715A4E]">{p.hint}</p>
          {st.editable ? (
            <div className="mt-2 flex gap-2">
              <Input type="password" autoComplete="off" placeholder={p.configured ? "Replace key" : "Paste API key"} value={draft[p.id] || ""}
                onChange={(e) => setDraft((d) => ({ ...d, [p.id]: e.target.value }))} aria-label={`${p.name} key`} />
              <Button size="sm" disabled={busy === p.id || (draft[p.id] || "").trim().length < 16} onClick={() => save(p.id)}>Save</Button>
              {p.configured ? <Button size="sm" variant="outline" disabled={busy === p.id} onClick={() => remove(p.id)}>Remove</Button> : null}
            </div>
          ) : null}
        </div>
      ))}
      {!st.editable ? <p className="text-xs text-[#715A4E]">Keys are set on the server in this deployment.</p> : null}
    </div>
  );
}
