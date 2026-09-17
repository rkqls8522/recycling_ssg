import useAxios from "@/hooks/useAxios";
import { FavoriteResponse, RegionInfo, UserResponse } from "@/types";
import { authHeaders } from "@/utils/header";
import { useNavigate } from "react-router-dom";
import { useAuthContext } from "../AuthScreen/AuthContext";

export function useMypage() {
  const navigate = useNavigate();
  const { logout: authLogout } = useAuthContext();

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

  return { favorites, favoritesLoading, loadFavorites, logout };
}
