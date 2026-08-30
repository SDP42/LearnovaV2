import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Browser voice I/O for the assistant (spec Phase 8).
 *
 *   speech in  → Web Speech `SpeechRecognition`  → onResult(finalText)
 *   speech out → `speechSynthesis.speak(...)`     (barge-in: any new listen or
 *                a call to `stopSpeaking()` cancels the current utterance)
 *
 * Degrades quietly: `supported` is false where the APIs are missing, and the
 * widget falls back to text-only.
 */
export function useVoice({ onResult } = {}) {
  const SR =
    typeof window !== "undefined" &&
    (window.SpeechRecognition || window.webkitSpeechRecognition);
  const synth = typeof window !== "undefined" ? window.speechSynthesis : null;
  const supported = Boolean(SR) && Boolean(synth);

  const [listening, setListening] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [partial, setPartial] = useState("");
  const recRef = useRef(null);
  const onResultRef = useRef(onResult);
  onResultRef.current = onResult;

  useEffect(() => {
    if (!SR) return undefined;
    const rec = new SR();
    rec.lang = "en-US";
    rec.interimResults = true;
    rec.continuous = false;
    rec.onresult = (e) => {
      let finalT = "";
      let interim = "";
      for (let i = e.resultIndex; i < e.results.length; i += 1) {
        const t = e.results[i][0].transcript;
        if (e.results[i].isFinal) finalT += t;
        else interim += t;
      }
      setPartial(interim || finalT);
      if (finalT.trim()) {
        setPartial("");
        onResultRef.current?.(finalT.trim());
      }
    };
    rec.onerror = () => setListening(false);
    rec.onend = () => setListening(false);
    recRef.current = rec;
    return () => {
      try {
        rec.abort();
      } catch {
        /* noop */
      }
    };
  }, [SR]);

  const stopSpeaking = useCallback(() => {
    try {
      synth?.cancel();
    } catch {
      /* noop */
    }
    setSpeaking(false);
  }, [synth]);

  const speak = useCallback(
    (text) => {
      if (!synth || !text) return;
      stopSpeaking();
      const u = new SpeechSynthesisUtterance(String(text));
      u.rate = 1.05;
      u.onend = () => setSpeaking(false);
      u.onerror = () => setSpeaking(false);
      setSpeaking(true);
      synth.speak(u);
    },
    [synth, stopSpeaking]
  );

  const listen = useCallback(() => {
    if (!recRef.current || listening) return;
    stopSpeaking(); // barge-in
    setPartial("");
    try {
      recRef.current.start();
      setListening(true);
    } catch {
      setListening(false);
    }
  }, [listening, stopSpeaking]);

  const stopListening = useCallback(() => {
    try {
      recRef.current?.stop();
    } catch {
      /* noop */
    }
    setListening(false);
  }, []);

  return { supported, listening, speaking, partial, listen, stopListening, speak, stopSpeaking };
}
