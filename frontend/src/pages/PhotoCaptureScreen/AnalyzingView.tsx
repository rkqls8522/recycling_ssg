import { useEffect, useState } from "react"
import { CLASSIFY_STEPS } from "../../api/api"
import FlowIndicator from "../../components/common/FlowIndicator"

interface Props {
  previewUrl: string
  completedSteps: number[]
  currentStep: number
}

const ANALYZING_MESSAGES = [
  "이미지를 준비하고 있습니다...",
  "폐기물 영역을 찾고 있습니다...",
  "품목을 분류하고 있습니다...",
  "지역 배출 지침을 검색하고 있습니다...",
  "맞춤 안내문을 만들고 있습니다...",
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

export default function AnalyzingView({ previewUrl, completedSteps, currentStep }: Props) {
  const [dotCount, setDotCount] = useState(1)
  const [tipIndex, setTipIndex] = useState(() => Math.floor(Math.random() * DISPOSAL_TIPS.length))
  const [sliding, setSliding] = useState(false)

  // Animated ellipsis
  useEffect(() => {
    const id = setInterval(() => setDotCount((c) => (c % 3) + 1), 500)
    return () => clearInterval(id)
  }, [])

  // Auto-advance every 3 seconds
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

  const dots = ".".repeat(dotCount)
  const message = ANALYZING_MESSAGES[Math.min(currentStep, ANALYZING_MESSAGES.length - 1)]
  const tip = DISPOSAL_TIPS[tipIndex]

  return (
    <div className="flex flex-col h-full bg-background animate-fade-in-up">
      {/* Header */}
      <div className="bg-primary text-primary-foreground px-5 pt-12 pb-4">
        <div className="flex items-center justify-between mb-4">
          <div className="w-9" />
          <FlowIndicator
            currentStep={1}
            currentIcon={
              <svg className="animate-spin w-2.5 h-2.5" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
            }
          />
          <div className="w-9" />
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 flex flex-col px-5 pt-6 pb-6 overflow-y-auto no-scrollbar gap-5">

        {/* Image + status */}
        <div className="flex items-center gap-4">
          <div className="relative w-20 h-20 rounded-xl overflow-hidden shadow-lg border-2 border-border flex-shrink-0">
            <img src={previewUrl} alt="분석 중인 사진" className="w-full h-full object-cover" />
            <div
              className="absolute left-0 right-0 h-0.5 bg-primary/70 animate-scan-line pointer-events-none"
              style={{ top: 0, boxShadow: "0 0 8px 2px rgba(27,92,53,0.4)" }}
            />
            <div className="absolute inset-0 bg-primary/5 pointer-events-none" />
          </div>
          <div className="flex-1">
            <p className="text-sm font-bold text-foreground leading-snug">
              AI가 분석하고 있습니다{dots}
            </p>
            <p className="text-xs text-muted-foreground mt-1 leading-relaxed">
              {message}
            </p>
          </div>
        </div>

        {/* Pipeline steps — compact */}
        <div className="w-full bg-card rounded-2xl border border-border overflow-hidden">
          {CLASSIFY_STEPS.map((step, i) => {
            const done = completedSteps.includes(i)
            const active = currentStep === i

            return (
              <div
                key={i}
                className={`flex items-center gap-3 px-4 py-3 transition-colors ${
                  i < CLASSIFY_STEPS.length - 1 ? "border-b border-border" : ""
                } ${done ? "bg-secondary/40" : active ? "bg-primary/5" : ""}`}
              >
                <div className={`w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 transition-all ${
                  done
                    ? "bg-primary text-primary-foreground"
                    : active
                    ? "bg-primary/10 border-2 border-primary"
                    : "bg-muted border-2 border-border"
                }`}>
                  {done ? (
                    <svg viewBox="0 0 12 12" fill="none" className="w-2.5 h-2.5" aria-hidden="true">
                      <path d="M2 6l3 3 5-5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  ) : active ? (
                    <svg className="animate-spin h-2.5 w-2.5 text-primary" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                  ) : null}
                </div>
                <p className={`text-xs font-medium flex-1 transition-colors ${
                  done ? "text-primary" : active ? "text-foreground" : "text-muted-foreground/40"
                }`}>
                  {step.label}
                </p>
                {done && (
                  <span className="text-[10px] font-mono text-primary/50 bg-primary/8 px-1.5 py-0.5 rounded-full">
                    완료
                  </span>
                )}
                {active && (
                  <span className="text-[10px] font-mono text-primary bg-primary/10 px-1.5 py-0.5 rounded-full">
                    진행 중{dots}
                  </span>
                )}
              </div>
            )
          })}
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
            {/* Slide area */}
            <div className="overflow-hidden">
              <div
                className="p-5 transition-all duration-280"
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
        </div>

      </div>
    </div>
  )
}
