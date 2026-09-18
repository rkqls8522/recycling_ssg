import { useEffect, useState } from "react"
import BackButton from "../../components/common/BackButton"

interface Props {
  onBack: () => void
}

const AGENT_STEPS = [
  "분리배출 규정 문서를 불러오는 중...",
  "지역별 예외 조항을 검토하는 중...",
  "유사 사례 데이터베이스를 탐색하는 중...",
  "복합 소재 여부를 교차 확인하는 중...",
  "최신 지침 개정 이력을 확인하는 중...",
  "맞춤 배출 안내문을 작성하는 중...",
]

interface Tip {
  emoji: string
  title: string
  body: string
  tag: string
}

const DISPOSAL_TIPS: Tip[] = [
  {
    emoji: "🥄",
    title: "일회용 플라스틱 숟가락·포크",
    body: "플라스틱이라도 음식물이 묻기 쉽고 재활용 선별이 어려워 일반쓰레기(종량제 봉투)로 배출해야 합니다.",
    tag: "플라스틱류 ✗",
  },
  {
    emoji: "🧾",
    title: "영수증(감열지)",
    body: "ATM·마트 영수증은 열에 반응하는 감열지로 만들어져 일반 종이와 달리 재활용이 불가합니다. 종량제 봉투에 넣으세요.",
    tag: "종이류 ✗",
  },
  {
    emoji: "🍕",
    title: "기름 묻은 피자 상자",
    body: "기름이 배지 않은 깨끗한 부분만 잘라서 종이류 배출. 기름 묻은 부분은 일반쓰레기입니다.",
    tag: "부분만 종이류",
  },
  {
    emoji: "🧴",
    title: "샴푸·세제 펌프 용기",
    body: "내용물을 비우고 헹군 후 플라스틱류 배출 가능. 하지만 속에 스프링이 든 펌프 헤드는 분리해서 고철류로 따로 버리세요.",
    tag: "분리 배출 필요",
  },
  {
    emoji: "🪟",
    title: "깨진 유리",
    body: "깨진 유리는 선별 작업자를 다치게 할 수 있어 유리류 수거함에 넣으면 안 됩니다. 신문지나 상자로 감싸 종량제 봉투에 배출하세요.",
    tag: "유리류 ✗",
  },
  {
    emoji: "🥛",
    title: "종이팩 vs 일반 종이",
    body: "우유팩·두유팩 등 종이팩은 코팅이 되어 있어 일반 폐지와 다릅니다. 전용 수거함에 따로 배출해야 재활용률이 올라갑니다.",
    tag: "종이팩 전용함",
  },
  {
    emoji: "🎈",
    title: "스티로폼의 테이프·스티커",
    body: "테이프나 스티커가 붙은 스티로폼은 재활용 불가. 이물질을 모두 제거한 깨끗한 상태에서만 스티로폼류로 배출할 수 있습니다.",
    tag: "이물질 제거 필수",
  },
  {
    emoji: "🔋",
    title: "건전지·배터리",
    body: "일반쓰레기나 재활용 수거함 모두 ✗. 마트·편의점의 폐건전지 전용 수거함에 넣어야 합니다. 폭발·화재 위험이 있습니다.",
    tag: "전용 수거함",
  },
  {
    emoji: "🍶",
    title: "소주·맥주병 보증금",
    body: "소주·맥주병은 빈용기 보증금 대상입니다. 그냥 버리지 말고 편의점·마트에 반납하면 병당 100~130원을 돌려받을 수 있습니다.",
    tag: "환불 가능",
  },
  {
    emoji: "🌡️",
    title: "체온계 (수은)",
    body: "수은 체온계는 절대 일반쓰레기로 버리면 안 됩니다. 주민센터나 약국의 폐의약품·유해폐기물 수거함을 이용하세요.",
    tag: "유해폐기물",
  },
  {
    emoji: "👟",
    title: "낡은 운동화",
    body: "고무·합성소재가 섞인 신발은 재활용이 어렵습니다. 대형 폐기물 신고 없이 종량제 봉투에 담아 배출할 수 있습니다.",
    tag: "일반쓰레기",
  },
  {
    emoji: "🫙",
    title: "뚜껑과 용기는 따로",
    body: "유리병의 금속 뚜껑은 금속류, 플라스틱 뚜껑은 플라스틱류로 분리 배출해야 합니다. 함께 넣으면 선별 효율이 떨어집니다.",
    tag: "소재별 분리",
  },
]

export default function AgentThinkingView({ onBack }: Props) {
  const [elapsed, setElapsed] = useState(0)
  const [visibleSteps, setVisibleSteps] = useState<number[]>([0])
  const [tipIndex, setTipIndex] = useState(() => Math.floor(Math.random() * DISPOSAL_TIPS.length))
  const [sliding, setSliding] = useState(false)
  const [blinkOn, setBlinkOn] = useState(true)
  const [dotCount, setDotCount] = useState(1)

  // Elapsed timer
  useEffect(() => {
    const id = setInterval(() => setElapsed((s) => s + 1), 1000)
    return () => clearInterval(id)
  }, [])

  // Reveal agent steps one by one
  useEffect(() => {
    const id = setInterval(() => {
      setVisibleSteps((prev) => {
        const next = (prev[prev.length - 1] + 1) % AGENT_STEPS.length
        return prev.length >= AGENT_STEPS.length ? prev : [...prev, next]
      })
    }, 2200)
    return () => clearInterval(id)
  }, [])

  // Auto-advance tip carousel every 3s
  useEffect(() => {
    const id = setInterval(() => {
      setSliding(true)
      setTimeout(() => {
        setTipIndex((i) => (i + 1) % DISPOSAL_TIPS.length)
        setSliding(false)
      }, 280)
    }, 3000)
    return () => clearInterval(id)
  }, [])

  // Blink eyes on character
  useEffect(() => {
    const id = setInterval(() => {
      setBlinkOn(false)
      setTimeout(() => setBlinkOn(true), 140)
    }, 3000)
    return () => clearInterval(id)
  }, [])

  // Ellipsis
  useEffect(() => {
    const id = setInterval(() => setDotCount((c) => (c % 3) + 1), 500)
    return () => clearInterval(id)
  }, [])

  const dots = ".".repeat(dotCount)
  const mins = Math.floor(elapsed / 60)
  const secs = elapsed % 60
  const timeLabel = mins > 0 ? `${mins}분 ${secs}초` : `${secs}초`
  const tip = DISPOSAL_TIPS[tipIndex]

  return (
    <div className="flex flex-col h-full bg-background animate-fade-in-up">
      {/* Header */}
      <div className="bg-primary text-primary-foreground px-5 pt-12 pb-4">
        <div className="flex items-center justify-between mb-4">
          <BackButton onClick={onBack} ariaLabel="취소" />
          <div className="text-center">
            <p className="text-xs font-semibold opacity-70 uppercase tracking-widest">심층 분석</p>
          </div>
          {/* Elapsed time */}
          <div className="px-2.5 py-1 bg-primary-foreground/10 rounded-full">
            <span className="text-xs font-mono font-semibold">{timeLabel}</span>
          </div>
        </div>
      </div>

      {/* Main */}
      <div className="flex-1 overflow-y-auto no-scrollbar px-5 pt-6 pb-6 flex flex-col gap-5">

        {/* Character + status */}
        <div className="flex flex-col items-center gap-3">
          {/* Thinking character */}
          <div className="relative">
            {/* Thought bubbles */}
            <div className="absolute -top-1 -right-2 flex flex-col items-center gap-1">
              <div className="w-2 h-2 rounded-full bg-primary/20 animate-pulse" />
              <div className="w-2.5 h-2.5 rounded-full bg-primary/30 animate-pulse" style={{ animationDelay: "0.2s" }} />
              <div className="w-8 h-6 rounded-xl bg-primary/15 flex items-center justify-center animate-pulse" style={{ animationDelay: "0.4s" }}>
                <span className="text-[10px]">🤔</span>
              </div>
            </div>

            <svg width="72" height="72" viewBox="0 0 64 64" fill="none" aria-hidden="true">
              <ellipse cx="32" cy="61" rx="14" ry="3" fill="black" fillOpacity="0.07" />
              <circle cx="32" cy="30" r="26" fill="#1b5c35" />
              <ellipse cx="24" cy="20" rx="7" ry="5" fill="white" fillOpacity="0.15" transform="rotate(-20 24 20)" />
              {/* Eyes — blink */}
              {blinkOn ? (
                <>
                  <circle cx="24" cy="27" r="4" fill="white" />
                  <circle cx="40" cy="27" r="4" fill="white" />
                  {/* Pupils looking up-right (thinking) */}
                  <circle cx="25" cy="26" r="2" fill="#0f3d22" />
                  <circle cx="41" cy="26" r="2" fill="#0f3d22" />
                  <circle cx="25.8" cy="25.2" r="0.8" fill="white" />
                  <circle cx="41.8" cy="25.2" r="0.8" fill="white" />
                </>
              ) : (
                <>
                  <rect x="20" y="26" width="8" height="2" rx="1" fill="white" />
                  <rect x="36" y="26" width="8" height="2" rx="1" fill="white" />
                </>
              )}
              {/* Thinking mouth (slightly open) */}
              <path d="M26 37 Q32 40 38 37" stroke="white" strokeWidth="2" strokeLinecap="round" fill="none" />
              {/* Swirl on forehead */}
              <path d="M28 16 Q32 13 36 16 Q34 19 32 17 Q30 15 32 13" stroke="white" strokeWidth="1.2" strokeLinecap="round" fill="none" opacity="0.5" />
              <line x1="32" y1="4" x2="32" y2="10" stroke="#1b5c35" strokeWidth="2.5" strokeLinecap="round" />
              <circle cx="32" cy="3" r="3" fill="#4ade80" className="animate-pulse" />
            </svg>
          </div>

          <div className="text-center">
            <p className="text-base font-bold text-foreground">AI 에이전트가 분석 중{dots}</p>
            <p className="text-xs text-muted-foreground mt-1">복잡한 케이스라 조금 더 걸리고 있어요</p>
          </div>
        </div>

        {/* Agent reasoning steps */}
        <div className="bg-card rounded-2xl border border-border overflow-hidden">
          <div className="px-4 py-3 border-b border-border flex items-center gap-2">
            <div className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">에이전트 처리 현황</p>
          </div>
          <div className="flex flex-col">
            {AGENT_STEPS.map((step, i) => {
              const isVisible = visibleSteps.includes(i)
              const isActive = isVisible && i === visibleSteps[visibleSteps.length - 1]
              const isDone = isVisible && !isActive
              if (!isVisible) return null
              return (
                <div
                  key={i}
                  className={`flex items-center gap-3 px-4 py-3 animate-step-appear ${
                    i < AGENT_STEPS.length - 1 && visibleSteps.includes(i + 1) ? "border-b border-border" : ""
                  } ${isActive ? "bg-primary/5" : ""}`}
                >
                  <div className={`w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 ${
                    isDone ? "bg-primary text-primary-foreground" : "bg-primary/10 border-2 border-primary"
                  }`}>
                    {isDone ? (
                      <svg viewBox="0 0 12 12" fill="none" className="w-2.5 h-2.5">
                        <path d="M2 6l3 3 5-5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                    ) : (
                      <svg className="animate-spin h-2.5 w-2.5 text-primary" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                      </svg>
                    )}
                  </div>
                  <p className={`text-xs font-medium flex-1 ${isDone ? "text-primary" : "text-foreground"}`}>
                    {step}
                  </p>
                </div>
              )
            })}
          </div>
        </div>

        {/* Tip carousel */}
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-2">
            <div className="h-px flex-1 bg-border" />
            <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest">
              분리배출 팁
            </span>
            <div className="h-px flex-1 bg-border" />
          </div>
          <div className="bg-card border border-border rounded-2xl overflow-hidden">
            <div
              className="p-5"
              style={{
                opacity: sliding ? 0 : 1,
                transform: sliding ? "translateX(-24px)" : "translateX(0)",
                transition: "opacity 0.28s ease, transform 0.28s ease",
              }}
            >
              <div className="flex items-start gap-3.5">
                <span className="text-3xl leading-none flex-shrink-0 mt-0.5" aria-hidden="true">
                  {tip.emoji}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <p className="text-sm font-bold text-foreground leading-snug">{tip.title}</p>
                    <span className="text-[10px] font-mono font-semibold bg-secondary text-secondary-foreground px-2 py-0.5 rounded-full flex-shrink-0 whitespace-nowrap">
                      {tip.tag}
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground leading-relaxed">{tip.body}</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Cancel hint */}
        <p className="text-xs text-muted-foreground text-center">
          너무 오래 걸리면{" "}
          <button onClick={onBack} className="text-primary font-semibold underline">
            취소하고 다시 촬영
          </button>
          해 주세요
        </p>
      </div>
    </div>
  )
}
