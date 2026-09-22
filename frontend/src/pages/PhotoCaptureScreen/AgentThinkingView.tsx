import { useEffect, useState } from "react";
import BackButton from "../../components/common/BackButton";
import TipPoster from "./TipPoster";

interface Props {
  onBack: () => void;
}

const AGENT_STEPS = [
  "분리배출 규정 문서를 불러오는 중...",
  "지역별 예외 조항을 검토하는 중...",
  "유사 사례 데이터베이스를 탐색하는 중...",
  "복합 소재 여부를 교차 확인하는 중...",
  "최신 지침 개정 이력을 확인하는 중...",
  "맞춤 배출 안내문을 작성하는 중...",
];

export default function AgentThinkingView({ onBack }: Props) {
  const [elapsed, setElapsed] = useState(0);
  const [stepIndex, setStepIndex] = useState(0);
  const [blinkOn, setBlinkOn] = useState(true);
  const [dotCount, setDotCount] = useState(1);

  // Elapsed timer
  useEffect(() => {
    const id = setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => clearInterval(id);
  }, []);

  // Advance to the next agent step one at a time (~30s to reach the last of 6 steps,
  // then hold there until the actual agent call finishes).
  useEffect(() => {
    const id = setInterval(() => {
      setStepIndex((prev) => (prev < AGENT_STEPS.length - 1 ? prev + 1 : prev));
    }, 5000);
    return () => clearInterval(id);
  }, []);

  // Blink eyes on character
  useEffect(() => {
    const id = setInterval(() => {
      setBlinkOn(false);
      setTimeout(() => setBlinkOn(true), 140);
    }, 3000);
    return () => clearInterval(id);
  }, []);

  // Ellipsis
  useEffect(() => {
    const id = setInterval(() => setDotCount((c) => (c % 3) + 1), 500);
    return () => clearInterval(id);
  }, []);

  const dots = ".".repeat(dotCount);
  const mins = Math.floor(elapsed / 60);
  const secs = elapsed % 60;
  const timeLabel = mins > 0 ? `${mins}분 ${secs}초` : `${secs}초`;

  return (
    <div className="flex flex-col h-full bg-background animate-fade-in-up">
      {/* Header */}
      <div className="bg-primary text-primary-foreground px-5 pt-12 pb-4">
        <div className="flex items-center justify-between mb-4">
          <BackButton onClick={onBack} ariaLabel="취소" />
          <div className="text-center">
            <p className="text-xs font-semibold opacity-70 uppercase tracking-widest">
              심층 분석
            </p>
          </div>
          {/* Elapsed time */}
          <div className="px-2.5 py-1 bg-primary-foreground/10 rounded-full">
            <span className="text-xs font-mono font-semibold">{timeLabel}</span>
          </div>
        </div>
      </div>

      {/* Main */}
      <div className="flex-1 overflow-y-auto no-scrollbar px-5 pt-6 pb-6 flex flex-col gap-5">
        {/* Agent reasoning steps */}
        <div className="bg-card rounded-2xl border border-border overflow-hidden">
          <div className="px-4 py-3 border-b border-border flex items-center gap-2">
            <div className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              에이전트 처리 현황
            </p>
          </div>
          <div
            key={stepIndex}
            className="flex items-center gap-3 px-4 py-3 animate-step-appear"
          >
            <div className="w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 bg-primary/10 border-2 border-primary">
              <svg
                className="animate-spin h-2.5 w-2.5 text-primary"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                />
              </svg>
            </div>
            <p className="text-xs font-medium flex-1 text-foreground">
              {AGENT_STEPS[stepIndex]}
            </p>
          </div>
        </div>

        {/* Tip poster — AnalyzingView2와 동일한 컴포넌트 재사용 */}
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-2">
            <div className="h-px flex-1 bg-border" />
            <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest">
              분리배출 팁
            </span>
            <div className="h-px flex-1 bg-border" />
          </div>
          <TipPoster className="h-130 flex items-center justify-center" />
        </div>

        {/* Cancel hint */}
        <p className="text-xs text-muted-foreground text-center">
          너무 오래 걸리면{" "}
          <button
            onClick={onBack}
            className="text-primary font-semibold underline"
          >
            취소하고 다시 촬영
          </button>
          해 주세요
        </p>
      </div>
    </div>
  );
}
