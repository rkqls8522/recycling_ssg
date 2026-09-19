import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from "react";

const GUIDE_BOX = { x: 0.14, y: 0.18, w: 0.72, h: 0.6 }; // 가이드 프레임 위치/크기 (0~1 비율)

const CONFIG = {
  minFillRatio: 0.3, // 바운딩 박스의 가로/세로 중 작은 쪽이 가이드 박스를 이 비율 이상 채워야 "있다"로 판단 (낮으면 "너무 멀어요")
  maxFillRatio: 0.9, // 이 이상 채워지면 "너무 가까워요"로 판단
  minNoiseFillRatio: 0.06, // 이보다 작으면 노이즈로 보고 "아예 없음"으로 취급 ("너무 멀어요"도 안 뜸)
  grabCutIntervalMs: 10, // 워커가 바쁘지 않을 때, 이 간격으로 새 요청을 보냄
  grabCutIterations: 4, // GrabCut 반복 횟수 (많을수록 정확하지만 느려짐)
  grabCutMargin: 0.08, // 가이드 박스 테두리에서 이 비율만큼 안쪽을 "물체가 있을 만한 영역" 힌트로 줌
};

interface DisplayBox {
  x: number;
  y: number;
  w: number;
  h: number;
}

interface GrabCutResult {
  fillRatio: number; // 바운딩 박스 가로/세로 중 작은 쪽이 가이드 박스를 채운 비율 (거리 판정용)
  box: DisplayBox | null;
}

interface WorkerResponse {
  reqId: number;
  coverage: number; // 참고용(면적 비율) — 실제 거리 판정에는 안 씀, box의 width/height로 fillRatio를 계산함
  box: { x: number; y: number; width: number; height: number } | null;
  error?: string;
}

interface Props {
  // 촬영된 사진을 기존 플로우(handleFileSelected)로 그대로 넘김 — CaptureView 밖은 아무것도 안 바뀜
  onCapture: (file: File) => void;
  // 카메라 권한 실패/미지원 시 부모가 기존 "탭하여 촬영"(OS 카메라) 방식으로 대체하도록 알림
  onUnavailable: () => void;
}

// 부모(CaptureView)가 바깥의 초록색 "촬영하기" 버튼에서 ref로 이 메서드를 호출함
export interface LiveViewfinderHandle {
  capture: () => void;
}

// 이 프로젝트의 실제 테마 색상(--primary, --destructive)을 그대로 읽어서 캔버스에 씀
let themeColorsCache: { primary: string; destructive: string } | null = null;
function getThemeColors() {
  if (themeColorsCache) return themeColorsCache;
  const styles = getComputedStyle(document.documentElement);
  themeColorsCache = {
    primary: styles.getPropertyValue("--primary").trim() || "#1b5c35",
    destructive: styles.getPropertyValue("--destructive").trim() || "#dc2626",
  };
  return themeColorsCache;
}

function roundRect(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number,
) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

function drawCorner(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  dx: number,
  dy: number,
  color: string,
) {
  ctx.strokeStyle = color;
  ctx.beginPath();
  ctx.moveTo(cx, cy + dy);
  ctx.lineTo(cx, cy);
  ctx.lineTo(cx + dx, cy);
  ctx.stroke();
}

const LiveViewfinder = forwardRef<LiveViewfinderHandle, Props>(
  function LiveViewfinder({ onCapture, onUnavailable }, ref) {
    const videoRef = useRef<HTMLVideoElement>(null);
    const overlayRef = useRef<HTMLCanvasElement>(null);
    const guideSampleRef = useRef<HTMLCanvasElement | null>(null);

    const isFrontCameraRef = useRef(false);
    const workerRef = useRef<Worker | null>(null);
    const workerBusyRef = useRef(false);
    const reqIdRef = useRef(0);
    const lastRequestTimeRef = useRef(0);
    const cachedResultRef = useRef<GrabCutResult>({ fillRatio: 0, box: null });
    const rafIdRef = useRef<number | null>(null);

    const [statusText, setStatusText] = useState("카메라를 켜는 중...");
    const [isObjectDetected, setIsObjectDetected] = useState(false);
    const [flashOn, setFlashOn] = useState(false);

    const drawGuide = useCallback((box: DisplayBox | null, ready: boolean) => {
      const overlay = overlayRef.current;
      const octx = overlay?.getContext("2d");
      if (!overlay || !octx) return;

      const { primary, destructive } = getThemeColors();
      octx.clearRect(0, 0, overlay.width, overlay.height);

      const x = GUIDE_BOX.x * overlay.width;
      const y = GUIDE_BOX.y * overlay.height;
      const w = GUIDE_BOX.w * overlay.width;
      const h = GUIDE_BOX.h * overlay.height;
      const r = 16;
      const color = ready ? primary : destructive;

      if (box) {
        octx.save();
        octx.strokeStyle = "#fbbf24";
        octx.lineWidth = 2;
        octx.setLineDash([5, 4]);
        octx.globalAlpha = 0.95;
        octx.strokeRect(box.x, box.y, box.w, box.h);
        octx.restore();
      }

      octx.strokeStyle = color;
      octx.lineWidth = 2;
      octx.globalAlpha = 0.55;
      octx.setLineDash([6, 6]);
      roundRect(octx, x, y, w, h, r);
      octx.stroke();
      octx.setLineDash([]);

      const bracket = 24;
      octx.lineWidth = 3;
      octx.globalAlpha = 1;
      drawCorner(octx, x, y, bracket, bracket, color);
      drawCorner(octx, x + w, y, -bracket, bracket, color);
      drawCorner(octx, x, y + h, bracket, -bracket, color);
      drawCorner(octx, x + w, y + h, -bracket, -bracket, color);
    }, []);

    const resizeOverlay = useCallback(() => {
      const overlay = overlayRef.current;
      if (!overlay) return;
      overlay.width = overlay.clientWidth;
      overlay.height = overlay.clientHeight;
      drawGuide(null, false);
    }, [drawGuide]);

    const guideBoxToRawRect = useCallback(() => {
      const video = videoRef.current;
      const overlay = overlayRef.current;
      if (!video || !overlay) return { x: 0, y: 0, w: 0, h: 0 };

      const gx = GUIDE_BOX.x * overlay.width;
      const gy = GUIDE_BOX.y * overlay.height;
      const gw = GUIDE_BOX.w * overlay.width;
      const gh = GUIDE_BOX.h * overlay.height;

      const scale = Math.max(
        overlay.width / video.videoWidth,
        overlay.height / video.videoHeight,
      );
      const offsetX = (video.videoWidth * scale - overlay.width) / 2;
      const offsetY = (video.videoHeight * scale - overlay.height) / 2;

      const preMirrorX = isFrontCameraRef.current
        ? overlay.width - gx - gw
        : gx;

      return {
        x: (preMirrorX + offsetX) / scale,
        y: (gy + offsetY) / scale,
        w: gw / scale,
        h: gh / scale,
      };
    }, []);

    // 워커가 돌려준 로컬 사각형(가이드 샘플 캔버스 기준 좌표)을 화면 표시 좌표로 변환
    const guideSampleRectToDisplayBox = useCallback(
      (localRect: {
        x: number;
        y: number;
        width: number;
        height: number;
      }): DisplayBox => {
        const overlay = overlayRef.current;
        const sample = guideSampleRef.current;
        if (!overlay || !sample) return { x: 0, y: 0, w: 0, h: 0 };

        const gx = GUIDE_BOX.x * overlay.width;
        const gy = GUIDE_BOX.y * overlay.height;
        const gw = GUIDE_BOX.w * overlay.width;
        const gh = GUIDE_BOX.h * overlay.height;
        const scaleX = gw / sample.width;
        const scaleY = gh / sample.height;

        const localX = localRect.x * scaleX;
        const localW = localRect.width * scaleX;
        // 전면 카메라는 화면에 좌우 반전(거울)으로 보여주는데, 크롭한 원본 이미지는 반전 안 돼있어서
        // 화면에 그릴 때는 가이드 박스 안에서 좌우를 다시 뒤집어야 실제 보이는 위치와 일치함
        const displayLocalX = isFrontCameraRef.current
          ? gw - localX - localW
          : localX;

        return {
          x: gx + displayLocalX,
          y: gy + localRect.y * scaleY,
          w: localW,
          h: localRect.height * scaleY,
        };
      },
      [],
    );

    // 워커가 안 바쁘고 마지막 요청에서 충분히 시간이 지났으면, 현재 프레임을 잘라서 워커에 던짐
    // (실제 GrabCut 계산은 워커 안에서 돌아서 메인 스레드/화면은 안 멈춤)
    const maybeRequestGrabCut = useCallback(() => {
      const video = videoRef.current;
      const sample = guideSampleRef.current;
      const worker = workerRef.current;
      if (!video || !sample || !worker) return;
      if (workerBusyRef.current) return;

      const now = performance.now();
      if (now - lastRequestTimeRef.current < CONFIG.grabCutIntervalMs) return;
      lastRequestTimeRef.current = now;

      const r = guideBoxToRawRect();
      const gctx = sample.getContext("2d", {
        willReadFrequently: true,
      } as CanvasRenderingContext2DSettings);
      if (!gctx) return;
      gctx.drawImage(
        video,
        r.x,
        r.y,
        r.w,
        r.h,
        0,
        0,
        sample.width,
        sample.height,
      );

      const imageData = gctx.getImageData(0, 0, sample.width, sample.height);
      workerBusyRef.current = true;
      reqIdRef.current += 1;

      worker.postMessage(
        {
          reqId: reqIdRef.current,
          width: sample.width,
          height: sample.height,
          buffer: imageData.data.buffer,
          margin: CONFIG.grabCutMargin,
          iterations: CONFIG.grabCutIterations,
        },
        [imageData.data.buffer], // zero-copy 전송 (transfer)
      );
    }, [guideBoxToRawRect]);

    // 화면은 매 프레임 부드럽게 갱신 (워커 응답이 오면 그때의 최신 결과만 반영)
    const renderLoop = useCallback(() => {
      maybeRequestGrabCut();

      const result = cachedResultRef.current;
      const fillRatio = result.fillRatio;
      const hasBox = fillRatio >= CONFIG.minNoiseFillRatio; // 노이즈보단 확실히 큰 뭔가가 있음
      const isTooFar = hasBox && fillRatio < CONFIG.minFillRatio; // 있긴 한데 너무 작게 보임
      const isTooClose = fillRatio >= CONFIG.maxFillRatio; // 가이드 박스를 거의 다 채움
      const isReady = hasBox && !isTooFar && !isTooClose;

      drawGuide(hasBox ? result.box : null, isReady);
      setIsObjectDetected(isReady);

      let message = "폐기물을 프레임 안에 놓아주세요";
      if (isTooClose) {
        message = "너무 가까워요, 조금 멀리 떨어져 주세요";
      } else if (isTooFar) {
        message = "너무 멀어요, 조금 가까이 가져와 주세요";
      } else if (hasBox) {
        message = "물체가 인식됐어요, 촬영해보세요";
      }
      setStatusText(message);

      rafIdRef.current = requestAnimationFrame(renderLoop);
    }, [drawGuide, maybeRequestGrabCut]);

    const capturePhoto = useCallback(() => {
      const video = videoRef.current;
      if (!video) return;

      const shotCanvas = document.createElement("canvas");
      shotCanvas.width = video.videoWidth;
      shotCanvas.height = video.videoHeight;
      const shotCtx = shotCanvas.getContext("2d");
      if (!shotCtx) return;

      if (!isFrontCameraRef.current) {
        shotCtx.drawImage(video, 0, 0, shotCanvas.width, shotCanvas.height);
      } else {
        shotCtx.translate(shotCanvas.width, 0);
        shotCtx.scale(-1, 1);
        shotCtx.drawImage(video, 0, 0, shotCanvas.width, shotCanvas.height);
      }

      setFlashOn(true);
      setTimeout(() => setFlashOn(false), 300);

      shotCanvas.toBlob(
        (blob) => {
          if (!blob) return;
          const file = new File([blob], `capture-${Date.now()}.jpg`, {
            type: "image/jpeg",
          });
          onCapture(file);
        },
        "image/jpeg",
        0.92,
      );
    }, [onCapture]);

    useImperativeHandle(ref, () => ({ capture: capturePhoto }), [capturePhoto]);

    useEffect(() => {
      let stream: MediaStream | null = null;
      let cancelled = false;

      async function init() {
        try {
          stream = await navigator.mediaDevices.getUserMedia({
            video: {
              facingMode: { ideal: "environment" },
              width: 1280,
              height: 960,
            },
            audio: false,
          });
          if (cancelled) {
            stream.getTracks().forEach((t) => t.stop());
            return;
          }
          const video = videoRef.current;
          if (!video) return;
          video.srcObject = stream;
          await video.play();

          const track = stream.getVideoTracks()[0];
          const settings = track.getSettings();
          isFrontCameraRef.current = settings.facingMode
            ? settings.facingMode === "user"
            : false;

          const sampleW = 100;
          const sampleH = Math.max(
            1,
            Math.round(sampleW * (GUIDE_BOX.h / GUIDE_BOX.w)),
          );
          const sample = document.createElement("canvas");
          sample.width = sampleW;
          sample.height = sampleH;
          guideSampleRef.current = sample;

          resizeOverlay();
        } catch (err) {
          // 카메라 권한 거부, 지원 안 되는 브라우저 등 → 부모가 기존 방식(OS 카메라)으로 대체하게 함
          console.error("카메라를 사용할 수 없어요:", err);
          onUnavailable();
          return;
        }

        // GrabCut 워커 시작 (OpenCV.js는 이 워커 안에서만 로드됨 — 메인 스레드는 안 건드림)
        const worker = new Worker(
          new URL("./grabcut.worker.ts", import.meta.url),
        );
        worker.onmessage = (e: MessageEvent<WorkerResponse>) => {
          const { box: localBox, error } = e.data;
          workerBusyRef.current = false;
          if (error) {
            console.error("GrabCut worker error:", error);
            return;
          }

          const sample = guideSampleRef.current;
          let fillRatio = 0;
          if (localBox && sample) {
            // 면적이 아니라 "바운딩 박스가 가이드 박스를 가로/세로로 얼마나 채우는지"로 거리를 판단
            const fillRatioW = localBox.width / sample.width;
            const fillRatioH = localBox.height / sample.height;
            fillRatio = Math.min(fillRatioW, fillRatioH); // 가로/세로 중 덜 채워진 쪽 기준
          }

          cachedResultRef.current = {
            fillRatio,
            box: localBox ? guideSampleRectToDisplayBox(localBox) : null,
          };
        };
        worker.onerror = (err) => {
          console.error("GrabCut worker 치명적 오류:", err);
          workerBusyRef.current = false;
        };
        workerRef.current = worker;

        rafIdRef.current = requestAnimationFrame(renderLoop);
      }

      // StrictMode는 개발 모드에서 마운트→정리(cleanup)→재마운트를 같은 틱(tick) 안에서 동기적으로 실행함.
      // init()을 setTimeout으로 한 틱 늦추면, '가짜' 첫 마운트는 정리 함수가 먼저 실행되면서
      // 아래 clearTimeout으로 취소돼서 카메라를 아예 안 켜고, 실제로 남는 마운트만 카메라를 켬.
      // (getUserMedia를 짧은 시간 안에 두 번 부르면 일부 웹캠/드라이버에서 화면이 멈추는 문제가 있어서 이렇게 막음)
      const startTimer = setTimeout(() => {
        void init();
      }, 0);

      const handleResize = () => resizeOverlay();
      window.addEventListener("resize", handleResize);

      return () => {
        cancelled = true;
        clearTimeout(startTimer);
        window.removeEventListener("resize", handleResize);
        if (rafIdRef.current) cancelAnimationFrame(rafIdRef.current);
        workerRef.current?.terminate();
        stream?.getTracks().forEach((t) => t.stop());
      };
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    return (
      <div className="absolute inset-0">
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          className={`absolute inset-0 w-full h-full object-cover ${isFrontCameraRef.current ? "-scale-x-100" : ""}`}
        />
        <canvas
          ref={overlayRef}
          className="absolute inset-0 w-full h-full pointer-events-none"
        />

        {flashOn && (
          <div className="absolute inset-0 bg-white opacity-80 transition-opacity duration-300" />
        )}

        <div
          className={`absolute left-1/2 top-4 -translate-x-1/2 whitespace-nowrap rounded-full px-4 py-1.5 text-xs font-medium text-white transition-colors ${
            isObjectDetected ? "bg-primary/80" : "bg-black/60"
          }`}
        >
          {statusText}
        </div>
      </div>
    );
  },
);

export default LiveViewfinder;
