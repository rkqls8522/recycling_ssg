import { v4 as uuidv4 } from "uuid";
import type {
  AnalyzeSuccessBody,
  ClassificationResult,
  ConfidenceLevel,
  DisposalGuideline,
  DisposalScheduleResponse,
  FailureHint,
} from "../types";
import { getToken } from "../utils/storage";
import { getRandomWasteItem, getGuidelineForRegion } from "./mockData";

export { MOCK_MODE } from "./config";

console.log(getToken());
export function authHeaders(): Record<string, string> {
  const token = getToken();

  return {
    Accept: "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    "X-Request-ID": uuidv4(),
  };
}

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

// GET /api/v1/disposal/schedule 응답 → 화면에서 쓰는 DisposalGuideline으로 변환
// (백엔드는 steps/notes 같은 세부 목록을 주지 않고 disposal_method 한 줄만 주므로, 그 한 줄을 첫 스텝으로 사용)
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
  const top1 = data.candidate_scores[0];
  return {
    itemName: data.minor_category,
    itemCategory: data.major_category,
    itemCategoryEn: top1 ? String(top1.class_id) : "unknown",
    confidence: top1 ? Math.round(top1.score * 100) : 100,
    confidenceLevel: "high",
    guidelines,
    regionCode,
    regionName: `${data.user_region.sido_name} ${data.user_region.sgg_name}`,
    feedbackId: data.feedback_id,
    classId: top1?.class_id,
    candidateScores: data.candidate_scores,
  };
}

// mock 모드 전용 — 실제 네트워크 요청 없이 5단계 파이프라인을 흉내낸다.
export async function runMockAnalyze(
  regionCode: string,
  regionName: string,
  onProgress?: (stepIndex: number) => void,
): Promise<AnalyzeOutcome> {
  for (let i = 0; i < 5; i++) {
    await delay(2000);
    onProgress?.(i);
  }
  const item = getRandomWasteItem();
  const guidelines = getGuidelineForRegion(item, regionCode);
  const roll = Math.random();
  let confidence: number;
  let confidenceLevel: ConfidenceLevel;
  let failureHint: FailureHint | undefined;

  if (roll < 0.6) {
    confidence = Math.min(
      98,
      item.baseConfidence + 3 + Math.floor(Math.random() * 8),
    );
    confidenceLevel = "high";
  } else if (roll < 0.85) {
    confidence = 60 + Math.floor(Math.random() * 22);
    confidenceLevel = "uncertain";
  } else {
    confidence = 20 + Math.floor(Math.random() * 38);
    confidenceLevel = "low";
    const hints: FailureHint[] = [
      "blurry",
      "dark",
      "multiple_objects",
      "unclear",
      "unknown",
    ];
    failureHint = hints[Math.floor(Math.random() * hints.length)];
  }

  if (confidenceLevel === "low") {
    return {
      status: "RETAKE_REQUIRED",
      retakeMessage: "객체를 정확히 판단하기 어렵습니다. 다시 촬영해주세요.",
    };
  }

  return {
    status: "SUCCESS",
    result: {
      itemName: item.itemName,
      itemCategory: item.itemCategory,
      itemCategoryEn: item.itemCategoryEn,
      confidence,
      confidenceLevel,
      failureHint,
      guidelines,
      regionCode,
      regionName,
    },
  };
}

// 실제 요청은 단일 요청/응답이라 진짜 진행률을 알 수 없다.
// 응답을 기다리는 동안 capStep까지만 일정 간격으로 진행 표시를 채우고,
// 응답이 오면 finish()로 남은 단계(기본 4까지)를 한번에 채운다.
export function startProgressTicker(
  onProgress?: (stepIndex: number) => void,
  capStep = 3,
  intervalMs = 900,
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

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
