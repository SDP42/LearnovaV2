import { useCallback, useEffect, useState } from "react";
import * as api from "@/api";

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

  const remove = useCallback(
    async (id) => {
      try {
        await api.deleteDeck(id);
        setDecks((d) => (d || []).filter((x) => (x.id ?? x.deck_id) !== id));
      } catch (e) {
        setError(e.message);
      }
    },
    []
  );

  return { decks, error, reload: load, remove };
}

export const deckId = (d) => d.id ?? d.deck_id;
export const deckTitle = (d) => d.title ?? d.source_name ?? "Untitled deck";
