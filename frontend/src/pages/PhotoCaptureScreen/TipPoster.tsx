import { useEffect, useState } from "react";

const TIP_IMAGES = [
  "/tips/TIP (1).png",
  "/tips/TIP (2).png",
  "/tips/TIP (3).png",
  "/tips/TIP (4).png",
  "/tips/TIP (5).png",
  "/tips/TIP (6).png",
  "/tips/TIP (7).png",
  "/tips/TIP (8).png",
  "/tips/TIP (9).png",
  "/tips/TIP (10).png",
  "/tips/TIP (11).png",
  "/tips/TIP (12).png",
];

function randomTipIndex(exclude = -1) {
  let idx = Math.floor(Math.random() * TIP_IMAGES.length);
  if (TIP_IMAGES.length > 1 && idx === exclude)
    idx = (idx + 1) % TIP_IMAGES.length;
  return idx;
}

interface Props {
  className?: string;
}

// 분리배출 팁 이미지를 10초마다 무작위로 교체하며 보여주는 포스터.
// AnalyzingView2, AgentThinkingView가 동일한 포스터를 쓰도록 공용 컴포넌트로 분리했다.
export default function TipPoster({ className }: Props) {
  const [tipIdx, setTipIdx] = useState(() => randomTipIndex());
  const [tipVisible, setTipVisible] = useState(true);

  // Rotate tip image every 10 seconds with a brief fade transition
  useEffect(() => {
    const id = setInterval(() => {
      setTipVisible(false);
      setTimeout(() => {
        setTipIdx((prev) => randomTipIndex(prev));
        setTipVisible(true);
      }, 300);
    }, 10000);
    return () => clearInterval(id);
  }, []);

  return (
    <div
      className={
        className ?? "flex-1 flex items-center justify-center min-h-0"
      }
    >
      <img
        src={TIP_IMAGES[tipIdx]}
        alt="분리수거 팁"
        className="w-full h-full rounded-2xl"
        style={{
          objectFit: "contain",
          maxHeight: "100%",
          opacity: tipVisible ? 1 : 0,
          transition: "opacity 0.3s ease",
        }}
      />
    </div>
  );
}
