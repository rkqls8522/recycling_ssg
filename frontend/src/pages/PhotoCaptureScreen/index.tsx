import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import type {
  AnalyzeApiResponse,
  CaptureState,
  ClassificationResult,
  DisposalScheduleResponse,
  User,
} from "../../types";
import useAxios from "../../hooks/useAxios";
import {
  buildAnalyzeResult,
  FALLBACK_GUIDELINE,
  mapDisposalSchedule,
  startProgressTicker,
  type AnalyzeOutcome,
} from "../../api/analyze";
import { useAuthContext } from "../AuthScreen/AuthContext";
import CaptureView from "./CaptureView";
import AnalyzingView from "./AnalyzingView";
import ResultFailView from "./ResultFailView";
import AgentThinkingView from "./AgentThinkingView";
import { authHeaders } from "@/utils/get-auth-headers";

function buildFailResult(user: User | null): ClassificationResult {
  return {
    itemName: "",
    itemCategory: "",
    itemCategoryEn: "unclear",
    confidence: 32,
    confidenceLevel: "low",
    failureHint: "blurry",
    guidelines: {
      steps: [],
      notes: [],
      collectionDays: "",
      source: "",
      sourceUrl: "",
    },
    regionCode: user?.regionCode ?? "",
    regionName: user?.regionName ?? "",
  };
}

export default function PhotoCaptureScreen() {
  const { user } = useAuthContext();
  const navigate = useNavigate();

  const [captureState, setCaptureState] = useState<CaptureState>("capture");
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [result, setResult] = useState<ClassificationResult | null>(null);
  const [completedSteps, setCompletedSteps] = useState<number[]>([]);
  const [currentStep, setCurrentStep] = useState(-1);

  const galleryRef = useRef<HTMLInputElement>(null);
  const prevUrl = useRef<string | null>(null);

  // 실제 백엔드 연동 — AuthScreen/MyPageScreen과 동일하게 useAxios(hooks/useAxios.tsx)로 호출한다.
  const { refetch: analyzeRequest } = useAxios<AnalyzeApiResponse>(
    "",
    { method: "post" },
    false,
  );
  const { refetch: disposalRequest } = useAxios<DisposalScheduleResponse>(
    "",
    { method: "get" },
    false,
  );

  if (!user) return null;

  function onBack() {
    navigate("/home");
  }

  function onViewGuidelines(r: ClassificationResult, imageUrl: string) {
    navigate("/result", { state: { result: r, imageUrl } });
  }

  function setPreviewWithCleanup(url: string | null) {
    if (prevUrl.current) URL.revokeObjectURL(prevUrl.current);
    prevUrl.current = url;
    setPreviewUrl(url);
  }

  function handleFileSelected(file: File) {
    const url = URL.createObjectURL(file);

    setSelectedFile(file);
    setPreviewWithCleanup(url);
    setCaptureState("capture");
    setCompletedSteps([]);
    setCurrentStep(-1);
  }

  // 분석 중 화면이 응답 속도에 따라 너무 빨리 사라지지 않도록 최소 이 정도는 보여준다.
  const MIN_ANALYZING_MS = 5000;

  // 실제 /api/v1/analyze 호출 — useAxios로 요청하고, SUCCESS면 이어서 배출정보(/disposal/schedule)까지 조회한다.
  async function runRealAnalyze(
    onProgress: (stepIndex: number) => void,
  ): Promise<AnalyzeOutcome> {
    const startedAt = Date.now();
    const ticker = startProgressTicker(onProgress);
    try {
      const form = new FormData();
      form.append("image", selectedFile!);

      const data = await analyzeRequest({
        url: "/api/v1/analyze",
        data: form,
        headers: authHeaders(),
      });

      if (data.status === "RETAKE_REQUIRED") {
        return { status: "RETAKE_REQUIRED", retakeMessage: data.message };
      }

      const top1 = data.candidate_scores[0];
      let guidelines = FALLBACK_GUIDELINE;
      if (top1) {
        try {
          const schedule = await disposalRequest({
            url: "/api/v1/disposal/schedule",
            params: { class_id: top1.class_id },
            headers: authHeaders(),
          });
          guidelines = mapDisposalSchedule(schedule);
        } catch {
          // 배출정보 조회가 실패해도 분석 결과 자체는 보여준다
        }
      }

      return {
        status: "SUCCESS",
        result: buildAnalyzeResult(data, user!.regionCode!, guidelines),
      };
    } finally {
      const elapsed = Date.now() - startedAt;
      if (elapsed < MIN_ANALYZING_MS) {
        await new Promise((resolve) =>
          setTimeout(resolve, MIN_ANALYZING_MS - elapsed),
        );
      }
      ticker.finish();
    }
  }

  async function handleAnalyze() {
    if (!selectedFile || !user!.regionCode || !user!.regionName) return;

    setCaptureState("analyzing");
    setCompletedSteps([]);
    setCurrentStep(0);

    const onProgress = (stepIndex: number) => {
      setCompletedSteps((prev) => [...prev, stepIndex]);
      setCurrentStep(stepIndex + 1);
    };

    try {
      const outcome = await runRealAnalyze(onProgress);

      if (outcome.status === "RETAKE_REQUIRED") {
        // 정상 비즈니스 분기(HTTP 200) — 재촬영 안내
        setResult({ ...buildFailResult(user), failureHint: "unclear" });
        setCaptureState("fail");
        return;
      }

      const classifyResult = outcome.result!;
      setResult(classifyResult);

      if (classifyResult.confidenceLevel === "high") {
        // High confidence → skip intermediate result, go straight to guidelines
        onViewGuidelines(classifyResult, previewUrl!);
      } else if (classifyResult.confidenceLevel === "uncertain") {
        setCaptureState("uncertain");
      } else {
        setCaptureState("fail");
      }
    } catch {
      setResult(null);
      setCaptureState("fail");
    }
  }

  function handleReset() {
    setPreviewWithCleanup(null);
    setSelectedFile(null);
    setCaptureState("capture");
    setResult(null);
    setCompletedSteps([]);
    setCurrentStep(-1);
  }

  function handleOpenGallery() {
    setCaptureState("capture");
    // Small delay to let state settle before triggering gallery
    setTimeout(() => galleryRef.current?.click(), 50);
  }

  return (
    <div className="h-full relative">
      {/* Transition wrapper — each view fades in */}
      {captureState === "capture" && (
        <CaptureView
          previewUrl={previewUrl}
          onFileSelected={handleFileSelected}
          onAnalyze={handleAnalyze}
          onReset={handleReset}
          onBack={onBack}
          hasRegion={!!user.regionCode}
          onOpenMyPage={() => navigate("/mypage")}
          onSetRegion={() => navigate("/region")}
        />
      )}

      {captureState === "analyzing" && previewUrl && (
        <AnalyzingView
          previewUrl={previewUrl}
          completedSteps={completedSteps}
          currentStep={currentStep}
        />
      )}

      {captureState === "agent_thinking" && (
        <AgentThinkingView onBack={handleReset} />
      )}

      {captureState === "fail" && (
        <ResultFailView
          failureHint={result?.failureHint}
          imageUrl={previewUrl ?? ""}
          onRetake={handleReset}
          onGallery={handleOpenGallery}
        />
      )}

      {/* Shared hidden gallery input — used by ResultFailView's gallery button */}
      <input
        ref={galleryRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) handleFileSelected(file);
          e.target.value = "";
        }}
      />
    </div>
  );
}
