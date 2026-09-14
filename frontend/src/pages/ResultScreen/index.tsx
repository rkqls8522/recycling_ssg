import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import type {
  CandidateScore,
  ClassificationResult,
  DisposalScheduleResponse,
  FeedbackConfirmResponse,
  FeedbackNotInListResponse,
  FeedbackSelectCandidateResponse,
} from "../../types";
import {
  authHeaders,
  FALLBACK_GUIDELINE,
  mapDisposalSchedule,
} from "../../api/analyze";
import useAxios from "../../hooks/useAxios";
import ChatDrawer from "./ChatDrawer";
import BackButton from "../../components/common/BackButton";
import { MoveToSourceIcon } from "@/components/common/Icons";
import AgentThinkingView from "../PhotoCaptureScreen/AgentThinkingView";

interface ResultLocationState {
  result: ClassificationResult;
  imageUrl: string;
}

// location.state 없이(예: 새로고침, 직접 URL 진입) 이 화면에 들어온 순간에만 잠깐 쓰이는 빈 값 —
// 실제 분석 데이터가 아니며, 아래 useEffect가 즉시 /capture로 돌려보낸다.
const EMPTY_RESULT: ClassificationResult = {
  itemName: "",
  itemCategory: "",
  itemCategoryEn: "",
  confidence: 0,
  confidenceLevel: "low",
  guidelines: {
    steps: [],
    notes: [],
    collectionDays: "",
    source: "",
    sourceUrl: "",
  },
  regionCode: "",
  regionName: "",
};

const CATEGORY_COLOR: Record<string, string> = {
  플라스틱류: "bg-blue-100 text-blue-700",
  유리류: "bg-cyan-100 text-cyan-700",
  금속류: "bg-slate-100 text-slate-700",
  "종이류 (종이팩)": "bg-yellow-100 text-yellow-700",
  스티로폼류: "bg-orange-100 text-orange-700",
};

export default function ResultScreen() {
  const location = useLocation();
  const navigate = useNavigate();
  const [chatOpen, setChatOpen] = useState(false);
  const state = location.state as ResultLocationState | null;

  const [result, setResult] = useState<ClassificationResult>(EMPTY_RESULT);
  const [imageUrl, setImageUrl] = useState("");
  const [pickerOpen, setPickerOpen] = useState(false);
  const [agentThinkingOpen, setAgentThinkingOpen] = useState(false);
  const [feedbackBusy, setFeedbackBusy] = useState(false);
  const [feedbackError, setFeedbackError] = useState("");
  const { itemName, guidelines, regionName } = result;

  // 실제 백엔드 연동 — PhotoCaptureScreen과 동일하게 useAxios(hooks/useAxios.tsx)로 호출한다.
  const { refetch: confirmRequest } = useAxios<FeedbackConfirmResponse>(
    "",
    { method: "post" },
    false,
  );
  const { refetch: selectCandidateRequest } =
    useAxios<FeedbackSelectCandidateResponse>("", { method: "post" }, false);
  const { refetch: notInListRequest } = useAxios<FeedbackNotInListResponse>(
    "",
    { method: "post" },
    false,
  );
  const { refetch: disposalRequest } = useAxios<DisposalScheduleResponse>(
    "",
    { method: "get" },
    false,
  );

  useEffect(() => {
    if (state?.result) {
      setResult(state.result);
      setImageUrl(state.imageUrl);
    } else {
      navigate("/capture", { replace: true });
    }
  }, [state, navigate]);

  if (!state) return null;

  function onBack() {
    navigate("/capture");
  }

  function handlePickerOpen() {
    setChatOpen(false);
    setFeedbackError("");
    setPickerOpen(true);
  }

  // /analyze가 준 candidate_scores 중 다른 후보를 선택
  // (predicted_class_id와 같은 후보를 다시 고르면 백엔드가 FEEDBACK_SAME_AS_PREDICTION을 반환하므로 confirm으로 처리)
  async function handlePickCandidate(candidate: CandidateScore) {
    if (!result.feedbackId) return;

    if (candidate.class_id === result.classId) {
      setPickerOpen(false);
      await handleConfirmCorrect();
      return;
    }

    setFeedbackBusy(true);
    setFeedbackError("");
    try {
      await selectCandidateRequest({
        url: `/api/v1/feedback/${result.feedbackId}/select-candidate`,
        data: { class_id: candidate.class_id },
        headers: authHeaders(),
      });
      const [major, minor] = candidate.category.split("_");
      let gl = FALLBACK_GUIDELINE;
      try {
        const schedule = await disposalRequest({
          url: "/api/v1/disposal/schedule",
          params: { class_id: candidate.class_id },
          headers: authHeaders(),
        });
        gl = mapDisposalSchedule(schedule);
      } catch {
        // 배출정보 조회가 실패해도 품목 수정 자체는 반영한다
      }
      setResult({
        ...result,
        itemName: minor ?? candidate.category,
        itemCategory: major ?? candidate.category,
        classId: candidate.class_id,
        confidenceLevel: "high",
        guidelines: gl,
      });
      setPickerOpen(false);
    } catch {
      setFeedbackError("품목 수정 중 오류가 발생했습니다. 다시 시도해주세요.");
    } finally {
      setFeedbackBusy(false);
    }
  }

  function handleRetake() {
    handlePickerOpen();
  }

  // "맞아요" — 최초 예측이 맞다고 서버에 확정(confirm)한 뒤 이동
  async function handleConfirmCorrect() {
    if (result.feedbackId) {
      try {
        await confirmRequest({
          url: `/api/v1/feedback/${result.feedbackId}/confirm`,
          headers: authHeaders(),
        });
      } catch {
        // 피드백 저장 실패는 조용히 무시 — 사용자 플로우(뒤로가기)는 막지 않는다
      }
    }
    onBack();
  }

  // "여기 없어요" → escalate to the LLM agent for a deeper look
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
      let gl = FALLBACK_GUIDELINE;
      try {
        const schedule = await disposalRequest({
          url: "/api/v1/disposal/schedule",
          params: { class_id: res.final_class_id },
          headers: authHeaders(),
        });
        gl = mapDisposalSchedule(schedule);
      } catch {
        // 배출정보 조회가 실패해도 재분류 결과 자체는 반영한다
      }
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

  if (agentThinkingOpen) {
    return <AgentThinkingView onBack={() => setAgentThinkingOpen(false)} />;
  }

  return (
    <div className="flex flex-col h-full bg-background">
      {/* Header */}
      <div className="bg-primary text-primary-foreground px-5 pt-12 pb-4 flex items-center gap-3">
        <BackButton onClick={onBack} ariaLabel="뒤로 가기" />
        <div className="flex-1">
          <h2 className="text-base font-bold">분석 결과</h2>
          <p className="text-xs opacity-70">{regionName} 기준</p>
        </div>
        <div className="w-10 h-10 rounded-xl overflow-hidden border-2 border-primary-foreground/30">
          <img
            src={imageUrl}
            alt="분석된 폐기물 사진"
            className="w-full h-full object-cover"
          />
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto no-scrollbar px-5 pt-5 pb-6 flex flex-col gap-4">
        {/* Recognition Card — item + collection days */}
        <div className="bg-card rounded-2xl border border-border p-5 flex items-center justify-between gap-4">
          <div>
            <p className="text-xs text-muted-foreground mb-1">인식된 품목</p>
            <h3 className="text-2xl font-bold text-foreground">{itemName}</h3>
          </div>
          <div className="flex-shrink-0 flex flex-col items-end gap-1">
            <p className="text-[10px] text-muted-foreground">수거 요일</p>
            <p className="text-sm font-semibold text-primary text-right">
              {guidelines.collectionDays}
            </p>
          </div>
        </div>

        {/* Guidelines Card */}
        <div className="bg-card rounded-2xl border border-border overflow-hidden">
          <div className="px-5 pt-5 pb-4 border-b border-border">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-widest">
              배출 방법
            </p>
            <h4 className="text-base font-bold text-foreground mt-1">
              {itemName} 분리배출 안내
            </h4>
          </div>

          {/* Steps */}
          <div className="px-5 py-4 flex flex-col gap-0">
            {guidelines.steps.map((step, i) => (
              <div key={i} className="flex gap-3 relative pb-4">
                {i < guidelines.steps.length - 1 && (
                  <div className="absolute left-[15px] top-7 bottom-0 w-px bg-border" />
                )}
                <div className="w-7 h-7 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0 z-10">
                  <span className="text-xs font-bold font-mono text-primary">
                    {i + 1}
                  </span>
                </div>
                <p className="text-sm text-foreground leading-relaxed pt-1">
                  {step}
                </p>
              </div>
            ))}
          </div>

          {/* Notes */}
          {guidelines.notes.length > 0 && (
            <div className="px-5 pb-5">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2.5">
                주의사항
              </p>
              <div className="flex flex-col gap-2">
                {guidelines.notes.map((note, i) => (
                  <div key={i} className="flex items-start gap-2">
                    <span className="text-amber-500 text-xs mt-0.5 flex-shrink-0 font-bold">
                      !
                    </span>
                    <p className="text-xs text-muted-foreground leading-relaxed">
                      {note}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Special instructions */}
          {guidelines.specialInstructions && (
            <div className="mx-5 mb-5 px-4 py-3 bg-blue-50 rounded-xl border border-blue-100">
              <p className="text-xs text-blue-800 leading-relaxed">
                {guidelines.specialInstructions}
              </p>
            </div>
          )}
        </div>

        {/* Source — whole box is the link */}
        <a
          href={guidelines.sourceUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center justify-between px-4 py-3.5 bg-muted rounded-xl active:bg-border transition-colors"
          aria-label={`${guidelines.source} 원문 보기`}
        >
          <div className="min-w-0">
            <p className="text-xs text-muted-foreground">
              출처 — 탭하면 원문으로 이동
            </p>
            <p className="text-xs font-medium text-foreground truncate mt-0.5">
              {guidelines.source}
            </p>
          </div>
          <MoveToSourceIcon />
        </a>
      </div>

      {/* Bottom CTA */}
      <div className="px-5 pb-8 pt-3 flex flex-col gap-3">
        <p className="text-sm font-semibold text-foreground text-center">
          인식된 품목이 맞습니까?
        </p>
        {feedbackError && !pickerOpen && (
          <p className="text-xs text-destructive text-center">
            {feedbackError}
          </p>
        )}
        <div className="flex gap-2.5">
          <button
            onClick={handleRetake}
            className="flex-1 py-3.5 rounded-2xl border border-border bg-card text-sm font-semibold text-foreground active:bg-muted transition-all"
          >
            다시 촬영
          </button>
          <button
            onClick={handleConfirmCorrect}
            className="flex-1 py-3.5 rounded-2xl bg-primary text-primary-foreground font-semibold text-sm active:scale-[0.98] transition-all shadow-md shadow-primary/20"
          >
            맞아요
          </button>
        </div>
      </div>

      {/* Floating chat character */}
      {!chatOpen && !pickerOpen && (
        <button
          onClick={() => setChatOpen(true)}
          className="absolute bottom-28 right-5 flex flex-col items-center gap-1 animate-float-bob active:scale-90 transition-transform"
          aria-label="AI 상담 열기"
        >
          <div className="bg-white border border-border rounded-2xl rounded-br-sm px-3 py-1.5 shadow-md">
            <p className="text-[11px] font-semibold text-foreground whitespace-nowrap">
              궁금해요!
            </p>
          </div>
          <div className="relative">
            <svg
              width="64"
              height="64"
              viewBox="0 0 64 64"
              fill="none"
              aria-hidden="true"
            >
              <ellipse
                cx="32"
                cy="61"
                rx="14"
                ry="3"
                fill="black"
                fillOpacity="0.08"
              />
              <circle cx="32" cy="30" r="26" fill="#1b5c35" />
              <ellipse
                cx="24"
                cy="20"
                rx="7"
                ry="5"
                fill="white"
                fillOpacity="0.15"
                transform="rotate(-20 24 20)"
              />
              <circle cx="24" cy="27" r="4" fill="white" />
              <circle cx="40" cy="27" r="4" fill="white" />
              <circle cx="25" cy="28" r="2" fill="#0f3d22" />
              <circle cx="41" cy="28" r="2" fill="#0f3d22" />
              <circle cx="26" cy="27" r="0.8" fill="white" />
              <circle cx="42" cy="27" r="0.8" fill="white" />
              <path
                d="M24 36 Q32 43 40 36"
                stroke="white"
                strokeWidth="2.5"
                strokeLinecap="round"
                fill="none"
              />
              <g opacity="0.5" transform="translate(27,39) scale(0.42)">
                <path
                  d="M12 4l-4 4h3c0 5.52 4.48 10 10 10 1.57 0 3.04-.38 4.34-1.03l-1.46-1.46C23 15.68 22.04 16 21 16c-3.87 0-7-3.13-7-7h3l-4-4zM21 4c-1.57 0-3.04.38-4.34 1.03l1.46 1.46C19 6.32 19.96 6 21 6c3.87 0 7 3.13 7 7h-3l4 4 4-4h-3C30 8.48 25.52 4 21 4z"
                  fill="white"
                />
              </g>
              <line
                x1="32"
                y1="4"
                x2="32"
                y2="10"
                stroke="#1b5c35"
                strokeWidth="2.5"
                strokeLinecap="round"
              />
              <circle cx="32" cy="3" r="3" fill="#4ade80" />
            </svg>
          </div>
        </button>
      )}

      <ChatDrawer
        result={result}
        open={chatOpen}
        onClose={() => setChatOpen(false)}
      />

      {/* Item picker bottom sheet */}
      {pickerOpen && (
        <>
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/40 z-20"
            onClick={() => setPickerOpen(false)}
          />

          {/* Sheet */}
          <div className="absolute bottom-0 left-0 right-0 z-30 bg-background rounded-t-3xl shadow-2xl animate-fade-in-up">
            {/* Handle */}
            <div className="flex justify-center pt-3 pb-1">
              <div className="w-10 h-1 rounded-full bg-border" />
            </div>

            {/* Header */}
            <div className="px-5 pt-3 pb-4 border-b border-border">
              <p className="text-base font-bold text-foreground">
                어떤 품목인가요?
              </p>
              <p className="text-xs text-muted-foreground mt-0.5">
                목록에서 선택하면 해당 배출 방법을 알려드립니다
              </p>
            </div>

            {/* Items list — top candidates */}
            <div className="px-5 pt-3 pb-2 flex flex-col gap-1">
              {feedbackError && (
                <p className="text-xs text-destructive px-1 pb-1">
                  {feedbackError}
                </p>
              )}
              {(result.candidateScores ?? []).map((candidate) => {
                const [major, minor] = candidate.category.split("_");
                const color =
                  CATEGORY_COLOR[major] ?? "bg-muted text-muted-foreground";
                return (
                  <button
                    key={candidate.class_id}
                    onClick={() => handlePickCandidate(candidate)}
                    disabled={feedbackBusy}
                    className="w-full flex items-center gap-3 px-4 py-3 rounded-xl active:bg-muted transition-colors text-left disabled:opacity-50"
                  >
                    <span
                      className={`text-[10px] font-semibold px-2 py-0.5 rounded-full flex-shrink-0 ${color}`}
                    >
                      {major}
                    </span>
                    <p className="text-sm font-medium text-foreground flex-1">
                      {minor ?? candidate.category}
                    </p>
                    <span className="text-[10px] text-muted-foreground flex-shrink-0">
                      {Math.round(candidate.score * 100)}%
                    </span>
                  </button>
                );
              })}

              {/* 여기 없어요 */}
              <button
                onClick={handleNotListed}
                disabled={feedbackBusy}
                className="w-full flex items-center gap-3 px-4 py-3 rounded-xl active:bg-muted transition-colors text-left disabled:opacity-50"
              >
                <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full flex-shrink-0 bg-muted text-muted-foreground">
                  AI 판단
                </span>
                <p className="text-sm font-medium text-muted-foreground flex-1">
                  여기 없어요
                </p>
              </button>
            </div>

            {/* Safe area spacer */}
            <div className="h-6" />
          </div>
        </>
      )}
    </div>
  );
}
