import useAxios from "@/hooks/useAxios";
import {
  AnalyzeApiResponse,
  AnalyzeSuccessBody,
  CaptureState,
  ClassificationResult,
  DisposalGuideline,
  DisposalScheduleResponse,
  User,
} from "@/types";
import { authHeaders } from "@/utils/header";
import { useAuthContext } from "../AuthScreen/AuthContext";
import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

export { MOCK_MODE } from "../../api/config";

export interface AnalyzeOutcome {
  status: "SUCCESS" | "RETAKE_REQUIRED";
  result?: ClassificationResult;
  retakeMessage?: string;
}

// 배출정보 조회가 실패했을 때 쓰는 안전한 기본값
export const FALLBACK_GUIDELINE: DisposalGuideline = {
  steps: ["지역 기준에 따라 배출해주세요."],
  notes: [],
  collectionDays: "정보 없음",
  source: "",
  sourceUrl: "",
};

// POST /api/v1/analyze 응답의 national_rule/region_rule(RAG 서비스 node2 결과)
// → 화면에서 쓰는 DisposalGuideline으로 변환.
// national_rule은 전국 공통 배출요령, region_rule은 있을 때만(경기도 지자체 예외) 추가로 얹는다.
// URL에서 "hscity.go.kr" 같은 호스트명만 뽑아낸다 (표시용, 실패하면 원본 문자열 그대로).
function hostnameOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

export function buildGuidelineFromAnalyze(
  data: AnalyzeSuccessBody,
): DisposalGuideline {
  const steps: string[] = [];
  const notes: string[] = [];

  const nationalRule =
    data.national_rule?.method != null
      ? { source: data.national_rule.source, method: data.national_rule.method }
      : null;
  if (nationalRule) {
    steps.push(nationalRule.method);
  }

  const regionRule = data.region_rule
    ? {
        region: data.region_rule.region,
        method: data.region_rule.method,
        sourceLabel: `${data.region_rule.region}청 홈페이지 — ${hostnameOf(data.region_rule.source_url)}`,
        sourceUrl: data.region_rule.source_url,
      }
    : null;
  if (regionRule) {
    notes.push(
      `[${regionRule.region} 지자체 예외 · ${data.region_rule!.exception_type}] ${regionRule.method}`,
    );
  }

  if (!nationalRule && !regionRule) {
    return FALLBACK_GUIDELINE;
  }

  return {
    steps: steps.length > 0 ? steps : ["지역 기준에 따라 배출해주세요."],
    notes,
    collectionDays: data.disposal_day ?? "정보 없음",
    source: regionRule?.region ?? nationalRule?.source ?? "기후에너지환경부",
    sourceUrl: regionRule?.sourceUrl ?? "",
    nationalRule,
    regionRule,
  };
}

// GET /api/v1/disposal/schedule 응답 → 화면에서 쓰는 DisposalGuideline으로 변환.
// (피드백으로 재분류된 class_id에 대해 배출정보를 다시 조회하는 useFeedback.tsx 전용 —
// /analyze 흐름 자체는 위 buildGuidelineFromAnalyze를 쓰고 이 함수는 호출하지 않는다.)
export function mapDisposalSchedule(
  d: DisposalScheduleResponse,
): DisposalGuideline {
  return {
    steps: [d.disposal_method ?? "지역 기준에 따라 배출해주세요."],
    notes: [],
    collectionDays: d.disposal_day ?? "정보 없음",
    source: d.source || "행정안전부 생활쓰레기배출정보",
    sourceUrl: "",
  };
}

// POST /api/v1/analyze의 SUCCESS 응답 + 배출정보 → ClassificationResult로 변환
export function buildAnalyzeResult(
  data: AnalyzeSuccessBody,
  regionCode: string,
  guidelines: DisposalGuideline,
): ClassificationResult {
  // Top-1(실제 예측)은 이제 최상위 class_id/score 필드에 있다 — candidate_scores는
  // Top-1을 제외한 "다른 후보"만 담고 있으므로 더 이상 [0]을 쓰지 않는다.
  return {
    itemName: data.minor_category,
    itemCategory: data.major_category,
    itemCategoryEn: String(data.class_id),
    confidence: Math.round(data.score * 100),
    confidenceLevel: "high",
    guidelines,
    regionCode,
    regionName: `${data.user_region.sido_name} ${data.user_region.sgg_name}`,
    feedbackId: data.feedback_id,
    classId: data.class_id,
    candidateScores: data.candidate_scores,
  };
}

// 실제 요청은 단일 요청/응답이라 진짜 진행률을 알 수 없다.
// 응답을 기다리는 동안 capStep까지만 일정 간격으로 진행 표시를 채우고,
// 응답이 오면 finish()로 남은 단계(기본 4까지)를 한번에 채운다.
// 기본값(1초 간격 * capStep 4)은 handleAnalyze의 최소 노출 시간(5초)과 맞춰
// 분석 중 화면이 5단계를 고르게 채우며 끝나도록 맞춘 것.
export function startProgressTicker(
  onProgress?: (stepIndex: number) => void,
  capStep = 4,
  intervalMs = 1000,
) {
  let step = -1;
  const id = setInterval(() => {
    if (step < capStep) {
      step += 1;
      onProgress?.(step);
    }
  }, intervalMs);
  return {
    finish(lastStep = 4) {
      clearInterval(id);
      while (step < lastStep) {
        step += 1;
        onProgress?.(step);
      }
    },
    stop() {
      clearInterval(id);
    },
  };
}

// 분석 중 화면이 응답 속도에 따라 너무 빨리 사라지지 않도록 최소 이 정도는 보여준다.
const MIN_ANALYZING_MS = 3000;

export function useAnalyze() {
  const { user } = useAuthContext();
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const prevUrl = useRef<string | null>(null);
  const [captureState, setCaptureState] = useState<CaptureState>("capture");
  const [completedSteps, setCompletedSteps] = useState<number[]>([]);
  const [currentStep, setCurrentStep] = useState(-1);
  const [result, setResult] = useState<ClassificationResult | null>(null);

  const navigate = useNavigate();

  // 실제 백엔드 연동 — AuthScreen/MyPageScreen과 동일하게 useAxios(hooks/useAxios.tsx)로 호출한다.
  const { refetch: analyzeRequest } = useAxios<AnalyzeApiResponse>(
    "",
    { method: "post" },
    false,
  );

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

      // /analyze 응답에 이미 RAG 서비스(node2)가 채운 national_rule/region_rule이
      // 실려 있으므로, 별도로 /disposal/schedule을 다시 호출하지 않고 바로 사용한다.
      const guidelines = buildGuidelineFromAnalyze(data);

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

  function onViewGuidelines(r: ClassificationResult, imageUrl: string) {
    navigate("/result", { state: { result: r, imageUrl } });
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

  return {
    user,
    selectedFile,
    setSelectedFile,
    runRealAnalyze,
    buildFailResult,
    handleFileSelected,
    handleAnalyze,
    previewUrl,
    setPreviewWithCleanup,
    captureState,
    completedSteps,
    currentStep,
    setCaptureState,
    setCompletedSteps,
    setCurrentStep,
    result,
    setResult,
    handleReset,
  };
}
