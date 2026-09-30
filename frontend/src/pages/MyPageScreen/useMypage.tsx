import useAxios from "@/hooks/useAxios";
import {
  ClassificationResult,
  DisposalScheduleResponse,
  FavoriteResponse,
  RegionInfo,
  UserResponse,
} from "@/types";
import { authHeaders } from "@/utils/header";
import { useNavigate } from "react-router-dom";
import { useAuthContext } from "../AuthScreen/AuthContext";
import {
  FALLBACK_GUIDELINE,
  mapDisposalSchedule,
} from "../PhotoCaptureScreen/useAnalyze";

export function useMypage() {
  const navigate = useNavigate();
  const { logout: authLogout, user } = useAuthContext();

  // 즐겨찾기 항목 가져오기
  const {
    data: favorites,
    loading: favoritesLoading,
    refetch,
  } = useAxios<FavoriteResponse>("", { method: "get" }, false);

  async function loadFavorites() {
    try {
      await refetch({
        url: "/api/v1/favorites",
        headers: authHeaders(),
      });

      // TODO: 조회 성공시 로직
    } catch (e) {
      console.error("즐겨찾기 조회 실패:", e);
    }
  }

  // 즐겨찾기 항목 클릭 → 해당 품목의 배출정보를 조회해 결과 화면으로 이동.
  // /analyze 흐름이 아니라 저장된 class_id 기준 조회라 feedbackId는 없다 —
  // ResultScreen/ChatDrawer는 feedbackId가 없으면 챗봇 연결을 알아서 건너뛴다.
  const { refetch: disposalRequest } = useAxios<DisposalScheduleResponse>(
    "",
    { method: "get" },
    false,
  );

  async function handleFavoriteClick(item: {
    class_id: number;
    major_category: string;
    minor_category: string;
  }) {
    if (!user?.regionCode || !user?.regionName) return;

    let guidelines = FALLBACK_GUIDELINE;
    try {
      const schedule = await disposalRequest({
        url: "/api/v1/disposal/schedule",
        params: { class_id: item.class_id },
        headers: authHeaders(),
      });
      guidelines = mapDisposalSchedule(schedule);
    } catch (e) {
      console.error("즐겨찾기 배출정보 조회 실패:", e);
    }

    const result: ClassificationResult = {
      itemName: item.minor_category,
      itemCategory: item.major_category,
      itemCategoryEn: String(item.class_id),
      confidence: 100,
      confidenceLevel: "high",
      guidelines,
      regionCode: user.regionCode,
      regionName: user.regionName,
      classId: item.class_id,
    };

    navigate("/result", { state: { result, imageUrl: "" } });
  }

  // 로그아웃
  const { refetch: logoutRequest } = useAxios<void>(
    "",
    { method: "post" },
    false,
  );

  async function logout() {
    try {
      await logoutRequest({
        url: "/api/v1/auth/logout",
        headers: authHeaders(),
      });

      authLogout();
      navigate("/login", { replace: true });
    } catch (e) {
      console.error("로그아웃 실패:", e);
    }
  }

  return { favorites, favoritesLoading, loadFavorites, logout, handleFavoriteClick };
}
