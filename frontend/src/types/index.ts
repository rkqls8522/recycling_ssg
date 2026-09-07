export interface User {
  id: string
  email: string
  regionCode?: string
  regionName?: string
}

export interface District {
  code: string
  name: string
}

export interface Province {
  code: string
  name: string
  districts: District[]
}

export type FailureHint =
  | "blurry"
  | "dark"
  | "multiple_objects"
  | "unclear"
  | "unknown"

export type ConfidenceLevel = "high" | "uncertain" | "low"

export interface ClassificationResult {
  itemName: string
  itemCategory: string
  itemCategoryEn: string
  confidence: number
  confidenceLevel: ConfidenceLevel
  failureHint?: FailureHint
  guidelines: DisposalGuideline
  regionCode: string
  regionName: string
}

export interface DisposalGuideline {
  steps: string[]
  notes: string[]
  collectionDays: string
  specialInstructions?: string
  source: string
  sourceUrl: string
}

export type Screen = "auth" | "region" | "home" | "classifying" | "result"

export type AuthMode = "login" | "signup"

export type CaptureState =
  | "capture"
  | "analyzing"
  | "agent_thinking"
  | "success"
  | "uncertain"
  | "fail"
