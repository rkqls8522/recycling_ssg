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
}

export interface DisposalGuideline {
  steps: string[];
  notes: string[];
  collectionDays: string;
  specialInstructions?: string;
  source: string;
  sourceUrl: string;
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
  region: string | null; // Region 타입이 별도로 있다면 그걸로 교체
  created_at: string;
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
      created_at: Date;
    },
  ];
}
