import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import type { ClassificationResult } from "../../types";
import ChatDrawer from "./ChatDrawer";
import BackButton from "../../components/common/BackButton";
import { ChatbotIcon, MoveToSourceIcon } from "@/components/common/Icons";
import AgentThinkingView from "../PhotoCaptureScreen/AgentThinkingView";
import { useResult } from "./useResult";
import { useFeedback } from "./useFeedback";

interface ResultLocationState {
  result: ClassificationResult;
  imageUrl: string;
}

export default function ResultScreen() {
  const location = useLocation();
  const navigate = useNavigate();
  const state = location.state as ResultLocationState | null;
  const [imageUrl, setImageUrl] = useState("");

  const {
    handleRetake,
    feedbackError,
    setFeedbackError,
    pickerOpen,
    setPickerOpen,
    result,
    setResult,
    feedbackBusy,
    setFeedbackBusy,
    agentThinkingOpen,
    setAgentThinkingOpen,
    chatOpen,
    setChatOpen,
  } = useResult();

  const { handleYoloFeedback, handleCandidateFeedback, handleNotListed } =
    useFeedback(
      result,
      setResult,
      setPickerOpen,
      setFeedbackBusy,
      setFeedbackError,
      setAgentThinkingOpen,
    );

  const { itemName, guidelines, regionName } = result;

  useEffect(() => {
    if (!state?.result) {
      navigate("/capture", { replace: true });
      return;
    }
    setResult(state.result);
    setImageUrl(state.imageUrl);
  }, [state]);

  if (agentThinkingOpen) {
    return <AgentThinkingView onBack={() => setAgentThinkingOpen(false)} />;
  }

  return (
    <div className="flex flex-col h-full bg-background">
      {/* Header */}
      <div className="bg-primary text-primary-foreground px-5 pt-12 pb-4 flex items-center gap-3">
        <BackButton onClick={() => navigate("/home")} ariaLabel="뒤로 가기" />
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
        <div className="bg-card rounded-2xl border border-border scrollbar-thin overflow-auto ">
          <div className="px-5 pt-5 pb-4 border-b border-border">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-widest">
              배출 방법
            </p>
            <h4 className="text-base font-bold text-foreground mt-1">
              📍 {itemName} 배출 방법
            </h4>
          </div>

          {guidelines.nationalRule || guidelines.regionRule ? (
            <>
              {/* 전국 공통 기준 (national_rule) */}
              {guidelines.nationalRule && (
                <div className="px-5 pt-4 pb-4 border-b border-border">
                  <p className="text-xs font-bold text-foreground mb-2">
                    [전국 공통 기준 : {guidelines.nationalRule.source}]
                  </p>
                  <p className="text-sm text-foreground leading-relaxed whitespace-pre-line">
                    {guidelines.nationalRule.method}
                  </p>
                </div>
              )}

              {/* 지자체 추가 안내 (region_rule) */}
              {guidelines.regionRule && (
                <div className="px-5 pt-4 pb-5 bg-amber-50">
                  <p className="text-xs font-bold text-amber-800 mb-2">
                    ⚠️ {guidelines.regionRule.region} 추가 안내
                  </p>
                  <p className="text-sm text-amber-900 leading-relaxed whitespace-pre-line mb-2">
                    {guidelines.regionRule.method}
                  </p>
                </div>
              )}
            </>
          ) : (
            <>
              {/* Steps — RAG 데이터가 없을 때(mock/구식 흐름)의 폴백 렌더링 */}
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
            </>
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
            onClick={() => {
              result.feedbackId && handleYoloFeedback(result.feedbackId);
            }}
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
            <ChatbotIcon />
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

                return (
                  <button
                    key={candidate.class_id}
                    onClick={() => handleCandidateFeedback(candidate.class_id)}
                    disabled={feedbackBusy}
                    className="w-full flex items-center gap-3 px-4 py-3 rounded-xl active:bg-muted transition-colors text-left disabled:opacity-50"
                  >
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
