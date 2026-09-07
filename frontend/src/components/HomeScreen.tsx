import { useRef, useState } from "react";
import type { ClassificationResult, User } from "../types";
import { classifyImage, CLASSIFY_STEPS } from "../lib/api";

interface Props {
  user: User;
  onResult: (result: ClassificationResult, imageUrl: string) => void;
  onChangeRegion: () => void;
  onLogout: () => void;
  onStartCapture?: () => void;
  onDemoAnalyzing?: () => void;
  onDemoAgentThinking?: () => void;
  onDemoFail?: () => void;
}

function CameraIcon({ size = 32 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      <circle cx="12" cy="13" r="4" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}

function GalleryIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" className="w-5 h-5" aria-hidden="true">
      <rect
        x="3"
        y="3"
        width="18"
        height="18"
        rx="2"
        stroke="currentColor"
        strokeWidth="1.5"
      />
      <circle
        cx="8.5"
        cy="8.5"
        r="1.5"
        stroke="currentColor"
        strokeWidth="1.5"
      />
      <path
        d="M21 15l-5-5L5 21"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function ChevronDownIcon() {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="currentColor"
      className="w-4 h-4"
      aria-hidden="true"
    >
      <path
        fillRule="evenodd"
        d="M5.22 8.22a.75.75 0 0 1 1.06 0L10 11.94l3.72-3.72a.75.75 0 1 1 1.06 1.06l-4.25 4.25a.75.75 0 0 1-1.06 0L5.22 9.28a.75.75 0 0 1 0-1.06z"
        clipRule="evenodd"
      />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="currentColor"
      className="w-4 h-4"
      aria-hidden="true"
    >
      <path
        fillRule="evenodd"
        d="M16.704 4.153a.75.75 0 0 1 .143 1.052l-8 10.5a.75.75 0 0 1-1.127.075l-4.5-4.5a.75.75 0 0 1 1.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 0 1 1.05-.143z"
        clipRule="evenodd"
      />
    </svg>
  );
}

export default function HomeScreen({
  user,
  onResult,
  onChangeRegion,
  onLogout,
  onStartCapture,
  onDemoAnalyzing,
  onDemoAgentThinking,
  onDemoFail,
}: Props) {
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isClassifying, setIsClassifying] = useState(false);
  const [completedSteps, setCompletedSteps] = useState<number[]>([]);
  const [currentStep, setCurrentStep] = useState(-1);
  const [error, setError] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);

  const cameraRef = useRef<HTMLInputElement>(null);
  const galleryRef = useRef<HTMLInputElement>(null);

  function handleFileSelected(file: File) {
    if (!file.type.startsWith("image/")) {
      setError("이미지 파일을 선택해 주세요");
      return;
    }
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    setSelectedFile(file);
    setError("");
    setCompletedSteps([]);
    setCurrentStep(-1);
  }

  async function handleClassify() {
    if (!selectedFile) return;
    if (!user.regionCode || !user.regionName) {
      setError("먼저 지역을 설정해 주세요");
      return;
    }

    setIsClassifying(true);
    setError("");
    setCompletedSteps([]);
    setCurrentStep(0);

    try {
      const result = await classifyImage(
        selectedFile,
        user.regionCode,
        user.regionName,
        (stepIndex) => {
          setCompletedSteps((prev) => [...prev, stepIndex]);
          setCurrentStep(stepIndex + 1);
        },
      );
      onResult(result, previewUrl!);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "분석에 실패했습니다. 다시 시도해 주세요.",
      );
      setIsClassifying(false);
      setCurrentStep(-1);
    }
  }

  function handleReset() {
    setPreviewUrl(null);
    setSelectedFile(null);
    setError("");
    setCompletedSteps([]);
    setCurrentStep(-1);
    setIsClassifying(false);
  }

  return (
    <div className="flex flex-col h-full bg-background">
      {/* Header */}
      <div className="bg-primary text-primary-foreground px-5 pt-12 pb-4 flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold tracking-tight">분리쏙</h1>
          {user.regionName ? (
            <div className="flex items-center gap-1 mt-0.5">
              <svg
                viewBox="0 0 16 16"
                fill="currentColor"
                className="w-3 h-3 opacity-70"
                aria-hidden="true"
              >
                <path
                  fillRule="evenodd"
                  d="M8 1.5a4.5 4.5 0 1 0 0 9 4.5 4.5 0 0 0 0-9zM2 6a6 6 0 1 1 10.174 4.31l3.258 3.257a.75.75 0 0 1-1.06 1.061l-3.258-3.257A6 6 0 0 1 2 6zm6 3.5a.75.75 0 0 1 .75.75v2a.75.75 0 0 1-1.5 0v-2A.75.75 0 0 1 8 9.5z"
                  clipRule="evenodd"
                />
              </svg>
              <span className="text-xs opacity-70">{user.regionName}</span>
            </div>
          ) : (
            <span className="text-xs opacity-60">지역 미설정</span>
          )}
        </div>

        {/* Menu */}
        <div className="relative">
          <button
            onClick={() => setMenuOpen((v) => !v)}
            className="w-10 h-10 flex items-center justify-center rounded-xl bg-primary-foreground/10 active:bg-primary-foreground/20 transition-colors"
            aria-label="메뉴"
          >
            <svg
              viewBox="0 0 24 24"
              fill="currentColor"
              className="w-5 h-5"
              aria-hidden="true"
            >
              <path
                d="M4 6h16M4 12h16M4 18h16"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                fill="none"
              />
            </svg>
          </button>

          {menuOpen && (
            <div className="absolute right-0 top-12 z-20 w-48 bg-white rounded-xl shadow-xl border border-border overflow-hidden">
              <button
                onClick={() => {
                  onChangeRegion();
                  setMenuOpen(false);
                }}
                className="w-full text-left px-4 py-3.5 text-sm text-foreground hover:bg-muted transition-colors flex items-center gap-2.5"
              >
                <svg
                  viewBox="0 0 20 20"
                  fill="currentColor"
                  className="w-4 h-4 text-muted-foreground"
                  aria-hidden="true"
                >
                  <path
                    fillRule="evenodd"
                    d="M9.69 18.933l.003.001C9.89 19.02 10 19 10 19s.11.02.308-.066l.002-.001.006-.003.018-.008a5.741 5.741 0 0 0 .281-.14c.186-.096.446-.24.757-.433.62-.384 1.445-.966 2.274-1.765C15.302 14.988 17 12.493 17 9A7 7 0 1 0 3 9c0 3.492 1.698 5.988 3.355 7.584a13.731 13.731 0 0 0 2.273 1.765 11.842 11.842 0 0 0 .976.544l.062.029.018.008.006.003zM10 11.25a2.25 2.25 0 1 0 0-4.5 2.25 2.25 0 0 0 0 4.5z"
                    clipRule="evenodd"
                  />
                </svg>
                지역 변경
              </button>
              <div className="h-px bg-border mx-4" />
              <button
                onClick={() => {
                  onLogout();
                  setMenuOpen(false);
                }}
                className="w-full text-left px-4 py-3.5 text-sm text-destructive hover:bg-red-50 transition-colors flex items-center gap-2.5"
              >
                <svg
                  viewBox="0 0 20 20"
                  fill="currentColor"
                  className="w-4 h-4"
                  aria-hidden="true"
                >
                  <path
                    fillRule="evenodd"
                    d="M3 4.25A2.25 2.25 0 0 1 5.25 2h5.5A2.25 2.25 0 0 1 13 4.25v2a.75.75 0 0 1-1.5 0v-2a.75.75 0 0 0-.75-.75h-5.5a.75.75 0 0 0-.75.75v11.5c0 .414.336.75.75.75h5.5a.75.75 0 0 0 .75-.75v-2a.75.75 0 0 1 1.5 0v2A2.25 2.25 0 0 1 10.75 18h-5.5A2.25 2.25 0 0 1 3 15.75V4.25z"
                    clipRule="evenodd"
                  />
                  <path
                    fillRule="evenodd"
                    d="M19 10a.75.75 0 0 0-.75-.75H8.704l1.048-1.069a.75.75 0 1 0-1.064-1.057l-2.5 2.53a.75.75 0 0 0 0 1.057l2.5 2.53a.75.75 0 1 0 1.064-1.057L8.704 10.75H18.25A.75.75 0 0 0 19 10z"
                    clipRule="evenodd"
                  />
                </svg>
                로그아웃
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 flex flex-col px-5 pt-5 pb-4 overflow-y-auto no-scrollbar gap-4">
        {!isClassifying ? (
          <>
            {/* Upload zone */}
            <div
              onClick={() => !previewUrl && cameraRef.current?.click()}
              className={`relative rounded-2xl border-2 overflow-hidden transition-all ${
                previewUrl
                  ? "border-primary"
                  : "border-dashed border-border bg-card hover:border-primary/50 hover:bg-secondary/30 cursor-pointer active:scale-[0.99]"
              }`}
              style={{ minHeight: previewUrl ? 280 : 220 }}
            >
              {previewUrl ? (
                <>
                  <img
                    src={previewUrl}
                    alt="업로드된 폐기물 사진"
                    className="w-full h-full object-cover"
                    style={{ maxHeight: 320 }}
                  />
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleReset();
                    }}
                    className="absolute top-3 right-3 w-8 h-8 rounded-full bg-black/50 flex items-center justify-center text-white text-xs hover:bg-black/70 transition-colors"
                    aria-label="사진 제거"
                  >
                    <svg
                      viewBox="0 0 20 20"
                      fill="currentColor"
                      className="w-4 h-4"
                      aria-hidden="true"
                    >
                      <path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22z" />
                    </svg>
                  </button>
                  <div className="absolute bottom-3 left-3">
                    <span className="px-2.5 py-1 bg-primary text-primary-foreground text-xs font-semibold rounded-full">
                      사진 선택됨
                    </span>
                  </div>
                </>
              ) : (
                <div className="flex flex-col items-center justify-center h-full py-10 gap-3 text-muted-foreground">
                  <div className="w-16 h-16 rounded-2xl bg-muted flex items-center justify-center">
                    <CameraIcon size={28} />
                  </div>
                  <div className="text-center">
                    <p className="text-sm font-semibold text-foreground">
                      탭하여 촬영
                    </p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      또는 아래에서 갤러리 선택
                    </p>
                  </div>
                </div>
              )}
            </div>

            {/* Gallery button */}
            {!previewUrl && (
              <button
                onClick={() => galleryRef.current?.click()}
                className="flex items-center justify-center gap-2.5 px-5 py-3.5 rounded-xl border border-border bg-card text-sm font-medium text-foreground hover:bg-muted active:scale-[0.98] transition-all"
              >
                <GalleryIcon />
                갤러리에서 선택
              </button>
            )}

            {/* Region warning */}
            {!user.regionCode && (
              <div className="flex items-start gap-3 px-4 py-3.5 bg-amber-50 rounded-xl border border-amber-200">
                <span className="text-amber-500 text-base mt-0.5 flex-shrink-0">
                  !
                </span>
                <div>
                  <p className="text-sm font-semibold text-amber-900">
                    지역이 설정되지 않았습니다
                  </p>
                  <button
                    onClick={onChangeRegion}
                    className="text-xs text-amber-700 underline mt-0.5"
                  >
                    지역 설정하기
                  </button>
                </div>
              </div>
            )}

            {error && (
              <p className="text-sm text-destructive bg-red-50 px-4 py-3 rounded-lg border border-red-100">
                {error}
              </p>
            )}
          </>
        ) : (
          /* Classifying state: show pipeline steps */
          <div className="flex flex-col items-center pt-4 gap-6">
            <div className="w-20 h-20 rounded-2xl overflow-hidden shadow-lg flex-shrink-0">
              {previewUrl && (
                <img
                  src={previewUrl}
                  alt="분석 중인 사진"
                  className="w-full h-full object-cover"
                />
              )}
            </div>

            <div className="w-full flex flex-col gap-0">
              {CLASSIFY_STEPS.map((step, i) => {
                const done = completedSteps.includes(i);
                const active = currentStep === i;
                return (
                  <div
                    key={i}
                    className="flex items-center gap-3 px-4 py-3.5 relative"
                  >
                    {i < CLASSIFY_STEPS.length - 1 && (
                      <div
                        className={`absolute left-[26px] top-[44px] w-px h-[calc(100%-20px)] transition-colors ${done ? "bg-primary" : "bg-border"}`}
                      />
                    )}
                    <div
                      className={`w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 z-10 transition-all ${
                        done
                          ? "bg-primary text-primary-foreground"
                          : active
                            ? "bg-primary/10 border-2 border-primary"
                            : "bg-muted border-2 border-border"
                      }`}
                    >
                      {done ? (
                        <CheckIcon />
                      ) : active ? (
                        <svg
                          className="animate-spin h-3 w-3 text-primary"
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
                      ) : null}
                    </div>
                    <div>
                      <p
                        className={`text-sm font-medium transition-colors ${
                          done
                            ? "text-primary"
                            : active
                              ? "text-foreground"
                              : "text-muted-foreground"
                        }`}
                      >
                        {step.label}
                      </p>
                      {active && (
                        <p className="text-xs text-muted-foreground mt-0.5">
                          진행 중...
                        </p>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>

            <p className="text-xs text-muted-foreground text-center">
              AI가 분리배출 방법을 분석하고 있습니다
            </p>
          </div>
        )}

        {/* Hidden file inputs */}
        <input
          ref={cameraRef}
          type="file"
          accept="image/*"
          capture="environment"
          className="hidden"
          onChange={(e) =>
            e.target.files?.[0] && handleFileSelected(e.target.files[0])
          }
        />
        <input
          ref={galleryRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={(e) =>
            e.target.files?.[0] && handleFileSelected(e.target.files[0])
          }
        />
      </div>

      {/* Bottom CTA */}
      {!isClassifying && (
        <div className="px-5 pb-8 pt-2 flex flex-col gap-2.5">
          {/* Primary: go to new capture flow */}
          {onStartCapture && (
            <button
              onClick={onStartCapture}
              disabled={!user.regionCode}
              className="w-full py-4 bg-primary text-primary-foreground rounded-2xl font-semibold text-base shadow-lg shadow-primary/20 active:scale-[0.98] transition-all disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2.5"
            >
              <CameraIcon size={20} />
              스마트 촬영 시작
            </button>
          )}
          {/* Legacy quick-upload still available */}
          <button
            onClick={handleClassify}
            disabled={!selectedFile || !user.regionCode}
            className="w-full py-3.5 border border-border bg-card text-foreground rounded-2xl font-medium text-sm active:bg-muted transition-all disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            <CameraIcon size={16} />
            {selectedFile ? "빠른 분석하기" : "기존 방식으로 선택"}
          </button>
          {previewUrl && (
            <button
              onClick={() => cameraRef.current?.click()}
              className="w-full py-3 text-sm font-medium text-muted-foreground flex items-center justify-center gap-1.5"
            >
              <ChevronDownIcon />
              다시 촬영하기
            </button>
          )}
        </div>
      )}

      {/* Overlay to close menu */}
      {menuOpen && (
        <div
          className="fixed inset-0 z-10"
          onClick={() => setMenuOpen(false)}
          aria-hidden="true"
        />
      )}
    </div>
  );
}
