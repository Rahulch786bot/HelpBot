import { useState, useRef, useEffect } from "react";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const AGENT_LABEL = {
  rag_agent: "Knowledge Agent",
  ticket_agent: "Ticket Agent",
  sensitive_guardrail: "Policy Guardrail",
};

const SUGGESTIONS = [
  "How many days of casual leave do I get per year?",
  "What's the per diem for domestic travel?",
  "My VPN keeps disconnecting every few minutes.",
  "What's the status of ticket TCK-1015?",
  "Can you escalate ticket TCK-1016?",
];

function TraceView({ msg }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="trace">
      <button className="trace-toggle" onClick={() => setOpen((o) => !o)}>
        {open ? "▾" : "▸"} routing trace ({msg.handled_by ? AGENT_LABEL[msg.handled_by] || msg.handled_by : "..."})
      </button>
      {open && (
        <ul>
          {msg.trace?.map((t, i) => (
            <li key={i}>{t}</li>
          ))}
          {msg.rag_citations?.length > 0 && (
            <li>
              citations:{" "}
              {msg.rag_citations
                .map((c) => `${c.source} § ${c.section}`)
                .join("; ")}
            </li>
          )}
        </ul>
      )}
    </div>
  );
}

export default function App() {
  const [messages, setMessages] = useState([
    {
      role: "bot",
      text:
        "Hi, I'm HelpBot — the Nimbus Corp internal helpdesk assistant. Ask me a policy question, report an issue, or check on an existing ticket.",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function send(text) {
    const query = (text ?? input).trim();
    if (!query || loading) return;
    setMessages((m) => [...m, { role: "user", text: query }]);
    setInput("");
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
      });
      if (!res.ok) throw new Error(`API error ${res.status}`);
      const data = await res.json();
      setMessages((m) => [
        ...m,
        {
          role: "bot",
          text: data.final_answer,
          intent: data.intent,
          handled_by: data.handled_by,
          trace: data.trace,
          rag_citations: data.rag_citations,
        },
      ]);
    } catch (err) {
      setMessages((m) => [
        ...m,
        {
          role: "bot",
          text: `Sorry — I couldn't reach the HelpBot backend (${err.message}). Is it running at ${API_URL}?`,
          error: true,
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function onKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  return (
    <div className="shell">
      <header className="header">
        <div className="logo">HB</div>
        <div>
          <h1>HelpBot</h1>
          <p>Nimbus Corp internal helpdesk assistant</p>
        </div>
      </header>

      <main className="chat">
        {messages.map((m, i) => (
          <div key={i} className={`bubble-row ${m.role}`}>
            <div className={`bubble ${m.role} ${m.error ? "error" : ""}`}>
              <p>{m.text}</p>
              {m.role === "bot" && m.handled_by && <TraceView msg={m} />}
            </div>
          </div>
        ))}
        {loading && (
          <div className="bubble-row bot">
            <div className="bubble bot typing">
              <span></span>
              <span></span>
              <span></span>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </main>

      {messages.length <= 1 && (
        <div className="suggestions">
          {SUGGESTIONS.map((s) => (
            <button key={s} onClick={() => send(s)}>
              {s}
            </button>
          ))}
        </div>
      )}

      <footer className="composer">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Ask a question, report an issue, or check a ticket..."
          rows={1}
        />
        <button onClick={() => send()} disabled={loading || !input.trim()}>
          Send
        </button>
      </footer>
    </div>
  );
}
