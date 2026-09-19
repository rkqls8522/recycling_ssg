import { useRef } from "react";
import { useNavigate } from "react-router-dom";
import CaptureView from "./CaptureView";
import AnalyzingView from "./AnalyzingView";
import ResultFailView from "./ResultFailView";
import AgentThinkingView from "./AgentThinkingView";
import { useAnalyze } from "./useAnalyze";
import AnalyzingView2 from "./AnalyzingView2";

export default function PhotoCaptureScreen() {
  const navigate = useNavigate();
  const galleryRef = useRef<HTMLInputElement>(null);

  const {
    user,
    previewUrl,
    setCaptureState,
    captureState,
    completedSteps,
    currentStep,
    handleFileSelected,
    handleAnalyze,
    result,
    handleReset,
  } = useAnalyze();

  if (!user) return null;

  function onBack() {
    navigate("/home");
  }

  function handleOpenGallery() {
    setCaptureState("capture");
    setTimeout(() => galleryRef.current?.click(), 50);
  }

  return (
    <div className="h-full relative">
      {/* Transition wrapper — each view fades in */}
      {captureState === "capture" && (
        <CaptureView
          previewUrl={previewUrl}
          onFileSelected={handleFileSelected}
          onAnalyze={handleAnalyze}
          onReset={handleReset}
          onBack={onBack}
          hasRegion={!!user.regionCode}
          onOpenMyPage={() => navigate("/mypage")}
          onSetRegion={() => navigate("/region")}
        />
      )}

      {captureState === "analyzing" && previewUrl && (
        <AnalyzingView2
          previewUrl={previewUrl}
          completedSteps={completedSteps}
          currentStep={currentStep}
        />
      )}

      {captureState === "agent_thinking" && (
        <AgentThinkingView onBack={handleReset} />
      )}

      {captureState === "fail" && (
        <ResultFailView
          failureHint={result?.failureHint}
          imageUrl={previewUrl ?? ""}
          onRetake={handleReset}
          onGallery={handleOpenGallery}
        />
      )}

      {/* Shared hidden gallery input — used by ResultFailView's gallery button */}
      <input
        ref={galleryRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) handleFileSelected(file);
          e.target.value = "";
        }}
      />
    </div>
  );
}
