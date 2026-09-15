import { useEffect, useRef, useState } from "react"
import type { ClassificationResult } from "../../types"

interface Props {
  result: ClassificationResult
  imageUrl: string
  onReanalyzed: (newResult: ClassificationResult) => void
  onRetake: () => void
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
  { emoji: "🥄", title: "일회용 플라스틱 숟가락·포크", body: "플라스틱이라도 음식물이 묻기 쉽고 재활용 선별이 어려워 일반쓰레기(종량제 봉투)로 배출해야 합니다.", tag: "플라스틱류 ✗" },
  { emoji: "🧾", title: "영수증(감열지)", body: "ATM·마트 영수증은 열에 반응하는 감열지로 만들어져 일반 종이와 달리 재활용이 불가합니다. 종량제 봉투에 넣으세요.", tag: "종이류 ✗" },
  { emoji: "🍕", title: "기름 묻은 피자 상자", body: "기름이 배지 않은 깨끗한 부분만 잘라서 종이류 배출. 기름 묻은 부분은 일반쓰레기입니다.", tag: "부분만 종이류" },
  { emoji: "🧴", title: "샴푸·세제 펌프 용기", body: "내용물을 비우고 헹군 후 플라스틱류 배출 가능. 하지만 속에 스프링이 든 펌프 헤드는 분리해서 고철류로 따로 버리세요.", tag: "분리 배출 필요" },
  { emoji: "🪟", title: "깨진 유리", body: "깨진 유리는 선별 작업자를 다치게 할 수 있어 유리류 수거함에 넣으면 안 됩니다. 신문지나 상자로 감싸 종량제 봉투에 배출하세요.", tag: "유리류 ✗" },
  { emoji: "🥛", title: "종이팩 vs 일반 종이", body: "우유팩·두유팩 등 종이팩은 코팅이 되어 있어 일반 폐지와 다릅니다. 전용 수거함에 따로 배출해야 재활용률이 올라갑니다.", tag: "종이팩 전용함" },
  { emoji: "🎈", title: "스티로폼의 테이프·스티커", body: "테이프나 스티커가 붙은 스티로폼은 재활용 불가. 이물질을 모두 제거한 깨끗한 상태에서만 스티로폼류로 배출할 수 있습니다.", tag: "이물질 제거 필수" },
  { emoji: "🔋", title: "건전지·배터리", body: "일반쓰레기나 재활용 수거함 모두 ✗. 마트·편의점의 폐건전지 전용 수거함에 넣어야 합니다. 폭발·화재 위험이 있습니다.", tag: "전용 수거함" },
  { emoji: "🍶", title: "소주·맥주병 보증금", body: "소주·맥주병은 빈용기 보증금 대상입니다. 그냥 버리지 말고 편의점·마트에 반납하면 병당 100~130원을 돌려받을 수 있습니다.", tag: "환불 가능" },
  { emoji: "🌡️", title: "체온계 (수은)", body: "수은 체온계는 절대 일반쓰레기로 버리면 안 됩니다. 주민센터나 약국의 폐의약품·유해폐기물 수거함을 이용하세요.", tag: "유해폐기물" },
  { emoji: "👟", title: "낡은 운동화", body: "고무·합성소재가 섞인 신발은 재활용이 어렵습니다. 대형 폐기물 신고 없이 종량제 봉투에 담아 배출할 수 있습니다.", tag: "일반쓰레기" },
  { emoji: "🫙", title: "뚜껑과 용기는 따로", body: "유리병의 금속 뚜껑은 금속류, 플라스틱 뚜껑은 플라스틱류로 분리 배출해야 합니다. 함께 넣으면 선별 효율이 떨어집니다.", tag: "소재별 분리" },
]

export default function ResultUncertainView({ result, imageUrl, onReanalyzed, onRetake }: Props) {
  const { itemName, itemCategory, confidence } = result
  const [reanalyzing, setReanalyzing] = useState(false)
  const [visibleSteps, setVisibleSteps] = useState<number[]>([])
  const [tipIndex, setTipIndex] = useState(() => Math.floor(Math.random() * DISPOSAL_TIPS.length))
  const [sliding, setSliding] = useState(false)
  const [dotCount, setDotCount] = useState(1)
  const stepsIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Auto-reanalyze after 1 second
  useEffect(() => {
    const timer = setTimeout(() => setReanalyzing(true), 1000)
    return () => clearTimeout(timer)
  }, [])

  // Start revealing agent steps when reanalyzing begins
  useEffect(() => {
    if (!reanalyzing) return
    setVisibleSteps([0])
    stepsIntervalRef.current = setInterval(() => {
      setVisibleSteps((prev) => {
        if (prev.length >= AGENT_STEPS.length) return prev
        return [...prev, prev.length]
      })
    }, 2200)
    return () => clearInterval(stepsIntervalRef.current!)
  }, [reanalyzing])

  // Trigger actual reanalysis result after ~13s (all steps shown + buffer)
  useEffect(() => {
    if (!reanalyzing) return
    const timer = setTimeout(() => {
      clearInterval(stepsIntervalRef.current!)
      const roll = Math.random()
      const newConfidence = roll < 0.7
        ? 85 + Math.floor(Math.random() * 10)
        : 25 + Math.floor(Math.random() * 30)
      const newLevel = newConfidence >= 82 ? "high" as const : "low" as const
      onReanalyzed({
        ...result,
        confidence: newConfidence,
        confidenceLevel: newLevel,
        failureHint: newLevel === "low" ? "unclear" : undefined,
      })
    }, 13200)
    return () => clearTimeout(timer)
  }, [reanalyzing, result, onReanalyzed])

  // Tip carousel every 3s
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

  // Ellipsis
  useEffect(() => {
    const id = setInterval(() => setDotCount((c) => (c % 3) + 1), 500)
    return () => clearInterval(id)
  }, [])

  const dots = ".".repeat(dotCount)
  const tip = DISPOSAL_TIPS[tipIndex]

  return (
    <div className="flex flex-col h-full bg-background">
      {/* Header */}
      <div className="bg-amber-600 text-white px-5 pt-12 pb-4">
        <div className="flex items-center justify-between mb-4">
          <div className="w-9" />
          <div className="flex items-center gap-1.5">
            {["촬영", "분석", "결과"].map((label, i) => (
              <div key={i} className="flex items-center">
                <div className="flex flex-col items-center gap-0.5">
                  <div className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold ${
                    i < 2 ? "bg-white/20 text-white/60" : "bg-white text-amber-600 ring-2 ring-white/30"
                  }`}>
                    {i < 2 ? (
                      <svg viewBox="0 0 12 12" fill="none" className="w-2.5 h-2.5">
                        <path d="M10 3L5 8.5 2 5.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                    ) : reanalyzing ? (
                      <svg className="animate-spin w-2.5 h-2.5" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                      </svg>
                    ) : "?"}
                  </div>
                  <span className={`text-[9px] font-semibold ${i === 2 ? "text-white" : "text-white/50"}`}>{label}</span>
                </div>
                {i < 2 && <div className="w-8 h-px mx-1 mb-3 bg-white/30" />}
              </div>
            ))}
          </div>
          <div className="w-9" />
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 flex flex-col px-5 pt-6 pb-6 gap-5 overflow-y-auto no-scrollbar">

        {/* Status */}
        <div className="flex items-center gap-4 animate-fade-in-up">
          <div className="w-20 h-20 rounded-xl overflow-hidden border-2 border-border flex-shrink-0 shadow-lg">
            <img src={imageUrl} alt="분석 중인 사진" className="w-full h-full object-cover" />
          </div>
          <div className="flex-1">
            <span className="text-[10px] font-semibold text-amber-600 uppercase tracking-widest">
              {reanalyzing ? "에이전트 재분석 중" : "재확인 필요"}
            </span>
            <p className="text-sm font-bold text-foreground mt-0.5 leading-snug">
              {reanalyzing ? `AI 에이전트가 심층 분석 중${dots}` : "인식 결과가 명확하지 않아요"}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              {itemName} · {itemCategory} · {confidence}%
            </p>
          </div>
        </div>

        {/* Agent steps */}
        <div className="bg-card rounded-2xl border border-border overflow-hidden animate-fade-in-up" style={{ animationDelay: "0.1s" }}>
          <div className="px-4 py-3 border-b border-border flex items-center gap-2">
            <div className={`w-1.5 h-1.5 rounded-full ${reanalyzing ? "bg-amber-500 animate-pulse" : "bg-border"}`} />
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">에이전트 처리 현황</p>
          </div>
          <div className="flex flex-col">
            {reanalyzing ? AGENT_STEPS.map((step, i) => {
              const isVisible = visibleSteps.includes(i)
              const isActive = isVisible && i === visibleSteps[visibleSteps.length - 1]
              const isDone = isVisible && !isActive
              if (!isVisible) return null
              return (
                <div
                  key={i}
                  className={`flex items-center gap-3 px-4 py-3 animate-step-appear ${
                    i < AGENT_STEPS.length - 1 && visibleSteps.includes(i + 1) ? "border-b border-border" : ""
                  } ${isActive ? "bg-amber-50" : ""}`}
                >
                  <div className={`w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 ${
                    isDone ? "bg-amber-500 text-white" : "bg-amber-50 border-2 border-amber-500"
                  }`}>
                    {isDone ? (
                      <svg viewBox="0 0 12 12" fill="none" className="w-2.5 h-2.5">
                        <path d="M2 6l3 3 5-5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                    ) : (
                      <svg className="animate-spin h-2.5 w-2.5 text-amber-500" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                      </svg>
                    )}
                  </div>
                  <p className={`text-xs font-medium flex-1 ${isDone ? "text-amber-600" : "text-foreground"}`}>
                    {step}
                  </p>
                </div>
              )
            }) : (
              <div className="px-4 py-4 flex items-center gap-3">
                <div className="w-5 h-5 rounded-full bg-muted border-2 border-border flex-shrink-0" />
                <p className="text-xs text-muted-foreground/50">잠시 후 에이전트 분석이 시작됩니다</p>
              </div>
            )}
          </div>
        </div>

        {/* Tip carousel */}
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-2">
            <div className="h-px flex-1 bg-border" />
            <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest">분리배출 팁</span>
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
                <span className="text-3xl leading-none flex-shrink-0 mt-0.5" aria-hidden="true">{tip.emoji}</span>
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

      {/* Bottom CTA */}
      <div className="px-5 pb-8 pt-3">
        <button
          onClick={onRetake}
          className="w-full py-4 bg-amber-600 text-white rounded-2xl font-semibold text-base shadow-lg shadow-amber-500/20 active:scale-[0.98] transition-all flex items-center justify-center gap-2.5"
        >
          <svg viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5" aria-hidden="true">
            <path fillRule="evenodd" d="M15.312 11.424a5.5 5.5 0 0 1-9.201 2.466l-.312-.311h2.433a.75.75 0 0 0 0-1.5H5.498a.75.75 0 0 0-.75.75v3.498a.75.75 0 0 0 1.5 0v-1.590l.308.31a7 7 0 0 0 11.717-3.138.75.75 0 0 0-1.466-.313zm-7.498-4.697l-.312.31V4.537a.75.75 0 0 0-1.5 0v3.498c0 .414.336.75.75.75h3.498a.75.75 0 0 0 0-1.5H7.617l.31-.311a7 7 0 0 0 11.524 3.947.75.75 0 0 0-.998-1.122 5.5 5.5 0 0 1-9.639-2.845z" clipRule="evenodd" />
          </svg>
          다시 촬영하기
        </button>
      </div>
    </div>
  )
}
