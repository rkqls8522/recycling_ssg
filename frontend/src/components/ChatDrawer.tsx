import { useEffect, useRef, useState } from "react"
import type { ClassificationResult } from "../types"

interface Message {
  id: number
  role: "user" | "bot"
  text: string
  pending?: boolean
}

interface Props {
  result: ClassificationResult
  open: boolean
  onClose: () => void
}

const SUGGESTED_QUESTIONS = [
  "라벨을 꼭 제거해야 하나요?",
  "씻기 어려울 때는 어떻게 하나요?",
  "수거함이 근처에 없으면요?",
  "비슷한 품목도 같은 방법인가요?",
]

// TODO: replace with real Upstage solar-pro2 call via /api/chat endpoint
function getMockResponse(question: string, result: ClassificationResult): string {
  const q = question
  const item = result.itemName
  const region = result.regionName
  const steps = result.guidelines.steps

  if (q.includes("라벨") || q.includes("스티커")) {
    return `네! ${item}의 경우 라벨(비닐 스티커)은 반드시 제거해야 합니다. 라벨이 붙은 채로 배출하면 재활용 선별 과정에서 오염 판정을 받아 일반쓰레기로 처리될 수 있어요. 라벨이 잘 안 떨어지면 물에 잠깐 불려서 제거하면 쉽게 됩니다.`
  }
  if (q.includes("씻") || q.includes("세척") || q.includes("더러")) {
    return `내용물을 비운 뒤 물로 한 번 헹구는 정도면 충분합니다. 완벽하게 세척할 필요는 없어요. 단, 기름이나 음식물이 많이 묻어 있어서 세척이 어렵다면 재활용이 불가하니 종량제 봉투에 넣어 일반쓰레기로 배출하세요.`
  }
  if (q.includes("수거함") || q.includes("위치") || q.includes("어디")) {
    return `${region} 수거함 위치는 해당 구청 홈페이지 또는 '내 손 안의 분리배출' 앱에서 확인할 수 있어요. 공동주택(아파트)이라면 단지 내 분리수거장을, 단독주택이라면 문 앞 또는 지정 거점 수거함을 이용하면 됩니다.`
  }
  if (q.includes("비슷") || q.includes("다른 품목") || q.includes("같은 방법")) {
    return `비슷하게 생겼더라도 소재에 따라 배출 방법이 다를 수 있습니다. 예를 들어 투명 페트병과 색이 있는 페트병은 수거함이 다르고, 유리병과 도자기도 다르게 처리됩니다. 헷갈릴 때는 품목을 다시 촬영해서 확인해 보세요!`
  }
  if (q.includes("요일") || q.includes("언제") || q.includes("수거일")) {
    return `${region} 기준 ${item}의 수거 요일은 ${result.guidelines.collectionDays}입니다. 수거 당일 오전까지 배출해 주시면 됩니다. 지역과 주택 유형에 따라 달라질 수 있으니 구청 공지를 함께 확인해 보세요.`
  }
  if (q.includes("뚜껑") || q.includes("캡")) {
    return `뚜껑은 ${item} 본체와 소재가 다를 수 있어서 분리 배출이 원칙입니다. 플라스틱 뚜껑은 플라스틱류, 금속 뚜껑은 금속류 수거함에 각각 넣어 주세요.`
  }

  // Generic fallback using guidelines context
  const stepSummary = steps.slice(0, 2).join(" → ")
  return `좋은 질문이에요! ${item} 배출 시 핵심은 "${stepSummary}" 순서로 처리하는 것입니다. 추가로 궁금한 점이 있으면 더 물어봐 주세요. 실제 서비스에서는 ${region} 기준 지침 문서를 근거로 더 정확한 답변을 드릴 수 있습니다.`
}

let msgId = 0

export default function ChatDrawer({ result, open, onClose }: Props) {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: ++msgId,
      role: "bot",
      text: `안녕하세요! **${result.itemName}** 분리배출에 대해 궁금한 점을 질문해 주세요. ${result.regionName} 기준으로 답변해 드릴게요.`,
    },
  ])
  const [input, setInput] = useState("")
  const [typing, setTyping] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 400)
  }, [open])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, typing])

  async function sendMessage(text: string) {
    if (!text.trim() || typing) return
    const userMsg: Message = { id: ++msgId, role: "user", text: text.trim() }
    setMessages((m) => [...m, userMsg])
    setInput("")
    setTyping(true)

    // TODO: POST /api/chat { question: text, itemName, regionCode, guidelines }
    //       with Upstage solar-pro2 via UPSTAGE_API_KEY
    await new Promise((r) => setTimeout(r, 900 + Math.random() * 600))
    const botText = getMockResponse(text, result)
    setMessages((m) => [...m, { id: ++msgId, role: "bot", text: botText }])
    setTyping(false)
  }

  function handleSuggest(q: string) {
    sendMessage(q)
  }

  // Bold **text** renderer (simple)
  function renderText(text: string) {
    const parts = text.split(/(\*\*[^*]+\*\*)/)
    return parts.map((p, i) =>
      p.startsWith("**") ? <strong key={i}>{p.slice(2, -2)}</strong> : p
    )
  }

  const showSuggestions = messages.length === 1

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
            <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 text-primary-foreground" aria-hidden="true">
              <path d="M3.505 2.365A41.369 41.369 0 0 1 9 2c1.863 0 3.697.124 5.495.365 1.247.167 2.318 1.174 2.429 2.428A44.198 44.198 0 0 1 17 8c0 1.077-.06 2.137-.174 3.177-.11 1.014-.98 1.848-2.012 1.978L10 14l-2.404 2.403A1 1 0 0 1 6 15.699V14H5.63c-1.241 0-2.27-.87-2.44-2.1A44.12 44.12 0 0 1 3 8c0-.965.057-1.916.168-2.852a2.52 2.52 0 0 1 .337-.783z" />
            </svg>
          </div>
          <div className="flex-1">
            <p className="text-sm font-bold text-foreground">AI 분리배출 상담</p>
            <p className="text-xs text-muted-foreground">{result.itemName} · {result.regionName}</p>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-full bg-muted flex items-center justify-center text-muted-foreground hover:bg-border transition-colors"
            aria-label="닫기"
          >
            <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4" aria-hidden="true">
              <path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22z" />
            </svg>
          </button>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto no-scrollbar px-4 py-4 flex flex-col gap-3">
          {messages.map((msg) => (
            <div key={msg.id} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
              {msg.role === "bot" && (
                <div className="w-6 h-6 rounded-full bg-primary flex items-center justify-center flex-shrink-0 mr-2 mt-0.5">
                  <svg viewBox="0 0 20 20" fill="currentColor" className="w-3 h-3 text-primary-foreground" aria-hidden="true">
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
                <svg viewBox="0 0 20 20" fill="currentColor" className="w-3 h-3 text-primary-foreground" aria-hidden="true">
                  <path d="M3.505 2.365A41.369 41.369 0 0 1 9 2c1.863 0 3.697.124 5.495.365 1.247.167 2.318 1.174 2.429 2.428A44.198 44.198 0 0 1 17 8c0 1.077-.06 2.137-.174 3.177-.11 1.014-.98 1.848-2.012 1.978L10 14l-2.404 2.403A1 1 0 0 1 6 15.699V14H5.63c-1.241 0-2.27-.87-2.44-2.1A44.12 44.12 0 0 1 3 8c0-.965.057-1.916.168-2.852a2.52 2.52 0 0 1 .337-.783z" />
                </svg>
              </div>
              <div className="bg-muted rounded-2xl rounded-tl-sm px-4 py-3 flex gap-1 items-center">
                {[0, 1, 2].map((i) => (
                  <div
                    key={i}
                    className="w-1.5 h-1.5 rounded-full bg-muted-foreground/50"
                    style={{ animation: `pulse 1.2s ease-in-out ${i * 0.2}s infinite` }}
                  />
                ))}
              </div>
            </div>
          )}

          {/* Suggested questions */}
          {showSuggestions && !typing && (
            <div className="flex flex-col gap-2 mt-1">
              <p className="text-xs text-muted-foreground px-1">자주 묻는 질문</p>
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
            onSubmit={(e) => { e.preventDefault(); sendMessage(input) }}
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
              <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4" aria-hidden="true">
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
  )
}
