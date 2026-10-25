import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import * as api from "@/api";

const CHANGED = "lv:decks-changed";
const notify = () => window.dispatchEvent(new Event(CHANGED));

/** Load the signed-in user's saved decks, with a refresh + delete helper. */
export function useDecks() {
  const [decks, setDecks] = useState(null);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    api
      .listMyDecks()
      .then((r) => setDecks(Array.isArray(r) ? r : r?.decks ?? []))
      .catch((e) => {
        setError(e.message);
        setDecks([]);
      });
  }, []);

  useEffect(load, [load]);
  useEffect(() => {
    window.addEventListener(CHANGED, load);
    return () => window.removeEventListener(CHANGED, load);
  }, [load]);

  const remove = useCallback(async (id) => {
    try {
      await api.deleteDeck(id);
      setDecks((d) => (d || []).filter((x) => deckId(x) !== id));
      notify();
    } catch (e) {
      setError(e.message);
      toast.error(e.message || "Could not delete the deck");
    }
  }, []);

  /** Hide now, toast with Undo, and only hit the API once the undo window closes. */
  const removeWithUndo = useCallback((deck) => {
    const id = deckId(deck);
    let undone = false;
    setDecks((d) => (d || []).filter((x) => deckId(x) !== id));
    const timer = setTimeout(async () => {
      if (undone) return;
      try {
        await api.deleteDeck(id);
        notify();
      } catch (e) {
        toast.error(e.message || "Could not delete the deck");
        notify();
      }
    }, 6000);
    toast(`Deleted “${deckTitle(deck)}”`, {
      duration: 6000,
      action: {
        label: "Undo",
        onClick: () => {
          undone = true;
          clearTimeout(timer);
          load();
        },
      },
    });
  }, [load]);

  return { decks, error, reload: load, remove, removeWithUndo };
}

export const deckId = (d) => d.id ?? d.deck_id;
export const deckTitle = (d) => d.title ?? d.source_name ?? "Untitled deck";
