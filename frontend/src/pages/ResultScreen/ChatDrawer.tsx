import { useEffect, useRef, useState } from "react";
import type { ClassificationResult, ChatResponse } from "../../types";
import useAxios from "@/hooks/useAxios";
import { authHeaders } from "@/utils/header";

interface Message {
  id: number;
  role: "user" | "bot";
  text: string;
  pending?: boolean;
}

interface Props {
  result: ClassificationResult;
  open: boolean;
  onClose: () => void;
}

const SUGGESTED_QUESTIONS = [
  "라벨을 꼭 제거해야 하나요?",
  "씻기 어려울 때는 어떻게 하나요?",
  "수거함이 근처에 없으면요?",
  "비슷한 품목도 같은 방법인가요?",
];

let msgId = 0;

export default function ChatDrawer({ result, open, onClose }: Props) {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: ++msgId,
      role: "bot",
      text: `안녕하세요! ${result.itemName} 분리배출에 대해 궁금한 점을 질문해 주세요. ${result.regionName} 기준으로 답변해 드릴게요.`,
    },
  ]);
  const [input, setInput] = useState("");
  const [typing, setTyping] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // 실제 백엔드 POST /api/v1/chat (agent/service.py -> RAG chatbot_node) 호출.
  // feedback_id로 이미 분류된 major/minor_category를 백엔드가 그대로 사용하므로
  // 여기서는 자유 질문(message)만 실어 보낸다.
  const { refetch: chatRequest } = useAxios<ChatResponse>(
    "",
    { method: "post" },
    false,
  );

  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 400);
  }, [open]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, typing]);

  async function sendMessage(text: string) {
    if (!text.trim() || typing) return;
    const userMsg: Message = { id: ++msgId, role: "user", text: text.trim() };
    setMessages((m) => [...m, userMsg]);
    setInput("");
    setTyping(true);

    if (!result.feedbackId) {
      setMessages((m) => [
        ...m,
        {
          id: ++msgId,
          role: "bot",
          text: "이 결과에는 챗봇 상담을 연결할 수 없어요. 사진을 다시 분석한 뒤 이용해 주세요.",
        },
      ]);
      setTyping(false);
      return;
    }

    try {
      const res = await chatRequest({
        url: "/api/v1/chat",
        data: { feedback_id: result.feedbackId, message: text.trim() },
        headers: authHeaders(),
      });
      setMessages((m) => [
        ...m,
        { id: ++msgId, role: "bot", text: res.answer },
      ]);
    } catch (e) {
      console.error("chat 요청 실패", e);
      setMessages((m) => [
        ...m,
        {
          id: ++msgId,
          role: "bot",
          text: "답변을 가져오는 중 문제가 발생했어요. 잠시 후 다시 시도해 주세요.",
        },
      ]);
    } finally {
      setTyping(false);
    }
  }

  function handleSuggest(q: string) {
    sendMessage(q);
  }

  // Bold **text** renderer (simple)
  function renderText(text: string) {
    const parts = text.split(/(\*\*[^*]+\*\*)/);
    return parts.map((p, i) =>
      p.startsWith("**") ? <strong key={i}>{p.slice(2, -2)}</strong> : p,
    );
  }

  const showSuggestions = messages.length === 1;

  return (
    <>
      {/* Backdrop */}
      <div
        className={`fixed inset-0 bg-black/40 z-30 transition-opacity duration-300 ${open ? "opacity-100" : "opacity-0 pointer-events-none"}`}
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Drawer */}
      <div
        className={`fixed bottom-0 left-1/2 -translate-x-1/2 w-full max-w-[430px] z-40 flex flex-col bg-background rounded-t-3xl shadow-2xl transition-transform duration-300 ease-out ${open ? "translate-y-0" : "translate-y-full"}`}
        style={{ height: "78%" }}
        role="dialog"
        aria-label="분리배출 AI 상담"
      >
        {/* Handle */}
        <div className="flex justify-center pt-3 pb-1 flex-shrink-0">
          <div className="w-10 h-1 rounded-full bg-border" />
        </div>

        {/* Header */}
        <div className="flex items-center gap-3 px-5 py-3 border-b border-border flex-shrink-0">
          <div className="w-8 h-8 rounded-xl bg-primary flex items-center justify-center flex-shrink-0">
            <svg
              viewBox="0 0 20 20"
              fill="currentColor"
              className="w-4 h-4 text-primary-foreground"
              aria-hidden="true"
            >
              <path d="M3.505 2.365A41.369 41.369 0 0 1 9 2c1.863 0 3.697.124 5.495.365 1.247.167 2.318 1.174 2.429 2.428A44.198 44.198 0 0 1 17 8c0 1.077-.06 2.137-.174 3.177-.11 1.014-.98 1.848-2.012 1.978L10 14l-2.404 2.403A1 1 0 0 1 6 15.699V14H5.63c-1.241 0-2.27-.87-2.44-2.1A44.12 44.12 0 0 1 3 8c0-.965.057-1.916.168-2.852a2.52 2.52 0 0 1 .337-.783z" />
            </svg>
          </div>
          <div className="flex-1">
            <p className="text-sm font-bold text-foreground">
              AI 분리배출 상담
            </p>
            <p className="text-xs text-muted-foreground">
              {result.itemName} · {result.regionName}
            </p>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-full bg-muted flex items-center justify-center text-muted-foreground hover:bg-border transition-colors"
            aria-label="닫기"
          >
            <svg
              viewBox="0 0 20 20"
              fill="currentColor"
              className="w-4 h-4"
              aria-hidden="true"
            >
              <path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22z" />
            </svg>
          </button>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto no-scrollbar px-4 py-4 flex flex-col gap-3">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              {msg.role === "bot" && (
                <div className="w-6 h-6 rounded-full bg-primary flex items-center justify-center flex-shrink-0 mr-2 mt-0.5">
                  <svg
                    viewBox="0 0 20 20"
                    fill="currentColor"
                    className="w-3 h-3 text-primary-foreground"
                    aria-hidden="true"
                  >
                    <path d="M3.505 2.365A41.369 41.369 0 0 1 9 2c1.863 0 3.697.124 5.495.365 1.247.167 2.318 1.174 2.429 2.428A44.198 44.198 0 0 1 17 8c0 1.077-.06 2.137-.174 3.177-.11 1.014-.98 1.848-2.012 1.978L10 14l-2.404 2.403A1 1 0 0 1 6 15.699V14H5.63c-1.241 0-2.27-.87-2.44-2.1A44.12 44.12 0 0 1 3 8c0-.965.057-1.916.168-2.852a2.52 2.52 0 0 1 .337-.783z" />
                  </svg>
                </div>
              )}
              <div
                className={`max-w-[78%] px-4 py-2.5 rounded-2xl text-sm leading-relaxed ${
                  msg.role === "user"
                    ? "bg-primary text-primary-foreground rounded-tr-sm"
                    : "bg-muted text-foreground rounded-tl-sm"
                }`}
              >
                {renderText(msg.text)}
              </div>
            </div>
          ))}

          {/* Typing indicator */}
          {typing && (
            <div className="flex justify-start">
              <div className="w-6 h-6 rounded-full bg-primary flex items-center justify-center flex-shrink-0 mr-2 mt-0.5">
                <svg
                  viewBox="0 0 20 20"
                  fill="currentColor"
                  className="w-3 h-3 text-primary-foreground"
                  aria-hidden="true"
                >
                  <path d="M3.505 2.365A41.369 41.369 0 0 1 9 2c1.863 0 3.697.124 5.495.365 1.247.167 2.318 1.174 2.429 2.428A44.198 44.198 0 0 1 17 8c0 1.077-.06 2.137-.174 3.177-.11 1.014-.98 1.848-2.012 1.978L10 14l-2.404 2.403A1 1 0 0 1 6 15.699V14H5.63c-1.241 0-2.27-.87-2.44-2.1A44.12 44.12 0 0 1 3 8c0-.965.057-1.916.168-2.852a2.52 2.52 0 0 1 .337-.783z" />
                </svg>
              </div>
              <div className="bg-muted rounded-2xl rounded-tl-sm px-4 py-3 flex gap-1 items-center">
                {[0, 1, 2].map((i) => (
                  <div
                    key={i}
                    className="w-1.5 h-1.5 rounded-full bg-muted-foreground/50"
                    style={{
                      animation: `pulse 1.2s ease-in-out ${i * 0.2}s infinite`,
                    }}
                  />
                ))}
              </div>
            </div>
          )}

          {/* Suggested questions */}
          {showSuggestions && !typing && (
            <div className="flex flex-col gap-2 mt-1">
              <p className="text-xs text-muted-foreground px-1">
                자주 묻는 질문
              </p>
              <div className="flex flex-wrap gap-2">
                {SUGGESTED_QUESTIONS.map((q) => (
                  <button
                    key={q}
                    onClick={() => handleSuggest(q)}
                    className="px-3 py-1.5 rounded-full border border-border bg-card text-xs font-medium text-foreground hover:bg-secondary hover:border-primary/30 active:scale-95 transition-all"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="px-4 pb-8 pt-3 border-t border-border flex-shrink-0">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              sendMessage(input);
            }}
            className="flex items-center gap-2"
          >
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="궁금한 점을 입력하세요..."
              className="flex-1 px-4 py-3 rounded-xl border border-border bg-card text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-all"
            />
            <button
              type="submit"
              disabled={!input.trim() || typing}
              className="w-11 h-11 rounded-xl bg-primary text-primary-foreground flex items-center justify-center flex-shrink-0 disabled:opacity-40 disabled:cursor-not-allowed active:scale-95 transition-all"
              aria-label="전송"
            >
              <svg
                viewBox="0 0 20 20"
                fill="currentColor"
                className="w-4 h-4"
                aria-hidden="true"
              >
                <path d="M3.105 2.289a.75.75 0 0 0-.826.95l1.414 4.925A1.5 1.5 0 0 0 5.135 9.25h6.115a.75.75 0 0 1 0 1.5H5.135a1.5 1.5 0 0 0-1.442 1.086l-1.414 4.926a.75.75 0 0 0 .826.95 28.896 28.896 0 0 0 15.293-7.154.75.75 0 0 0 0-1.115A28.897 28.897 0 0 0 3.105 2.289z" />
              </svg>
            </button>
          </form>
        </div>
      </div>

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 0.3; transform: scale(0.8); }
          50% { opacity: 1; transform: scale(1); }
        }
      `}</style>
    </>
  );
}
