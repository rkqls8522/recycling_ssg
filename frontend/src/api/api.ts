import type { ClassificationResult, ConfidenceLevel, FailureHint } from "../types"
import { getToken, saveToken, saveUser, getUser } from "../utils/storage"
import { getRandomWasteItem, getGuidelineForRegion } from "./mockData"

// TODO: Replace with actual Spring backend URL
const API_BASE = import.meta.env.VITE_API_URL ?? ""

// Mock mode when no backend URL is configured
const MOCK_MODE = !API_BASE

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const token = getToken()
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options?.headers,
    },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ message: "요청에 실패했습니다" }))
    throw new Error(err.message ?? "요청에 실패했습니다")
  }
  return res.json()
}

// ─── Auth ────────────────────────────────────────────────────────────────────

interface AuthPayload {
  email: string
  password: string
}

interface AuthResponse {
  token: string
  user: { id: string; email: string; regionCode?: string; regionName?: string }
}

export async function signup(payload: AuthPayload): Promise<AuthResponse> {
  if (MOCK_MODE) {
    await delay(800)
    const mockRes: AuthResponse = {
      token: `mock-jwt-${Date.now()}`,
      user: { id: `user-${Date.now()}`, email: payload.email },
    }
    saveToken(mockRes.token)
    saveUser(mockRes.user)
    return mockRes
  }
  // POST /auth/signup
  const res = await request<AuthResponse>("/auth/signup", {
    method: "POST",
    body: JSON.stringify(payload),
  })
  saveToken(res.token)
  saveUser(res.user)
  return res
}

export async function login(payload: AuthPayload): Promise<AuthResponse> {
  if (MOCK_MODE) {
    await delay(800)
    const saved = getUser()
    const mockRes: AuthResponse = {
      token: `mock-jwt-${Date.now()}`,
      user: saved ?? { id: `user-${Date.now()}`, email: payload.email },
    }
    saveToken(mockRes.token)
    saveUser(mockRes.user)
    return mockRes
  }
  // POST /auth/login
  const res = await request<AuthResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  })
  saveToken(res.token)
  saveUser(res.user)
  return res
}

// ─── Region ──────────────────────────────────────────────────────────────────

interface RegionPayload {
  regionCode: string
  regionName: string
}

export async function getUserRegion(): Promise<RegionPayload | null> {
  if (MOCK_MODE) {
    const user = getUser()
    if (user?.regionCode) return { regionCode: user.regionCode, regionName: user.regionName ?? "" }
    return null
  }
  // GET /user/region
  return request<RegionPayload>("/user/region")
}

export async function updateUserRegion(payload: RegionPayload): Promise<void> {
  if (MOCK_MODE) {
    await delay(400)
    const user = getUser()
    if (user) {
      saveUser({ ...user, regionCode: payload.regionCode, regionName: payload.regionName })
    }
    return
  }
  // PUT /user/region
  await request<void>("/user/region", { method: "PUT", body: JSON.stringify(payload) })
}

// ─── Classification ───────────────────────────────────────────────────────────

export interface ClassifyProgressStep {
  label: string
  done: boolean
}

export const CLASSIFY_STEPS: ClassifyProgressStep[] = [
  { label: "이미지 전처리 중", done: false },
  { label: "객체 탐지 중", done: false },
  { label: "품목 분류 중", done: false },
  { label: "지침 검색 중", done: false },
  { label: "안내문 생성 중", done: false },
]

export async function classifyImage(
  imageFile: File,
  regionCode: string,
  regionName: string,
  onProgress?: (stepIndex: number) => void,
): Promise<ClassificationResult> {
  if (MOCK_MODE) {
    // Simulate the 5-stage pipeline with staged delays
    for (let i = 0; i < 5; i++) {
      await delay(i === 4 ? 2000 : 2000)
      onProgress?.(i)
    }
    const item = getRandomWasteItem()
    const guidelines = getGuidelineForRegion(item, regionCode)

    // 3-way confidence distribution: 60% high / 25% uncertain / 15% fail
    const roll = Math.random()
    let confidence: number
    let confidenceLevel: ConfidenceLevel
    let failureHint: FailureHint | undefined

    if (roll < 0.60) {
      // High confidence: 85–98%
      const jitter = Math.floor(Math.random() * 8)
      confidence = Math.min(98, item.baseConfidence + 3 + jitter)
      confidenceLevel = "high"
    } else if (roll < 0.85) {
      // Uncertain: 60–81%
      confidence = 60 + Math.floor(Math.random() * 22)
      confidenceLevel = "uncertain"
    } else {
      // Low / fail: 20–57%
      confidence = 20 + Math.floor(Math.random() * 38)
      confidenceLevel = "low"
      const hints: FailureHint[] = ["blurry", "dark", "multiple_objects", "unclear", "unknown"]
      failureHint = hints[Math.floor(Math.random() * hints.length)]
    }

    return {
      itemName: item.itemName,
      itemCategory: item.itemCategory,
      itemCategoryEn: item.itemCategoryEn,
      confidence,
      confidenceLevel,
      failureHint,
      guidelines,
      regionCode,
      regionName,
    }
  }

  // POST /classify — multipart/form-data
  const form = new FormData()
  form.append("image", imageFile)
  form.append("regionCode", regionCode)

  const token = getToken()
  const res = await fetch(`${API_BASE}/classify`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ message: "분류에 실패했습니다" }))
    throw new Error(err.message ?? "분류에 실패했습니다")
  }
  return res.json()
}

// ─── Util ─────────────────────────────────────────────────────────────────────

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}
