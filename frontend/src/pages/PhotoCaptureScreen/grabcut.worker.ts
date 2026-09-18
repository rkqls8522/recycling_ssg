// GrabCut을 메인 스레드 밖(별도 스레드)에서 돌리는 워커.
// OpenCV.js도 이 워커 안에서만 로드해서, 메인 스레드는 화면 그리는 것에만 집중하게 함.

interface GrabCutRequest {
  reqId: number;
  width: number;
  height: number;
  buffer: ArrayBuffer; // RGBA Uint8ClampedArray.buffer (postMessage로 transfer됨)
  margin: number;
  iterations: number;
}

interface GrabCutResponse {
  reqId: number;
  coverage: number;
  box: { x: number; y: number; width: number; height: number } | null;
  error?: string;
}

let cvReady = false;
let cvLoadingPromise: Promise<void> | null = null;

function loadOpenCv(): Promise<void> {
  if (cvReady) return Promise.resolve();
  if (cvLoadingPromise) return cvLoadingPromise;

  cvLoadingPromise = new Promise((resolve, reject) => {
    try {
      // 워커(클래식 워커)에서는 importScripts로 전역 스크립트를 동기적으로 불러올 수 있음
      (self as any).importScripts("https://docs.opencv.org/4.x/opencv.js");
    } catch (err) {
      reject(err);
      return;
    }
    const start = performance.now();
    const check = () => {
      const cvGlobal = (self as any).cv;
      if (cvGlobal && typeof cvGlobal.Mat === "function") {
        cvReady = true;
        resolve();
        return;
      }
      if (cvGlobal && !cvGlobal.Mat) {
        cvGlobal["onRuntimeInitialized"] = () => {
          cvReady = true;
          resolve();
        };
        return;
      }
      if (performance.now() - start > 20000) {
        reject(new Error("OpenCV 로딩 타임아웃 (worker)"));
        return;
      }
      setTimeout(check, 100);
    };
    check();
  });

  return cvLoadingPromise;
}

self.onmessage = async (e: MessageEvent<GrabCutRequest>) => {
  const { reqId, width, height, buffer, margin, iterations } = e.data;

  try {
    await loadOpenCv();
    const cv = (self as any).cv;

    const imageData = new ImageData(new Uint8ClampedArray(buffer), width, height);

    let src: any, srcRGB: any, mask: any, bgdModel: any, fgdModel: any;
    try {
      src = cv.matFromImageData(imageData);
      srcRGB = new cv.Mat();
      cv.cvtColor(src, srcRGB, cv.COLOR_RGBA2RGB);

      mask = cv.Mat.zeros(srcRGB.rows, srcRGB.cols, cv.CV_8UC1);
      bgdModel = new cv.Mat();
      fgdModel = new cv.Mat();

      const mx = Math.round(srcRGB.cols * margin);
      const my = Math.round(srcRGB.rows * margin);
      const rect = new cv.Rect(mx, my, srcRGB.cols - mx * 2, srcRGB.rows - my * 2);

      cv.grabCut(srcRGB, mask, rect, bgdModel, fgdModel, iterations, cv.GC_INIT_WITH_RECT);

      const maskData = mask.data as Uint8Array;
      let minX = mask.cols;
      let minY = mask.rows;
      let maxX = 0;
      let maxY = 0;
      let fgCount = 0;
      for (let y = 0; y < mask.rows; y++) {
        for (let x = 0; x < mask.cols; x++) {
          const v = maskData[y * mask.cols + x];
          if (v === 1 || v === 3) {
            fgCount++;
            if (x < minX) minX = x;
            if (x > maxX) maxX = x;
            if (y < minY) minY = y;
            if (y > maxY) maxY = y;
          }
        }
      }

      const sampleArea = width * height;
      const coverage = sampleArea > 0 ? fgCount / sampleArea : 0;

      const response: GrabCutResponse =
        fgCount === 0
          ? { reqId, coverage: 0, box: null }
          : { reqId, coverage, box: { x: minX, y: minY, width: maxX - minX, height: maxY - minY } };

      (self as any).postMessage(response);
    } finally {
      [src, srcRGB, mask, bgdModel, fgdModel].forEach((m) => m && m.delete());
    }
  } catch (err) {
    const response: GrabCutResponse = {
      reqId,
      coverage: 0,
      box: null,
      error: err instanceof Error ? err.message : String(err),
    };
    (self as any).postMessage(response);
  }
};
