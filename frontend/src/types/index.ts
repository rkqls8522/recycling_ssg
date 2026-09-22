export interface User {
  id: string;
  email: string;
  regionCode?: string;
  regionName?: string;
}

export interface District {
  code: string;
  name: string;
}

export interface Province {
  code: string;
  name: string;
  districts: District[];
}

export type FailureHint =
  | "blurry"
  | "dark"
  | "multiple_objects"
  | "unclear"
  | "unknown";

export type ConfidenceLevel = "high" | "uncertain" | "low";

export interface ClassificationResult {
  itemName: string;
  itemCategory: string;
  itemCategoryEn: string;
  confidence: number;
  confidenceLevel: ConfidenceLevel;
  failureHint?: FailureHint;
  guidelines: DisposalGuideline;
  regionCode: string;
  regionName: string;
  // 실제 백엔드(/api/v1/analyze) 연동 시에만 채워지는 필드 —
  // mock 플로우(buildMockResult 등)에서는 undefined로 유지되어 기존 동작을 그대로 보존한다.
  feedbackId?: number;
  classId?: number;
  candidateScores?: CandidateScore[];
}

export interface DisposalGuideline {
  steps: string[];
  notes: string[];
  collectionDays: string;
  specialInstructions?: string;
  source: string;
  sourceUrl: string;
  // RAG(node2) 결과를 "전국 공통 기준" / "지자체 추가 안내"로 나눠 보여주기 위한 구조화 필드.
  // /analyze(RAG 연동) 흐름에서만 채워짐 — mock이나 /disposal/schedule 폴백 흐름에서는 null/undefined.
  nationalRule?: { source: string; method: string } | null;
  regionRule?: {
    region: string;
    method: string;
    sourceLabel: string;
    sourceUrl: string;
  } | null;
}

export type Screen = "auth" | "region" | "home" | "classifying" | "result";

export type AuthMode = "login" | "signup";

export type CaptureState =
  | "capture"
  | "analyzing"
  | "agent_thinking"
  | "success"
  | "uncertain"
  | "fail";

export interface SignupPayload {
  email: string;
  password: string;
}

export interface SignupResponse {
  user_id: number;
  email: string;
  region: RegionInfo | null;
  created_at: string;
}
export interface UserResponse {
  user_id: number;
  email: string;
  region: RegionInfo | null;
  created_at: string;
  updated_at: string;
}

// POST /api/v1/auth/login 응답 — signup과 달리 access_token을 함께 내려준다.
export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: UserResponse;
}

export interface ApiErrorBody {
  success: false;
  code: string; // "AUTH_EMAIL_EXISTS" | "REQUEST_VALIDATION_ERROR" | "DATABASE_ERROR" | "INTERNAL_SERVER_ERROR" 등
  message: string;
  details: { field: string; message: string }[] | null;
  request_id: string;
}

export interface FavoriteResponse {
  items: [
    {
      favorite_id: number;
      class_id: number;
      major_category: string;
      minor_category: string;
      message: string;
    },
  ];
}

// ─── /api/v1/analyze, /api/v1/feedback/*, /api/v1/disposal/schedule ───────────
// Notion "프론트 - 백 api" 명세서 기준 (2026-09-14 정리)

export interface RegionInfo {
  region_id: number;
  sido_name: string;
  sgg_name: string;
}

export interface CandidateScore {
  class_id: number;
  category: string; // 예: "플라스틱류_욕실용품" (major_minor)
  score: number;
}

export interface NationalRule {
  source: string;
  method: string | null;
}

export interface RegionRule {
  region: string;
  source_url: string;
  exception_type: string;
  method: string;
}

export interface AnalyzeSuccessBody {
  status: "SUCCESS";
  major_category: string;
  minor_category: string;
  // Top-1(실제 예측) class_id/score. major_category/minor_category와 같은 대상.
  class_id: number;
  score: number;
  // Top-1을 제외한 "다른 후보" 목록 (모델이 틀렸을 때 사용자에게 보여줄 대안).
  candidate_scores: CandidateScore[];
  user_region: RegionInfo;
  disposal_day: string | null;
  national_rule: NationalRule | null;
  region_rule: RegionRule | null;
  image_id: number;
  feedback_id: number;
  warnings: string[];
}

export interface AnalyzeRetakeBody {
  status: "RETAKE_REQUIRED";
  code: string;
  message: string;
  threshold?: number;
  // AI_LOW_CONFIDENCE일 때 실제 Top-1 신뢰도 점수 (threshold 미만이라 재촬영을
  // 요구한 바로 그 값). AI_NO_MAIN_OBJECT는 null.
  score?: number | null;
  // AI_LOW_CONFIDENCE일 때 모델이 (확신은 낮지만) 예측한 대상. 셋이 함께 채워지거나
  // 함께 null이다. AI_NO_MAIN_OBJECT는 예측 자체가 없으므로 전부 null.
  class_id?: number | null;
  major_category?: string | null;
  minor_category?: string | null;
  // AI_LOW_CONFIDENCE는 SUCCESS와 동일하게 저장되므로 그 행의 feedback_id.
  // AI_NO_MAIN_OBJECT는 저장된 행이 없으므로 null.
  feedback_id?: number | null;
  request_id: string;
}

export type AnalyzeApiResponse = AnalyzeSuccessBody | AnalyzeRetakeBody;

export interface DisposalScheduleResponse {
  class_id: number;
  major_category: string;
  minor_category: string;
  region: RegionInfo;
  disposal_day: string | null;
  start_time: string | null;
  end_time: string | null;
  disposal_method: string | null;
  source: string;
}

export interface FeedbackConfirmResponse {
  feedback_id: number;
  is_correct: true;
  final_class_id: number;
  correction_source: null;
  message: string;
}

export interface FeedbackSelectCandidateResponse {
  feedback_id: number;
  is_correct: false;
  final_class_id: number;
  correction_source: "USER";
  message: string;
}

export interface FeedbackNotInListResponse {
  feedback_id: number;
  is_correct: false;
  final_class_id: number;
  correction_source: "GEMINI";
  major_category: string;
  minor_category: string;
  disposal_day: string | null;
  national_rule: NationalRule | null;
  region_rule: RegionRule | null;
  message: string;
}

export type RegionItem = {
  region_id: number;
  sido_name: string;
  sgg_name: string;
};

export type GetRegionResponse = {
  items: RegionItem[];
};

export type Region = {
  region_id: number;
  sido_name: string;
  sgg_name: string;
};

export type UserRegionResponse = {
  user_id: number;
  region: Region;
};
