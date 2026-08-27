/**
 * ChatPage — Dark glassmorphism, full ds-* design system.
 * FHIR RAG chatbot powered by Ollama phi3 (local, no API key required).
 */
import React, { useState, useRef, useEffect } from 'react';
import { ragApi } from '../shared/services/api';
import { Brain, Send, User, Loader2, RotateCcw, Info, WifiOff } from 'lucide-react';

// ── Types ─────────────────────────────────────────────────────────────────────
interface Message {
  id: number; role: 'user' | 'assistant';
  content: string; timestamp: Date;
  model?: string; isError?: boolean;
}
interface RagStatus {
  status: 'operational' | 'unavailable';
  chat_model: string; mapping_model: string; total_mappings: number;
}

// ── Constants ─────────────────────────────────────────────────────────────────
const SUGGESTED_QUESTIONS = [
  'What FHIR path maps to a patient date of birth?',
  'How does CareLock map medication dosage to FHIR?',
  'Which FHIR resource stores lab results?',
  'What is the FHIR path for encounter diagnosis?',
  'How is patient identifier mapped from a source database?',
];

const INITIAL_MESSAGE: Message = {
  id: 0, role: 'assistant',
  content:
    "Hello! I'm the CareLock Sync AI assistant, powered by Ollama phi3 running locally on your machine.\n\n" +
    "I can answer questions about FHIR R4 mappings, schema transformations, and how hospital data " +
    "maps to the FHIR standard. My answers are grounded in the CareLock mapping knowledge base.\n\n" +
    "What would you like to know?",
  timestamp: new Date(), model: 'phi3',
};

// ── Main component ─────────────────────────────────────────────────────────────
const ChatPage: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([INITIAL_MESSAGE]);
  const [input, setInput]       = useState('');
  const [loading, setLoading]   = useState(false);
  const [ragStatus, setRagStatus] = useState<RagStatus | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef  = useRef<HTMLInputElement>(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);
  useEffect(() => {
    ragApi.status().then((s) => setRagStatus(s as RagStatus)).catch(() => setRagStatus(null));
  }, []);

  const sendMessage = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || loading) return;
    const userMsg: Message = { id: Date.now(), role: 'user', content: trimmed, timestamp: new Date() };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setLoading(true);
    try {
      const data = await ragApi.chat(trimmed);
      setMessages((prev) => [...prev, { id: Date.now() + 1, role: 'assistant', content: data.answer ?? 'No response received.', timestamp: new Date(), model: data.model ?? 'phi3' }]);
    } catch {
      setMessages((prev) => [...prev, { id: Date.now() + 1, role: 'assistant', content: 'RAG service unavailable.\n\nMake sure Ollama is running:\n  ollama serve\n\nAnd the phi3 model is pulled:\n  ollama pull phi3', timestamp: new Date(), isError: true }]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(input); }
  };

  const clearChat = () => setMessages([{ ...INITIAL_MESSAGE, id: Date.now(), timestamp: new Date(), content: 'Chat cleared. Ask me anything about FHIR mappings or schema transformations.' }]);

  const isOllamaReady = ragStatus?.status === 'operational';

  const card: React.CSSProperties = {
    background: 'var(--ds-card-bg)',
    backdropFilter: 'var(--ds-card-blur)',
    WebkitBackdropFilter: 'var(--ds-card-blur)' as any,
    border: '1px solid var(--ds-card-border)',
    borderRadius: '1rem',
    boxShadow: 'var(--ds-card-shadow)',
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 8rem)', gap: '1rem', fontFamily: "'Inter',sans-serif", maxWidth: 1100, margin: '0 auto' }}>

      {/* Header */}
      <div className="ds-animate" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0, flexWrap: 'wrap', gap: '0.75rem' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 800, color: 'var(--ds-text-primary)', letterSpacing: '-0.02em', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Brain style={{ width: 20, height: 20, color: 'var(--ds-accent-purple)' }} /> AI Assistant
          </h1>
          <p style={{ margin: '0.25rem 0 0', fontSize: '0.8125rem', color: 'var(--ds-text-muted)' }}>
            FHIR mapping Q&A powered by <span style={{ color: 'var(--ds-accent-purple)', fontWeight: 600 }}>Ollama phi3</span> 
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
          {ragStatus === null ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', fontSize: '0.75rem', color: 'var(--ds-status-pending-text)', background: 'var(--ds-status-pending-bg)', border: '1px solid rgba(245,158,11,0.3)', borderRadius: '0.5rem', padding: '0.375rem 0.75rem' }}>
              <WifiOff style={{ width: 12, height: 12 }} /> Backend offline
            </div>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', fontSize: '0.75rem', color: isOllamaReady ? 'var(--ds-status-active-text)' : 'var(--ds-status-pending-text)', background: isOllamaReady ? 'var(--ds-status-active-bg)' : 'var(--ds-status-pending-bg)', border: `1px solid ${isOllamaReady ? 'rgba(16,185,129,0.3)' : 'rgba(245,158,11,0.3)'}`, borderRadius: '0.5rem', padding: '0.375rem 0.75rem' }}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: isOllamaReady ? 'var(--ds-accent-green)' : 'var(--ds-accent-orange)', flexShrink: 0 }} />
              {isOllamaReady ? `${ragStatus.chat_model} · ${ragStatus.total_mappings} mappings` : 'Ollama offline — run: ollama serve'}
            </div>
          )}
          <button onClick={clearChat}
            style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', fontSize: '0.8125rem', color: 'var(--ds-text-muted)', background: 'var(--ds-surface)', border: '1px solid var(--ds-border)', borderRadius: '0.5rem', padding: '0.375rem 0.75rem', cursor: 'pointer', fontFamily: 'inherit', transition: 'all 0.2s' }}>
            <RotateCcw style={{ width: 12, height: 12 }} /> Clear
          </button>
        </div>
      </div>

      {/* Chat window */}
      <div className="ds-animate ds-animate-d1" style={{ ...card, flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column', minHeight: 0 }}>

        {/* Messages */}
        <div className="ds-scroll" style={{ flex: 1, overflowY: 'auto', padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {messages.map((msg) => (
            <div key={msg.id} style={{ display: 'flex', gap: '0.625rem', flexDirection: msg.role === 'user' ? 'row-reverse' : 'row', alignItems: 'flex-end' }}>
              {/* Avatar */}
              <div style={{ width: 30, height: 30, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, background: msg.role === 'user' ? 'rgba(59,130,246,0.18)' : msg.isError ? 'rgba(239,68,68,0.15)' : 'rgba(139,92,246,0.18)' }}>
                {msg.role === 'user'
                  ? <User  style={{ width: 13, height: 13, color: 'var(--ds-accent-blue)'   }} />
                  : <Brain style={{ width: 13, height: 13, color: msg.isError ? 'var(--ds-status-error-text)' : 'var(--ds-accent-purple)' }} />
                }
              </div>
              {/* Bubble */}
              <div style={{ maxWidth: '75%', borderRadius: '1rem', padding: '0.75rem 1rem', fontSize: '0.8125rem', lineHeight: 1.55, background: msg.role === 'user' ? 'linear-gradient(135deg,var(--ds-accent-blue),#4f46e5)' : msg.isError ? 'var(--ds-status-error-bg)' : 'var(--ds-surface)', border: `1px solid ${msg.role === 'user' ? 'transparent' : msg.isError ? 'rgba(239,68,68,0.3)' : 'var(--ds-table-border)'}`, borderBottomRightRadius: msg.role === 'user' ? '0.25rem' : '1rem', borderBottomLeftRadius: msg.role === 'user' ? '1rem' : '0.25rem' }}>
                <p style={{ margin: 0, whiteSpace: 'pre-wrap', color: msg.role === 'user' ? '#fff' : msg.isError ? 'var(--ds-status-error-text)' : 'var(--ds-text-primary)' }}>{msg.content}</p>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.375rem', fontSize: '0.6875rem', color: msg.role === 'user' ? 'rgba(255,255,255,0.6)' : 'var(--ds-text-muted)', justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start' }}>
                  <span>{msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                  {msg.model && (
                    <span style={{ background: 'rgba(139,92,246,0.15)', color: 'var(--ds-accent-purple)', padding: '0.1rem 0.375rem', borderRadius: '0.25rem', fontWeight: 600 }}>{msg.model}</span>
                  )}
                </div>
              </div>
            </div>
          ))}

          {/* Typing indicator */}
          {loading && (
            <div style={{ display: 'flex', gap: '0.625rem', alignItems: 'flex-end' }}>
              <div style={{ width: 30, height: 30, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(139,92,246,0.18)', flexShrink: 0 }}>
                <Brain style={{ width: 13, height: 13, color: 'var(--ds-accent-purple)' }} />
              </div>
              <div style={{ background: 'var(--ds-surface)', border: '1px solid var(--ds-table-border)', borderRadius: '1rem', borderBottomLeftRadius: '0.25rem', padding: '0.75rem 1rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.8125rem', color: 'var(--ds-text-muted)' }}>
                  <Loader2 style={{ width: 13, height: 13, animation: 'spin 0.8s linear infinite' }} />
                  phi3 is thinking…
                </div>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Suggested questions */}
        {messages.length <= 1 && (
          <div style={{ padding: '0.75rem 1.25rem', flexShrink: 0, borderTop: '1px solid var(--ds-table-border)' }}>
            <p style={{ margin: '0 0 0.5rem', display: 'flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.6875rem', color: 'var(--ds-text-muted)' }}>
              <Info style={{ width: 11, height: 11 }} /> Suggested questions
            </p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.375rem' }}>
              {SUGGESTED_QUESTIONS.map((q) => (
                <button key={q} onClick={() => sendMessage(q)} disabled={loading || !isOllamaReady}
                  style={{ fontSize: '0.6875rem', background: 'rgba(139,92,246,0.10)', color: 'var(--ds-accent-purple)', border: '1px solid rgba(139,92,246,0.25)', borderRadius: '2rem', padding: '0.25rem 0.625rem', cursor: 'pointer', fontFamily: 'inherit', transition: 'all 0.2s', opacity: (loading || !isOllamaReady) ? 0.4 : 1 }}>
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Input bar */}
        <div style={{ borderTop: '1px solid var(--ds-table-border)', padding: '0.875rem 1rem', flexShrink: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={isOllamaReady ? 'Ask about FHIR mappings, data transformations…' : 'Start Ollama first: ollama serve'}
              disabled={loading}
              style={{ flex: 1, background: 'var(--ds-surface)', border: '1px solid var(--ds-border)', borderRadius: '0.75rem', padding: '0.625rem 1rem', fontSize: '0.8125rem', color: 'var(--ds-text-primary)', outline: 'none', fontFamily: 'inherit', transition: 'border-color 0.2s, box-shadow 0.2s', opacity: loading ? 0.6 : 1 }}
              onFocus={e => { e.target.style.borderColor = 'var(--ds-accent-purple)'; e.target.style.boxShadow = '0 0 0 3px rgba(139,92,246,0.18)'; }}
              onBlur={e => { e.target.style.borderColor = 'var(--ds-border)'; e.target.style.boxShadow = 'none'; }}
            />
            <button
              onClick={() => sendMessage(input)}
              disabled={loading || !input.trim() || !isOllamaReady}
              style={{ width: 38, height: 38, borderRadius: '0.625rem', background: 'linear-gradient(135deg,var(--ds-accent-purple),#4f46e5)', color: '#fff', border: 'none', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', transition: 'opacity 0.2s', opacity: (loading || !input.trim() || !isOllamaReady) ? 0.45 : 1, flexShrink: 0 }}
            >
              {loading ? <Loader2 style={{ width: 14, height: 14, animation: 'spin 0.8s linear infinite' }} /> : <Send style={{ width: 14, height: 14 }} />}
            </button>
          </div>
          <p style={{ margin: '0.375rem 0 0', fontSize: '0.6875rem', color: 'var(--ds-text-muted)', paddingLeft: '0.25rem' }}>
            Press Enter to send · Shift+Enter for new line · Powered by Ollama phi3 (local)
          </p>
        </div>
      </div>
    </div>
  );
};

export default ChatPage;
