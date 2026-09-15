import { useState } from "react"
import type { ClassificationResult } from "../types"
import ChatDrawer from "./ChatDrawer"

interface Props {
  result: ClassificationResult
  imageUrl: string
  onBack: () => void
}

function BackIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5" aria-hidden="true">
      <path fillRule="evenodd" d="M17 10a.75.75 0 0 1-.75.75H5.612l4.158 3.96a.75.75 0 1 1-1.04 1.08l-5.5-5.25a.75.75 0 0 1 0-1.08l5.5-5.25a.75.75 0 1 1 1.04 1.08L5.612 9.25H16.25A.75.75 0 0 1 17 10z" clipRule="evenodd" />
    </svg>
  )
}

export default function ResultScreen({ result, imageUrl, onBack }: Props) {
  const { itemName, guidelines, regionName } = result
  const [chatOpen, setChatOpen] = useState(false)

  return (
    <div className="flex flex-col h-full bg-background">
      {/* Header */}
      <div className="bg-primary text-primary-foreground px-5 pt-12 pb-4 flex items-center gap-3">
        <button
          onClick={onBack}
          className="w-9 h-9 rounded-xl bg-primary-foreground/10 flex items-center justify-center active:bg-primary-foreground/20 transition-colors"
          aria-label="뒤로 가기"
        >
          <BackIcon />
        </button>
        <div className="flex-1">
          <h2 className="text-base font-bold">분석 결과</h2>
          <p className="text-xs opacity-70">{regionName} 기준</p>
        </div>
        <div className="w-10 h-10 rounded-xl overflow-hidden border-2 border-primary-foreground/30">
          <img src={imageUrl} alt="분석된 폐기물 사진" className="w-full h-full object-cover" />
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto no-scrollbar px-5 pt-5 pb-6 flex flex-col gap-4">

        {/* Recognition Card — item + collection days */}
        <div className="bg-card rounded-2xl border border-border p-5 flex items-center justify-between gap-4">
          <div>
            <p className="text-xs text-muted-foreground mb-1">인식된 품목</p>
            <h3 className="text-2xl font-bold text-foreground">{itemName}</h3>
          </div>
          <div className="flex-shrink-0 flex flex-col items-end gap-1">
            <p className="text-[10px] text-muted-foreground">수거 요일</p>
            <p className="text-sm font-semibold text-primary text-right">{guidelines.collectionDays}</p>
          </div>
        </div>

        {/* Guidelines Card */}
        <div className="bg-card rounded-2xl border border-border overflow-hidden">
          <div className="px-5 pt-5 pb-4 border-b border-border">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-widest">
              배출 방법
            </p>
            <h4 className="text-base font-bold text-foreground mt-1">{itemName} 분리배출 안내</h4>
          </div>

          {/* Steps */}
          <div className="px-5 py-4 flex flex-col gap-0">
            {guidelines.steps.map((step, i) => (
              <div key={i} className="flex gap-3 relative pb-4">
                {i < guidelines.steps.length - 1 && (
                  <div className="absolute left-[15px] top-7 bottom-0 w-px bg-border" />
                )}
                <div className="w-7 h-7 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0 z-10">
                  <span className="text-xs font-bold font-mono text-primary">{i + 1}</span>
                </div>
                <p className="text-sm text-foreground leading-relaxed pt-1">{step}</p>
              </div>
            ))}
          </div>

          {/* Notes */}
          {guidelines.notes.length > 0 && (
            <div className="px-5 pb-5">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2.5">
                주의사항
              </p>
              <div className="flex flex-col gap-2">
                {guidelines.notes.map((note, i) => (
                  <div key={i} className="flex items-start gap-2">
                    <span className="text-amber-500 text-xs mt-0.5 flex-shrink-0 font-bold">!</span>
                    <p className="text-xs text-muted-foreground leading-relaxed">{note}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Special instructions */}
          {guidelines.specialInstructions && (
            <div className="mx-5 mb-5 px-4 py-3 bg-blue-50 rounded-xl border border-blue-100">
              <p className="text-xs text-blue-800 leading-relaxed">{guidelines.specialInstructions}</p>
            </div>
          )}
        </div>

        {/* Source — whole box is the link */}
        <a
          href={guidelines.sourceUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center justify-between px-4 py-3.5 bg-muted rounded-xl active:bg-border transition-colors"
          aria-label={`${guidelines.source} 원문 보기`}
        >
          <div className="min-w-0">
            <p className="text-xs text-muted-foreground">출처 — 탭하면 원문으로 이동</p>
            <p className="text-xs font-medium text-foreground truncate mt-0.5">{guidelines.source}</p>
          </div>
          <svg viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0 ml-3" aria-hidden="true">
            <path fillRule="evenodd" d="M4.25 5.5a.75.75 0 0 0-.75.75v8.5c0 .414.336.75.75.75h8.5a.75.75 0 0 0 .75-.75v-4a.75.75 0 0 1 1.5 0v4A2.25 2.25 0 0 1 12.75 17h-8.5A2.25 2.25 0 0 1 2 14.75v-8.5A2.25 2.25 0 0 1 4.25 4h5a.75.75 0 0 1 0 1.5h-5z" clipRule="evenodd" />
            <path fillRule="evenodd" d="M6.194 12.753a.75.75 0 0 0 1.06.053L16.5 4.44v2.81a.75.75 0 0 0 1.5 0v-4.5a.75.75 0 0 0-.75-.75h-4.5a.75.75 0 0 0 0 1.5h2.553l-9.056 8.194a.75.75 0 0 0-.053 1.06z" clipRule="evenodd" />
          </svg>
        </a>
      </div>

      {/* Bottom CTA */}
      <div className="px-5 pb-8 pt-3 flex flex-col gap-3">
        <p className="text-sm font-semibold text-foreground text-center">인식된 품목이 맞습니까?</p>
        <div className="flex gap-2.5">
          <button
            onClick={onBack}
            className="flex-1 py-3.5 rounded-2xl border border-border bg-card text-sm font-semibold text-foreground active:bg-muted transition-all"
          >
            다시 촬영
          </button>
          <button
            onClick={onBack}
            className="flex-1 py-3.5 rounded-2xl bg-primary text-primary-foreground font-semibold text-sm active:scale-[0.98] transition-all shadow-md shadow-primary/20"
          >
            맞아요
          </button>
        </div>
      </div>

      {/* Floating chat character */}
      {!chatOpen && (
        <button
          onClick={() => setChatOpen(true)}
          className="absolute bottom-28 right-5 flex flex-col items-center gap-1 animate-float-bob active:scale-90 transition-transform"
          aria-label="AI 상담 열기"
        >
          <div className="bg-white border border-border rounded-2xl rounded-br-sm px-3 py-1.5 shadow-md">
            <p className="text-[11px] font-semibold text-foreground whitespace-nowrap">궁금해요!</p>
          </div>
          <div className="relative">
            <svg width="64" height="64" viewBox="0 0 64 64" fill="none" aria-hidden="true">
              <ellipse cx="32" cy="61" rx="14" ry="3" fill="black" fillOpacity="0.08" />
              <circle cx="32" cy="30" r="26" fill="#1b5c35" />
              <ellipse cx="24" cy="20" rx="7" ry="5" fill="white" fillOpacity="0.15" transform="rotate(-20 24 20)" />
              <circle cx="24" cy="27" r="4" fill="white" />
              <circle cx="40" cy="27" r="4" fill="white" />
              <circle cx="25" cy="28" r="2" fill="#0f3d22" />
              <circle cx="41" cy="28" r="2" fill="#0f3d22" />
              <circle cx="26" cy="27" r="0.8" fill="white" />
              <circle cx="42" cy="27" r="0.8" fill="white" />
              <path d="M24 36 Q32 43 40 36" stroke="white" strokeWidth="2.5" strokeLinecap="round" fill="none" />
              <g opacity="0.5" transform="translate(27,39) scale(0.42)">
                <path d="M12 4l-4 4h3c0 5.52 4.48 10 10 10 1.57 0 3.04-.38 4.34-1.03l-1.46-1.46C23 15.68 22.04 16 21 16c-3.87 0-7-3.13-7-7h3l-4-4zM21 4c-1.57 0-3.04.38-4.34 1.03l1.46 1.46C19 6.32 19.96 6 21 6c3.87 0 7 3.13 7 7h-3l4 4 4-4h-3C30 8.48 25.52 4 21 4z" fill="white" />
              </g>
              <line x1="32" y1="4" x2="32" y2="10" stroke="#1b5c35" strokeWidth="2.5" strokeLinecap="round" />
              <circle cx="32" cy="3" r="3" fill="#4ade80" />
            </svg>
          </div>
        </button>
      )}

      <ChatDrawer result={result} open={chatOpen} onClose={() => setChatOpen(false)} />
    </div>
  )
}
