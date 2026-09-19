import { useState } from "react";
import { ClassificationResult } from "@/types";

export function useResult() {
  const [chatOpen, setChatOpen] = useState(false);
  const [feedbackError, setFeedbackError] = useState("");
  const [pickerOpen, setPickerOpen] = useState(false);
  const [result, setResult] = useState<ClassificationResult>(EMPTY_RESULT);
  const [feedbackBusy, setFeedbackBusy] = useState(false);
  const [agentThinkingOpen, setAgentThinkingOpen] = useState(false);

  function handlePickerOpen() {
    setChatOpen(false);
    setFeedbackError("");
    setPickerOpen(true);
  }

  function handleRetake() {
    handlePickerOpen();
  }

  return {
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
  };
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
