import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { ClassificationResult } from "../../types";
import { classifyImage, CLASSIFY_STEPS } from "../../api/api";
import { useAuthContext } from "../AuthScreen/AuthContext";
import {
  ChevronDownIcon,
  CheckIcon,
  GalleryIcon,
  CameraIcon,
  SearchIcon,
  UserIcon,
} from "@/components/common/Icons";

export default function HomeScreen() {
  const { user, logout } = useAuthContext();
  const navigate = useNavigate();
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isClassifying, setIsClassifying] = useState(false);
  const [completedSteps, setCompletedSteps] = useState<number[]>([]);
  const [currentStep, setCurrentStep] = useState(-1);
  const [error, setError] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);

  const cameraRef = useRef<HTMLInputElement>(null);
  const galleryRef = useRef<HTMLInputElement>(null);

  if (!user) return null;

  function onResult(result: ClassificationResult, imageUrl: string) {
    navigate("/result", { state: { result, imageUrl } });
  }

  function onChangeRegion() {
    navigate("/region");
  }

  function onLogout() {
    logout();
    navigate("/login", { replace: true });
  }

  function onStartCapture() {
    navigate("/capture", { state: { demoState: "uncertain" } });
  }

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
    if (!user!.regionCode || !user!.regionName) {
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
        user!.regionCode,
        user!.regionName,
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
              <SearchIcon />
              <span className="text-xs opacity-70">{user.regionName}</span>
            </div>
          ) : (
            <span className="text-xs opacity-60">지역 미설정</span>
          )}
        </div>

        {/* Menu */}
        <div className="relative">
          <button
            onClick={() => navigate("/mypage")}
            className="w-10 h-10 flex items-center justify-center rounded-xl bg-primary-foreground/10 active:bg-primary-foreground/20 transition-colors"
            aria-label="메뉴"
          >
            <UserIcon />
          </button>
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
