// 공통 API 설정 — api.ts, analyze.ts 등에서 공유
// TODO: 실제 백엔드 배포 시 VITE_API_URL 환경변수(.env) 또는 vite.config.ts server.proxy 설정 필요
export const API_BASE = import.meta.env.VITE_API_URL ?? "";

// 백엔드 URL이 설정되지 않은 경우 mock 모드로 동작
export const MOCK_MODE = !API_BASE;
