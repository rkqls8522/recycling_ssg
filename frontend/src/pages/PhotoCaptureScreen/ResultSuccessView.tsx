import type { ClassificationResult } from "../../types"
import FlowIndicator from "../../components/common/FlowIndicator"

interface Props {
  result: ClassificationResult
  imageUrl: string
  onViewGuidelines: () => void
  onRetake: () => void
}

const CATEGORY_COLORS: Record<string, string> = {
  "플라스틱류": "bg-blue-100 text-blue-800 border-blue-200",
  "유리류": "bg-cyan-100 text-cyan-800 border-cyan-200",
  "금속류": "bg-orange-100 text-orange-800 border-orange-200",
  "종이류 (종이팩)": "bg-amber-100 text-amber-800 border-amber-200",
  "스티로폼류": "bg-purple-100 text-purple-800 border-purple-200",
}

function getCategoryColor(category: string): string {
  return CATEGORY_COLORS[category] ?? "bg-green-100 text-green-800 border-green-200"
}

export default function ResultSuccessView({ result, imageUrl, onViewGuidelines, onRetake }: Props) {
  const { itemName, itemCategory, confidence } = result

  return (
    <div className="flex flex-col h-full bg-background">
      {/* Header */}
      <div className="bg-primary text-primary-foreground px-5 pt-12 pb-4">
        <div className="flex items-center justify-between mb-4">
          <div className="w-9" />
          <FlowIndicator currentStep={2} tone="primary" currentIcon="✓" />
          <div className="w-9" />
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 flex flex-col items-center px-5 pt-8 pb-6 gap-5 overflow-y-auto no-scrollbar">

        {/* Success animation */}
        <div className="flex flex-col items-center gap-4 animate-fade-in-up">
          <div className="relative">
            {/* Pulse ring */}
            <div className="absolute inset-0 rounded-full bg-primary/20 animate-pulse-ring" />
            {/* Icon circle */}
            <div className="w-20 h-20 rounded-full bg-primary flex items-center justify-center shadow-xl shadow-primary/30 animate-check-pop">
              <svg viewBox="0 0 24 24" fill="none" className="w-10 h-10 text-primary-foreground" aria-hidden="true">
                <path d="M5 13l4 4L19 7" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
          </div>

          <div className="text-center">
            <p className="text-xs font-semibold text-primary uppercase tracking-widest">인식 성공</p>
            <h2 className="text-3xl font-bold text-foreground mt-1 tracking-tight">{itemName}</h2>
          </div>
        </div>

        {/* Result card */}
        <div className="w-full bg-card rounded-2xl border border-border p-5 animate-fade-in-up" style={{ animationDelay: "0.1s" }}>
          <div className="flex items-center justify-between gap-4">
            {/* Thumbnail */}
            <div className="w-16 h-16 rounded-xl overflow-hidden border-2 border-border flex-shrink-0">
              <img src={imageUrl} alt="인식된 폐기물 사진" className="w-full h-full object-cover" />
            </div>
            {/* Info */}
            <div className="flex-1">
              <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-mono font-semibold border ${getCategoryColor(itemCategory)}`}>
                {itemCategory}
              </span>
            </div>
            {/* Confidence */}
            <div className="text-right flex-shrink-0">
              <p className="text-xs text-muted-foreground">정확도</p>
              <p className="text-2xl font-bold font-mono text-primary">{confidence}%</p>
            </div>
          </div>

          {/* Confidence bar */}
          <div className="mt-4">
            <div className="w-full h-1.5 bg-muted rounded-full overflow-hidden">
              <div
                className="h-full bg-primary rounded-full transition-all duration-1000"
                style={{ width: `${confidence}%` }}
              />
            </div>
            <p className="text-xs text-muted-foreground mt-1.5">
              높은 신뢰도로 인식되었습니다 — 즉시 배출 안내를 제공합니다
            </p>
          </div>
        </div>

        {/* Region indicator */}
        <div className="w-full flex items-center gap-2.5 px-4 py-3 bg-secondary rounded-xl border border-secondary-foreground/10 animate-fade-in-up" style={{ animationDelay: "0.15s" }}>
          <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 text-secondary-foreground flex-shrink-0" aria-hidden="true">
            <path fillRule="evenodd" d="M9.69 18.933l.003.001C9.89 19.02 10 19 10 19s.11.02.308-.066l.002-.001.006-.003.018-.008a5.741 5.741 0 0 0 .281-.14c.186-.096.446-.24.757-.433.62-.384 1.445-.966 2.274-1.765C15.302 14.988 17 12.493 17 9A7 7 0 1 0 3 9c0 3.492 1.698 5.988 3.355 7.584a13.731 13.731 0 0 0 2.273 1.765 11.842 11.842 0 0 0 .976.544l.062.029.018.008.006.003zM10 11.25a2.25 2.25 0 1 0 0-4.5 2.25 2.25 0 0 0 0 4.5z" clipRule="evenodd" />
          </svg>
          <span className="text-sm font-semibold text-secondary-foreground">{result.regionName}</span>
          <span className="text-xs text-secondary-foreground/60 ml-auto">기준 적용됨</span>
        </div>
      </div>

      {/* Bottom CTAs */}
      <div className="px-5 pb-8 pt-3 flex flex-col gap-2.5 animate-fade-in-up" style={{ animationDelay: "0.2s" }}>
        <button
          onClick={onViewGuidelines}
          className="w-full py-4 bg-primary text-primary-foreground rounded-2xl font-semibold text-base shadow-lg shadow-primary/20 active:scale-[0.98] transition-all flex items-center justify-center gap-2.5"
        >
          배출 방법 확인하기
          <svg viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5" aria-hidden="true">
            <path fillRule="evenodd" d="M3 10a.75.75 0 0 1 .75-.75h10.638L10.23 5.29a.75.75 0 1 1 1.04-1.08l5.5 5.25a.75.75 0 0 1 0 1.08l-5.5 5.25a.75.75 0 1 1-1.04-1.08l4.158-3.96H3.75A.75.75 0 0 1 3 10z" clipRule="evenodd" />
          </svg>
        </button>
        <button
          onClick={onRetake}
          className="w-full py-3 text-sm font-medium text-muted-foreground flex items-center justify-center gap-1.5 active:opacity-60 transition-opacity"
        >
          다른 품목 분석하기
        </button>
      </div>
    </div>
  )
}
