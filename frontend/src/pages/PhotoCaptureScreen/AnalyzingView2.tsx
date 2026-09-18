import { useEffect, useState } from "react";
import { CLASSIFY_STEPS } from "@/api/api";

interface Props {
  previewUrl: string;
  completedSteps: number[];
  currentStep: number;
}

const ANALYZING_MESSAGES = [
  "이미지를 준비하고 있습니다...",
  "폐기물 영역을 찾고 있습니다...",
  "품목을 분류하고 있습니다...",
  "지역 배출 지침을 검색하고 있습니다...",
  "맞춤 안내문을 만들고 있습니다...",
];

const TIP_IMAGES = [
  "/tips/TIP (1).png",
  "/tips/TIP (2).png",
  "/tips/TIP (3).png",
  "/tips/TIP (4).png",
  "/tips/TIP (5).png",
  "/tips/TIP (6).png",
  "/tips/TIP (7).png",
  "/tips/TIP (8).png",
  "/tips/TIP (9).png",
  "/tips/TIP (10).png",
  "/tips/TIP (11).png",
  "/tips/TIP (12).png",
];

function randomTipIndex(exclude = -1) {
  let idx = Math.floor(Math.random() * TIP_IMAGES.length);
  if (TIP_IMAGES.length > 1 && idx === exclude)
    idx = (idx + 1) % TIP_IMAGES.length;
  return idx;
}

export default function AnalyzingView2({
  previewUrl,
  completedSteps,
  currentStep,
}: Props) {
  const [dotCount, setDotCount] = useState(1);
  const [tipIdx, setTipIdx] = useState(() => randomTipIndex());
  const [tipVisible, setTipVisible] = useState(true);

  // Animated ellipsis
  useEffect(() => {
    const id = setInterval(() => setDotCount((c) => (c % 3) + 1), 500);
    return () => clearInterval(id);
  }, []);

  // Rotate tip image every 10 seconds with a brief fade transition
  useEffect(() => {
    const id = setInterval(() => {
      setTipVisible(false);
      setTimeout(() => {
        setTipIdx((prev) => randomTipIndex(prev));
        setTipVisible(true);
      }, 300);
    }, 10000);
    return () => clearInterval(id);
  }, []);

  const dots = ".".repeat(dotCount);
  const message =
    ANALYZING_MESSAGES[Math.min(currentStep, ANALYZING_MESSAGES.length - 1)];
  const totalSteps = CLASSIFY_STEPS.length;
  const progressPercent =
    totalSteps > 0
      ? Math.round(
          ((completedSteps.length + (currentStep < totalSteps ? 0.5 : 0)) /
            totalSteps) *
            100,
        )
      : 0;

  return (
    <div className="flex flex-col h-full bg-background animate-fade-in-up">
      {/* Header */}
      <div className="bg-primary text-primary-foreground px-5 pt-12 pb-4">
        <div className="flex items-center justify-between mb-4">
          <div className="w-9" />
          <div className="flex items-center gap-1.5">
            {["촬영", "분석", "결과"].map((label, i) => (
              <div key={i} className="flex items-center">
                <div className="flex flex-col items-center gap-0.5">
                  <div
                    className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold ${
                      i === 0
                        ? "bg-primary-foreground/30 text-primary-foreground/60"
                        : i === 1
                          ? "bg-primary-foreground text-primary ring-2 ring-primary-foreground/30"
                          : "bg-primary-foreground/20 text-primary-foreground/50"
                    }`}
                  >
                    {i === 0 ? (
                      <svg
                        viewBox="0 0 12 12"
                        fill="none"
                        className="w-2.5 h-2.5"
                      >
                        <path
                          d="M10 3L5 8.5 2 5.5"
                          stroke="currentColor"
                          strokeWidth="1.5"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                      </svg>
                    ) : i === 1 ? (
                      <svg
                        className="animate-spin w-2.5 h-2.5"
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
                    ) : (
                      i + 1
                    )}
                  </div>
                  <span
                    className={`text-[9px] font-semibold ${
                      i === 1
                        ? "text-primary-foreground"
                        : "text-primary-foreground/50"
                    }`}
                  >
                    {label}
                  </span>
                </div>
                {i < 2 && (
                  <div
                    className={`w-8 h-px mx-1 mb-3 ${
                      i === 0
                        ? "bg-primary-foreground/40"
                        : "bg-primary-foreground/20"
                    }`}
                  />
                )}
              </div>
            ))}
          </div>
          <div className="w-9" />
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 flex flex-col px-5 pt-4 pb-5 overflow-hidden">
        {/* Analysis status — compact */}
        <div className="mb-4">
          <p className="text-sm font-semibold text-foreground mb-2">
            이미지를 분석하고 있어요{dots}
          </p>
          <div className="flex items-center gap-2">
            <div className="flex-1 h-2.5 bg-muted rounded-full overflow-hidden">
              <div
                className="h-full bg-primary rounded-full transition-all duration-700"
                style={{ width: `${progressPercent}%` }}
              />
            </div>
            <span className="text-sm font-bold text-primary tabular-nums w-10 text-right">
              {progressPercent}%
            </span>
          </div>
          <p className="text-xs text-muted-foreground mt-1.5 leading-relaxed">
            잠시만 기다려주세요. 더 정확한 분류를 위해 AI가 열심히 분석하고
            있어요.
          </p>
          {/* Keep message in state for logic reference, render subtly */}
          <p className="text-[10px] text-muted-foreground/60 mt-0.5">
            {message}
          </p>
        </div>

        {/* Tip image — fills available space */}
        <div className="flex-1 flex items-center justify-center min-h-0 mb-4">
          <img
            src={TIP_IMAGES[tipIdx]}
            alt="분리수거 팁"
            className="w-full h-full rounded-2xl"
            style={{
              objectFit: "contain",
              maxHeight: "100%",
              opacity: tipVisible ? 1 : 0,
              transition: "opacity 0.3s ease",
            }}
          />
        </div>

        {/* Bottom notice */}
        <div className="bg-emerald-50 rounded-xl px-4 py-3 flex items-start gap-2.5 flex-shrink-0">
          <span className="text-base leading-none mt-0.5">💡</span>
          <div>
            <p className="text-xs font-bold text-emerald-800">잠깐!</p>
            <p className="text-xs text-emerald-700 leading-relaxed mt-0.5">
              올바른 분리배출이 더 좋은 환경을 만들어요.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
