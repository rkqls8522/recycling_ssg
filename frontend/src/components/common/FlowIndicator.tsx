import type { ReactNode } from "react"

type FlowTone = "primary" | "destructive" | "amber"

interface FlowIndicatorProps {
  /** 0 = 촬영, 1 = 분석, 2 = 결과 */
  currentStep: 0 | 1 | 2
  /** Header color theme this indicator sits on top of. Defaults to "primary". */
  tone?: FlowTone
  /** Custom icon/content for the current-step circle (spinner, ✓, ✕, ?, ...). Defaults to the step number. */
  currentIcon?: ReactNode
  labels?: string[]
}

const TONE_STYLES: Record<
  FlowTone,
  {
    done: string
    current: string
    currentRing: string
    upcoming: string
    lineDone: string
    lineUpcoming: string
    labelActive: string
    labelInactive: string
  }
> = {
  primary: {
    done: "bg-primary-foreground/30 text-primary-foreground/60",
    current: "bg-primary-foreground text-primary",
    currentRing: "ring-primary-foreground/30",
    upcoming: "bg-primary-foreground/20 text-primary-foreground/50",
    lineDone: "bg-primary-foreground/40",
    lineUpcoming: "bg-primary-foreground/20",
    labelActive: "text-primary-foreground",
    labelInactive: "text-primary-foreground/50",
  },
  destructive: {
    done: "bg-white/20 text-white/60",
    current: "bg-white text-destructive",
    currentRing: "ring-white/30",
    upcoming: "bg-white/20 text-white/60",
    lineDone: "bg-white/30",
    lineUpcoming: "bg-white/30",
    labelActive: "text-white",
    labelInactive: "text-white/50",
  },
  amber: {
    done: "bg-white/20 text-white/60",
    current: "bg-white text-amber-600",
    currentRing: "ring-white/30",
    upcoming: "bg-white/20 text-white/60",
    lineDone: "bg-white/30",
    lineUpcoming: "bg-white/30",
    labelActive: "text-white",
    labelInactive: "text-white/50",
  },
}

function CheckIcon() {
  return (
    <svg viewBox="0 0 12 12" fill="none" className="w-2.5 h-2.5">
      <path d="M10 3L5 8.5 2 5.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

// 촬영 → 분석 → 결과 3단계 진행 표시. PhotoCaptureScreen의 각 상태 뷰
// (CaptureView, AnalyzingView, ResultFailView, ResultUncertainView, ResultSuccessView)
// 에서 공유하는 컴포넌트.
export default function FlowIndicator({
  currentStep,
  tone = "primary",
  currentIcon,
  labels = ["촬영", "분석", "결과"],
}: FlowIndicatorProps) {
  const s = TONE_STYLES[tone]

  return (
    <div className="flex items-center gap-1.5">
      {labels.map((label, i) => (
        <div key={i} className="flex items-center">
          <div className="flex flex-col items-center gap-0.5">
            <div
              className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold transition-all ${
                i < currentStep ? s.done : i === currentStep ? `${s.current} ring-2 ${s.currentRing}` : s.upcoming
              }`}
            >
              {i < currentStep ? <CheckIcon /> : i === currentStep ? currentIcon ?? i + 1 : i + 1}
            </div>
            <span
              className={`text-[9px] font-semibold transition-colors ${
                i === currentStep ? s.labelActive : s.labelInactive
              }`}
            >
              {label}
            </span>
          </div>
          {i < labels.length - 1 && (
            <div
              className={`w-8 h-px mx-1 mb-3 transition-colors ${i < currentStep ? s.lineDone : s.lineUpcoming}`}
            />
          )}
        </div>
      ))}
    </div>
  )
}
