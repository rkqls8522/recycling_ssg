import { useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import type { ClassificationResult, CaptureState } from "../../types";
import { classifyImage } from "../../api/api";
import { DEMO_IMAGE } from "../../api/mockData";
import { useAuthContext } from "../AuthScreen/AuthContext";
import CaptureView from "./CaptureView";
import AnalyzingView from "./AnalyzingView";
import ResultFailView from "./ResultFailView";
import AgentThinkingView from "./AgentThinkingView";

type DemoState = "analyzing" | "agent_thinking" | "fail";

export default function PhotoCaptureScreen() {
  const { user } = useAuthContext();
  const navigate = useNavigate();
  const location = useLocation();
  const demoState = (location.state as { demoState?: DemoState } | null)
    ?.demoState;

  const [captureState, setCaptureState] = useState<CaptureState>(
    demoState ?? "capture",
  );
  const [previewUrl, setPreviewUrl] = useState<string | null>(
    demoState ? DEMO_IMAGE : null,
  );
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [result, setResult] = useState<ClassificationResult | null>(
    demoState === "fail"
      ? {
          itemName: "",
          itemCategory: "",
          itemCategoryEn: "unclear",
          confidence: 32,
          confidenceLevel: "low",
          failureHint: "blurry",
          guidelines: {
            steps: [],
            notes: [],
            collectionDays: "",
            source: "",
            sourceUrl: "",
          },
          regionCode: user?.regionCode ?? "",
          regionName: user?.regionName ?? "",
        }
      : null,
  );
  const [completedSteps, setCompletedSteps] = useState<number[]>([]);
  const [currentStep, setCurrentStep] = useState(-1);

  const galleryRef = useRef<HTMLInputElement>(null);
  const prevUrl = useRef<string | null>(null);

  if (!user) return null;

  function onBack() {
    navigate("/home");
  }

  function onViewGuidelines(r: ClassificationResult, imageUrl: string) {
    navigate("/result", { state: { result: r, imageUrl } });
  }

  function setPreviewWithCleanup(url: string | null) {
    if (prevUrl.current) URL.revokeObjectURL(prevUrl.current);
    prevUrl.current = url;
    setPreviewUrl(url);
  }

  function handleFileSelected(file: File) {
    const url = URL.createObjectURL(file);
    setSelectedFile(file);
    setPreviewWithCleanup(url);
    setCaptureState("capture");
    setCompletedSteps([]);
    setCurrentStep(-1);
  }

  async function handleAnalyze() {
    if (!selectedFile || !user!.regionCode || !user!.regionName) return;

    setCaptureState("analyzing");
    setCompletedSteps([]);
    setCurrentStep(0);

    try {
      const classifyResult = await classifyImage(
        selectedFile,
        user!.regionCode,
        user!.regionName,
        (stepIndex) => {
          setCompletedSteps((prev) => [...prev, stepIndex]);
          setCurrentStep(stepIndex + 1);
        },
      );
      setResult(classifyResult);

      if (classifyResult.confidenceLevel === "high") {
        // High confidence → skip intermediate result, go straight to guidelines
        onViewGuidelines(classifyResult, previewUrl!);
      } else if (classifyResult.confidenceLevel === "uncertain") {
        setCaptureState("uncertain");
      } else {
        setCaptureState("fail");
      }
    } catch {
      setResult(null);
      setCaptureState("fail");
    }
  }

  function handleReset() {
    setPreviewWithCleanup(null);
    setSelectedFile(null);
    setCaptureState("capture");
    setResult(null);
    setCompletedSteps([]);
    setCurrentStep(-1);
  }

  function handleReanalyzed(newResult: ClassificationResult) {
    setResult(newResult);
    if (newResult.confidenceLevel === "high") {
      onViewGuidelines(newResult, previewUrl!);
    } else {
      setCaptureState("fail");
    }
  }

  function handleOpenGallery() {
    setCaptureState("capture");
    // Small delay to let state settle before triggering gallery
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
        />
      )}

      {captureState === "analyzing" && (previewUrl ?? DEMO_IMAGE) && (
        <AnalyzingView
          previewUrl={previewUrl ?? DEMO_IMAGE}
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
          imageUrl={previewUrl ?? DEMO_IMAGE}
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
