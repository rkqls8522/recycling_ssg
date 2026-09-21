import type { Dispatch, SetStateAction } from "react";
import { useNavigate } from "react-router-dom";
import useAxios from "@/hooks/useAxios";
import type {
  ClassificationResult,
  DisposalScheduleResponse,
  FeedbackConfirmResponse,
  FeedbackNotInListResponse,
  FeedbackSelectCandidateResponse,
} from "@/types";
import { authHeaders } from "@/utils/header";
import {
  FALLBACK_GUIDELINE,
  buildGuidelineFromAnalyze,
  mapDisposalSchedule,
} from "../PhotoCaptureScreen/useAnalyze";

// result/픽커/에이전트 화면 상태는 useResult가 소유한다 — 이 훅은 그 상태를 받아서
// 피드백 관련 API 호출(확정/후보 선택/재분류)만 담당한다.
export function useFeedback(
  result: ClassificationResult,
  setResult: Dispatch<SetStateAction<ClassificationResult>>,
  setPickerOpen: Dispatch<SetStateAction<boolean>>,
  setFeedbackBusy: Dispatch<SetStateAction<boolean>>,
  setFeedbackError: Dispatch<SetStateAction<string>>,
  setAgentThinkingOpen: Dispatch<SetStateAction<boolean>>,
) {
  const navigate = useNavigate();

  const { refetch: disposalRequest } = useAxios<DisposalScheduleResponse>(
    "",
    { method: "get" },
    false,
  );

  // 1. Yolo 분류 결과를 그대로 확정 — "맞아요"
  const { refetch: yoloFeedbackRequest } = useAxios<FeedbackConfirmResponse>(
    "",
    { method: "post" },
    false,
  );

  async function handleYoloFeedback(feedback_id: number) {
    if (!feedback_id) return;

    try {
      await yoloFeedbackRequest({
        url: `/api/v1/feedback/${feedback_id}/confirm`,
        headers: authHeaders(),
      });
    } catch (e) {
      console.error("yolo 분류 결과 피드백 요청 실패", e);
    }
    navigate("/home");
  }

  // 2. 후보 목록 중 다른 품목 선택
  const { refetch: candidateFeedback } =
    useAxios<FeedbackSelectCandidateResponse>("", { method: "post" }, false);

  async function handleCandidateFeedback(class_id: number) {
    if (!result.feedbackId) return;

    const candidate = result.candidateScores?.find(
      (c) => c.class_id === class_id,
    );

    // 원래 1순위 후보를 다시 고른 경우 — 백엔드가 select-candidate에서
    // FEEDBACK_SAME_AS_PREDICTION을 반환하므로 confirm으로 처리한다.
    if (class_id === result.classId) {
      setPickerOpen(false);
      await handleYoloFeedback(result.feedbackId);
      return;
    }

    setFeedbackBusy(true);
    setFeedbackError("");
    try {
      await candidateFeedback({
        url: `/api/v1/feedback/${result.feedbackId}/select-candidate`,
        data: { class_id },
        headers: authHeaders(),
      });
      const [major, minor] = (candidate?.category ?? "").split("_");
      let gl = FALLBACK_GUIDELINE;
      try {
        const schedule = await disposalRequest({
          url: "/api/v1/disposal/schedule",
          params: { class_id },
          headers: authHeaders(),
        });
        gl = mapDisposalSchedule(schedule);
      } catch {
        // 배출정보 조회가 실패해도 품목 수정 자체는 반영한다
      }
      setResult((prev) => ({
        ...prev,
        itemName: minor ?? candidate?.category ?? prev.itemName,
        itemCategory: major ?? prev.itemCategory,
        classId: class_id,
        confidenceLevel: "high",
        guidelines: gl,
      }));
      setPickerOpen(false);
    } catch {
      setFeedbackError("품목 수정 중 오류가 발생했습니다. 다시 시도해주세요.");
    } finally {
      setFeedbackBusy(false);
    }
  }

  // 3. 목록에 없음 → LLM 재분류로 escalate
  const { refetch: notInListRequest } = useAxios<FeedbackNotInListResponse>(
    "",
    { method: "post" },
    false,
  );

  async function handleNotListed() {
    setPickerOpen(false);
    setFeedbackError("");
    setAgentThinkingOpen(true);

    if (!result.feedbackId) return;

    try {
      const res = await notInListRequest({
        url: `/api/v1/feedback/${result.feedbackId}/not-in-list`,
        headers: authHeaders(),
      });
      // /not-in-list 응답에 이미 RAG 서비스가 채운 national_rule/region_rule이
      // 실려 있으므로, /analyze와 동일하게 바로 사용한다 (/disposal/schedule
      // 재조회 X — 그건 행정안전부 공공데이터라 RAG 지식베이스와 내용이 다르다).
      const gl = buildGuidelineFromAnalyze(res as unknown as Parameters<typeof buildGuidelineFromAnalyze>[0]);
      setResult((prev) => ({
        ...prev,
        itemName: res.minor_category,
        itemCategory: res.major_category,
        classId: res.final_class_id,
        confidenceLevel: "high",
        guidelines: gl,
      }));
      setAgentThinkingOpen(false);
    } catch {
      setFeedbackError("추가 분석에 실패했습니다. 다시 시도해주세요.");
      setAgentThinkingOpen(false);
    }
  }

  return { handleYoloFeedback, handleCandidateFeedback, handleNotListed };
}
