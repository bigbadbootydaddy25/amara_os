import { useState, useRef, useEffect } from "react";
import { api } from "../api/client";
import styles from "./AssistantPanel.module.css";

interface Message {
  role: "user" | "assistant";
  text: string;
  ts: number;
}

interface Props {
  parcelId: number;
}

// ─── AI Adapter hook (swap implementation to use real AI) ─────────────────────
// When you wire in a real provider:
// 1. Change `api.assistantQuery` in api/client.ts to call your AI endpoint.
// 2. Or replace the call below with a direct fetch to Perplexity/OpenAI.
// Everything else in this component stays the same.
async function sendToAI(
  parcelId: number,
  message: string
): Promise<string> {
  const res = await api.assistantQuery(parcelId, message);
  return res.answer;
}
// ─────────────────────────────────────────────────────────────────────────────

export function AssistantPanel({ parcelId }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  // Scroll to bottom on new message
  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [messages]);

  // Reset history when switching parcels
  useEffect(() => {
    setMessages([]);
    setError(null);
  }, [parcelId]);

  async function submit() {
    const text = input.trim();
    if (!text || sending) return;

    const userMsg: Message = { role: "user", text, ts: Date.now() };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setSending(true);
    setError(null);

    try {
      const answer = await sendToAI(parcelId, text);
      setMessages((prev) => [...prev, { role: "assistant", text: answer, ts: Date.now() }]);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSending(false);
      inputRef.current?.focus();
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  /** "Speak" button: when you wire in Web Speech API, replace this handler.
   *  For now it just focuses the input to simulate mic activation. */
  function handleSpeak() {
    // TODO: wire in window.SpeechRecognition / webkitSpeechRecognition
    // Example:
    //   const recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
    //   recognition.onresult = (e) => setInput(e.results[0][0].transcript);
    //   recognition.start();
    inputRef.current?.focus();
  }

  return (
    <div className={styles.root}>
      <div className={styles.header}>
        <span className={styles.title}>PropVision Assistant</span>
        <span className={styles.badge}>AI</span>
      </div>

      <div className={styles.messages} ref={listRef}>
        {messages.length === 0 && (
          <div className={styles.placeholder}>
            Ask anything about this parcel — zoning, feasibility, comparables…
          </div>
        )}
        {messages.map((m) => (
          <div
            key={m.ts}
            className={`${styles.bubble} ${m.role === "user" ? styles.user : styles.assistant}`}
          >
            <span className={styles.bubbleRole}>{m.role === "user" ? "You" : "PropVision"}</span>
            <p className={styles.bubbleText}>{m.text}</p>
          </div>
        ))}
        {sending && (
          <div className={`${styles.bubble} ${styles.assistant}`}>
            <span className={styles.bubbleRole}>PropVision</span>
            <p className={styles.thinking}>Thinking…</p>
          </div>
        )}
      </div>

      {error && <div className={styles.error}>{error}</div>}

      <div className={styles.inputRow}>
        <button
          className={styles.speakBtn}
          onClick={handleSpeak}
          title="Speak (coming soon — wires to microphone)"
        >
          🎙
        </button>
        <input
          ref={inputRef}
          className={styles.input}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about this parcel…"
          disabled={sending}
        />
        <button
          className={styles.sendBtn}
          onClick={submit}
          disabled={sending || !input.trim()}
        >
          Send
        </button>
      </div>
    </div>
  );
}
