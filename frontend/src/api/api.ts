// 촬영 → 분석 진행 상태 UI(AnalyzingView)에서 쓰는 5단계 라벨.
// 실제 분석/인증/지역 API 연동은 각 화면에서 hooks/useAxios + api/analyze.ts로 처리한다
// (로그인: AuthScreen, 지역: RegionScreen, 분석: PhotoCaptureScreen — 모두 이 파일을 쓰지 않음).
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
