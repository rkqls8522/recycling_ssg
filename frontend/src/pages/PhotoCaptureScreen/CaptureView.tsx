import { useRef, useState } from "react";
import BackButton from "../../components/common/BackButton";
import FlowIndicator from "../../components/common/FlowIndicator";
import { UserIcon } from "../../components/common/Icons";
import LiveViewfinder, { type LiveViewfinderHandle } from "./LiveViewfinder";

interface Props {
  previewUrl: string | null;
  onFileSelected: (file: File) => void;
  onAnalyze: () => void;
  onReset: () => void;
  onBack: () => void;
  // HomeScreen이 없어지고 이 화면이 /home 역할까지 겸하게 되면서
  // (기존 HomeScreen에 있던) 마이페이지 진입/지역 미설정 안내를 여기서 대신 제공한다.
  hasRegion: boolean;
  onOpenMyPage: () => void;
  onSetRegion: () => void;
}

function CornerMarks() {
  const corner = "absolute w-7 h-7 border-primary";
  return (
    <>
      <div
        className={`${corner} top-0 left-0 border-t-[3px] border-l-[3px] rounded-tl-lg`}
      />
      <div
        className={`${corner} top-0 right-0 border-t-[3px] border-r-[3px] rounded-tr-lg`}
      />
      <div
        className={`${corner} bottom-0 left-0 border-b-[3px] border-l-[3px] rounded-bl-lg`}
      />
      <div
        className={`${corner} bottom-0 right-0 border-b-[3px] border-r-[3px] rounded-br-lg`}
      />
    </>
  );
}

export default function CaptureView({
  previewUrl,
  onFileSelected,
  onAnalyze,
  onReset,
  onBack,
  hasRegion,
  onOpenMyPage,
  onSetRegion,
}: Props) {
  const cameraRef = useRef<HTMLInputElement>(null);
  const galleryRef = useRef<HTMLInputElement>(null);
  const liveViewfinderRef = useRef<LiveViewfinderHandle>(null);
  // 실시간 카메라(getUserMedia)를 못 쓰면(권한 거부, 미지원 브라우저 등) 기존 방식(OS 카메라 열기)으로 대체
  const [liveCameraUnavailable, setLiveCameraUnavailable] = useState(false);

  function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) onFileSelected(file);
    e.target.value = "";
  }

  return (
    <div className="flex flex-col h-full bg-background">
      {/* Header */}
      <div className="bg-primary text-primary-foreground px-5 pt-12 pb-4">
        <div className="flex items-center justify-between mb-4">
          <BackButton onClick={onBack} ariaLabel="홈으로 돌아가기" />
          <FlowIndicator currentStep={0} />
          <button
            onClick={onOpenMyPage}
            className="w-9 h-9 flex items-center justify-center rounded-xl bg-primary-foreground/10 active:bg-primary-foreground/20 transition-colors"
            aria-label="마이페이지"
          >
            <UserIcon />
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 flex flex-col px-5 pt-5 pb-4 gap-4 overflow-y-auto no-scrollbar">
        {/* Viewfinder / Preview */}
        <div className="relative">
          <div
            className={`relative rounded-2xl overflow-hidden bg-muted flex items-center justify-center transition-all ${
              previewUrl
                ? "border-2 border-primary"
                : "border-2 border-dashed border-border"
            }`}
            style={{ minHeight: 260 }}
          >
            {previewUrl ? (
              <>
                <img
                  src={previewUrl}
                  alt="선택된 폐기물 사진"
                  className="w-full object-cover"
                  style={{ maxHeight: 300 }}
                />
                {/* Corner marks overlay */}
                <div className="absolute inset-4 pointer-events-none">
                  <CornerMarks />
                </div>
                {/* Remove button */}
                <button
                  onClick={onReset}
                  className="absolute top-3 right-3 w-8 h-8 rounded-full bg-black/50 flex items-center justify-center text-white hover:bg-black/70 transition-colors"
                  aria-label="사진 제거"
                >
                  <svg
                    viewBox="0 0 20 20"
                    fill="currentColor"
                    className="w-4 h-4"
                    aria-hidden="true"
                  >
                    <path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22z" />
                  </svg>
                </button>
              </>
            ) : liveCameraUnavailable ? (
              /* Empty viewfinder with guide (실시간 카메라를 못 쓸 때의 대체 화면) */
              <div
                className="relative flex flex-col items-center justify-center py-12 px-6 cursor-pointer w-full h-full"
                onClick={() => cameraRef.current?.click()}
              >
                {/* Guide frame */}
                <div className="absolute inset-8 pointer-events-none">
                  <CornerMarks />
                </div>
                <div className="w-16 h-16 rounded-2xl bg-muted-foreground/10 flex items-center justify-center mb-3">
                  <svg
                    viewBox="0 0 24 24"
                    fill="none"
                    className="w-8 h-8 text-muted-foreground"
                    aria-hidden="true"
                  >
                    <path
                      d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"
                      stroke="currentColor"
                      strokeWidth="1.5"
                      strokeLinejoin="round"
                    />
                    <circle
                      cx="12"
                      cy="13"
                      r="4"
                      stroke="currentColor"
                      strokeWidth="1.5"
                    />
                  </svg>
                </div>
                <p className="text-sm font-semibold text-foreground">
                  탭하여 촬영
                </p>
                <p className="text-xs text-muted-foreground mt-0.5 text-center">
                  또는 하단에서 갤러리 선택
                </p>
              </div>
            ) : (
              /* 실시간 카메라 + 가이드 프레임 자동 인식 (GrabCut) */
              <LiveViewfinder
                ref={liveViewfinderRef}
                onCapture={onFileSelected}
                onUnavailable={() => setLiveCameraUnavailable(true)}
              />
            )}
          </div>
        </div>

        {/* Shooting guide tips */}
        <div className="bg-card border border-border rounded-2xl px-4 py-3.5">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2.5">
            촬영 가이드
          </p>
          <div className="flex flex-col gap-2">
            {[
              { icon: "🎯", tip: "물체가 화면 중앙에 오도록 촬영하세요" },
              { icon: "💡", tip: "단순한 단색 배경에서 촬영하면 인식률이 높아집니다" },
              { icon: "📐", tip: "물체 전체가 프레임 안에 들어오게 해주세요" },
            ].map(({ icon, tip }) => (
              <div key={tip} className="flex items-start gap-2.5">
                <span className="text-base leading-none mt-0.5">{icon}</span>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  {tip}
                </p>
              </div>
            ))}
          </div>
        </div>

        {/* Region warning — HomeScreen에 있던 것을 이관 */}
        {!hasRegion && (
          <div className="flex items-start gap-3 px-4 py-3.5 bg-amber-50 rounded-xl border border-amber-200">
            <span className="text-amber-500 text-base mt-0.5 flex-shrink-0">
              !
            </span>
            <div>
              <p className="text-sm font-semibold text-amber-900">
                지역이 설정되지 않았습니다
              </p>
              <button
                onClick={onSetRegion}
                className="text-xs text-amber-700 underline mt-0.5"
              >
                지역 설정하기
              </button>
            </div>
          </div>
        )}

        {/* Hidden inputs */}
        <input
          ref={cameraRef}
          type="file"
          accept="image/*"
          capture="environment"
          className="hidden"
          onChange={handleFile}
        />
        <input
          ref={galleryRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={handleFile}
        />
      </div>

      {/* Bottom CTA */}
      <div className="px-5 pb-8 pt-2 flex flex-col gap-2.5">
        {previewUrl ? (
          <>
            <button
              onClick={onAnalyze}
              disabled={!hasRegion}
              className="w-full py-4 bg-primary text-primary-foreground rounded-2xl font-semibold text-base shadow-lg shadow-primary/20 active:scale-[0.98] transition-all flex items-center justify-center gap-2.5 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <svg
                viewBox="0 0 24 24"
                fill="none"
                className="w-5 h-5"
                aria-hidden="true"
              >
                <circle
                  cx="11"
                  cy="11"
                  r="8"
                  stroke="currentColor"
                  strokeWidth="1.5"
                />
                <path
                  d="M21 21l-4.35-4.35"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                />
              </svg>
              분석하기
            </button>
            <button
              onClick={onReset}
              className="w-full py-3 text-sm font-medium text-muted-foreground flex items-center justify-center gap-1.5 active:opacity-60 transition-opacity"
            >
              <svg
                viewBox="0 0 20 20"
                fill="currentColor"
                className="w-4 h-4"
                aria-hidden="true"
              >
                <path
                  fillRule="evenodd"
                  d="M15.312 11.424a5.5 5.5 0 0 1-9.201 2.466l-.312-.311h2.433a.75.75 0 0 0 0-1.5H5.498a.75.75 0 0 0-.75.75v3.498a.75.75 0 0 0 1.5 0v-1.590l.308.31a7 7 0 0 0 11.717-3.138.75.75 0 0 0-1.466-.313zm-7.498-4.697l-.312.31V4.537a.75.75 0 0 0-1.5 0v3.498c0 .414.336.75.75.75h3.498a.75.75 0 0 0 0-1.5H7.617l.31-.311a7 7 0 0 0 11.524 3.947.75.75 0 0 0-.998-1.122 5.5 5.5 0 0 1-9.639-2.845z"
                  clipRule="evenodd"
                />
              </svg>
              다시 촬영하기
            </button>
          </>
        ) : (
          <>
            {/* 촬영하기: 라이브 카메라면 뷰파인더의 촬영을, 폴백이면 OS 카메라를 트리거 */}
            <button
              onClick={() => {
                if (liveCameraUnavailable) {
                  cameraRef.current?.click();
                } else {
                  liveViewfinderRef.current?.capture();
                }
              }}
              className="w-full py-4 bg-primary text-primary-foreground rounded-2xl font-semibold text-base shadow-lg shadow-primary/20 active:scale-[0.98] transition-all flex items-center justify-center gap-2.5"
            >
              <svg
                viewBox="0 0 24 24"
                fill="none"
                className="w-6 h-6"
                aria-hidden="true"
              >
                <path
                  d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinejoin="round"
                />
                <circle
                  cx="12"
                  cy="13"
                  r="4"
                  stroke="currentColor"
                  strokeWidth="1.5"
                />
              </svg>
              촬영하기
            </button>

            {/* 갤러리에서 선택 */}
            <button
              onClick={() => galleryRef.current?.click()}
              className="flex items-center justify-center gap-2.5 px-5 py-3.5 rounded-xl border border-border bg-card text-sm font-medium text-foreground active:bg-muted transition-all"
            >
              <svg
                viewBox="0 0 24 24"
                fill="none"
                className="w-5 h-5"
                aria-hidden="true"
              >
                <rect
                  x="3"
                  y="3"
                  width="18"
                  height="18"
                  rx="2"
                  stroke="currentColor"
                  strokeWidth="1.5"
                />
                <circle
                  cx="8.5"
                  cy="8.5"
                  r="1.5"
                  stroke="currentColor"
                  strokeWidth="1.5"
                />
                <path
                  d="M21 15l-5-5L5 21"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinejoin="round"
                />
              </svg>
              갤러리에서 선택
            </button>
          </>
        )}
      </div>
    </div>
  );
}