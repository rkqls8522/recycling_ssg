import type { FailureHint } from "../../types"
import FlowIndicator from "../../components/common/FlowIndicator"

interface Props {
  failureHint?: FailureHint
  imageUrl: string
  onRetake: () => void
  onGallery: () => void
}

interface HintConfig {
  icon: string
  title: string
  description: string
  tips: string[]
}

const HINT_CONFIGS: Record<FailureHint, HintConfig> = {
  blurry: {
    icon: "🌀",
    title: "사진이 흐릿해요",
    description: "카메라가 흔들리거나 초점이 맞지 않은 것 같습니다.",
    tips: [
      "카메라를 물체 가까이 대고 고정한 뒤 촬영하세요",
      "스마트폰을 두 손으로 잡아 흔들림을 줄이세요",
      "화면을 탭해 초점을 맞춘 뒤 촬영하세요",
    ],
  },
  dark: {
    icon: "🌑",
    title: "조명이 너무 어두워요",
    description: "사진이 충분히 밝지 않아 물체를 인식하기 어렵습니다.",
    tips: [
      "밝은 곳으로 이동하거나 조명 아래에서 촬영하세요",
      "창문 근처 자연광 아래에서 찍으면 가장 좋습니다",
      "플래시를 켜서 촬영해 보세요",
    ],
  },
  multiple_objects: {
    icon: "🔀",
    title: "여러 물체가 섞여있어요",
    description: "화면에 여러 폐기물이 동시에 보여 특정하기 어렵습니다.",
    tips: [
      "분류할 품목 하나만 화면에 담아 촬영하세요",
      "배경을 깔끔하게 정리한 뒤 찍어 주세요",
      "물체를 손에 들고 촬영하면 더 잘 인식됩니다",
    ],
  },
  unclear: {
    icon: "🔍",
    title: "물체가 잘 안 보여요",
    description: "물체가 가려져 있거나 너무 작게 찍혀 인식이 어렵습니다.",
    tips: [
      "물체가 화면 중앙에, 화면의 50% 이상을 차지하도록 촬영하세요",
      "물체를 가리는 것이 없는지 확인하세요",
      "물체를 카메라 가까이 대고 촬영해 보세요",
    ],
  },
  unknown: {
    icon: "⚠️",
    title: "인식에 실패했습니다",
    description: "예상치 못한 오류로 품목을 인식하지 못했습니다.",
    tips: [
      "밝고 선명하게 물체가 잘 보이도록 다시 촬영해 보세요",
      "지원되는 폐기물 종류인지 확인해 보세요",
      "네트워크 연결을 확인하고 다시 시도해 보세요",
    ],
  },
}

export default function ResultFailView({ failureHint = "unknown", imageUrl, onRetake, onGallery }: Props) {
  const config = HINT_CONFIGS[failureHint]

  return (
    <div className="flex flex-col h-full bg-background">
      {/* Header */}
      <div className="bg-destructive/90 text-white px-5 pt-12 pb-4">
        <div className="flex items-center justify-between mb-4">
          <div className="w-9" />
          <FlowIndicator currentStep={2} tone="destructive" currentIcon="✕" />
          <div className="w-9" />
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 flex flex-col items-center px-5 pt-8 pb-6 gap-5 overflow-y-auto no-scrollbar">

        {/* Fail icon */}
        <div className="flex flex-col items-center gap-4 animate-fade-in-up">
          <div className="relative">
            <div className="w-20 h-20 rounded-full bg-red-100 flex items-center justify-center shadow-lg animate-x-pop">
              <svg viewBox="0 0 24 24" fill="none" className="w-10 h-10 text-destructive" aria-hidden="true">
                <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
              </svg>
            </div>
          </div>

          <div className="text-center">
            <p className="text-xs font-semibold text-destructive uppercase tracking-widest">인식 실패</p>
            <h2 className="text-2xl font-bold text-foreground mt-1">다시 촬영해 주세요</h2>
          </div>
        </div>

        {/* Failure reason card */}
        <div className="w-full bg-red-50 rounded-2xl border border-red-200 p-5 animate-fade-in-up" style={{ animationDelay: "0.1s" }}>
          <div className="flex items-start gap-3.5">
            {/* Blurred thumbnail */}
            <div className="w-14 h-14 rounded-xl overflow-hidden border-2 border-red-200 flex-shrink-0 relative">
              <img
                src={imageUrl}
                alt="인식 실패한 사진"
                className="w-full h-full object-cover"
                style={{ filter: "blur(1.5px) brightness(0.85)" }}
              />
              <div className="absolute inset-0 bg-red-500/20" />
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1.5">
                <span className="text-xl" aria-hidden="true">{config.icon}</span>
                <p className="text-sm font-bold text-red-900">{config.title}</p>
              </div>
              <p className="text-xs text-red-800/80 leading-relaxed">{config.description}</p>
            </div>
          </div>
        </div>

        {/* Tips */}
        <div className="w-full bg-card rounded-2xl border border-border p-5 animate-fade-in-up" style={{ animationDelay: "0.15s" }}>
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3.5">
            이렇게 해보세요
          </p>
          <div className="flex flex-col gap-3">
            {config.tips.map((tip, i) => (
              <div key={i} className="flex items-start gap-3">
                <div className="w-5 h-5 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <span className="text-[10px] font-bold font-mono text-primary">{i + 1}</span>
                </div>
                <p className="text-sm text-foreground leading-relaxed">{tip}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Supported items note */}
        <div className="w-full px-4 py-3 bg-muted rounded-xl animate-fade-in-up" style={{ animationDelay: "0.2s" }}>
          <p className="text-xs text-muted-foreground leading-relaxed">
            <span className="font-semibold">지원 품목:</span> 투명 페트병 · 유리병 · 알루미늄 캔 · 종이팩 · 스티로폼 · 플라스틱 용기
            {/* TODO: 인식 모델 교체 후 지원 품목 범위 확대 */}
          </p>
        </div>
      </div>

      {/* Bottom CTAs */}
      <div className="px-5 pb-8 pt-3 flex flex-col gap-2.5 animate-fade-in-up" style={{ animationDelay: "0.2s" }}>
        <button
          onClick={onRetake}
          className="w-full py-4 bg-primary text-primary-foreground rounded-2xl font-semibold text-base shadow-lg shadow-primary/20 active:scale-[0.98] transition-all flex items-center justify-center gap-2.5"
        >
          <svg viewBox="0 0 24 24" fill="none" className="w-5 h-5" aria-hidden="true">
            <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
            <circle cx="12" cy="13" r="4" stroke="currentColor" strokeWidth="1.5" />
          </svg>
          다시 촬영하기
        </button>
        <button
          onClick={onGallery}
          className="w-full py-3.5 border border-border rounded-2xl text-sm font-semibold text-foreground bg-card active:bg-muted transition-all flex items-center justify-center gap-2.5"
        >
          <svg viewBox="0 0 24 24" fill="none" className="w-5 h-5" aria-hidden="true">
            <rect x="3" y="3" width="18" height="18" rx="2" stroke="currentColor" strokeWidth="1.5" />
            <circle cx="8.5" cy="8.5" r="1.5" stroke="currentColor" strokeWidth="1.5" />
            <path d="M21 15l-5-5L5 21" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
          </svg>
          갤러리에서 다시 선택
        </button>
      </div>
    </div>
  )
}
