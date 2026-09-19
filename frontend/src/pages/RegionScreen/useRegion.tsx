import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import useAxios from "@/hooks/useAxios";
import { saveUser } from "@/utils/storage";
import { apiHeaders, authHeaders } from "@/utils/header";
import { useAuthContext } from "../AuthScreen/AuthContext";
import {
  GetRegionResponse,
  RegionItem,
  User,
  UserRegionResponse,
} from "@/types";

export function useRegion() {
  const [regionList, setRegionList] = useState<GetRegionResponse>();
  const [selectedSido, setSelectedSido] = useState("");
  const [selectedRegionId, setSelectedRegionId] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const { user, setUser } = useAuthContext();

  const navigate = useNavigate();

  // 지역 리스트 가져오기
  const { refetch: regionRequest } = useAxios<GetRegionResponse>(
    "",
    { method: "get" },
    false,
  );

  async function getRegions() {
    const endpoint = "/api/v1/regions";

    const data = await regionRequest({
      url: endpoint,
      headers: apiHeaders(),
    });
    setRegionList(data);

    // 이미 지역이 설정된 사용자(지역 변경 진입)면 목록이 오는 대로 현재 값을 셀렉트에 채운다
    if (user?.regionCode) {
      const current = data.items.find(
        (item) => String(item.region_id) === user.regionCode,
      );
      if (current) {
        setSelectedSido(current.sido_name);
        setSelectedRegionId(String(current.region_id));
      }
    }
  }

  // 지역 변경
  const { refetch: updateUserRegion } = useAxios<UserRegionResponse>(
    "",
    { method: "patch" },
    false,
  );

  // 2차 셀렉트: 선택된 시/도에 속한 시/군/구 목록 (region_id 기준)
  const districtList = useMemo<RegionItem[]>(() => {
    if (!regionList || !selectedSido) return [];
    return regionList.items.filter((item) => item.sido_name === selectedSido);
  }, [regionList, selectedSido]);

  const selectedDistrict =
    districtList.find((d) => String(d.region_id) === selectedRegionId) ?? null;

  function onSaved(updated: User) {
    setUser(updated);
    navigate("/home");
  }

  async function updateRegion() {
    // 1. 유저 로그인 상태 사전 검증
    if (!user) {
      setError("로그인 정보가 없습니다.");
      return;
    }

    // 2. 입력값 필수 검증
    if (!selectedSido || !selectedDistrict) {
      setError("시/도와 시/군/구를 모두 선택해 주세요");
      return;
    }

    setError("");
    setLoading(true);

    try {
      const regionName =
        `${selectedDistrict.sido_name} ${selectedDistrict.sgg_name}`.trim();

      // API 요청 — region_id는 Integer (명세 기준)
      await updateUserRegion({
        url: "/api/v1/users/me/region",
        data: {
          region_id: selectedDistrict.region_id,
        },
        headers: authHeaders(),
      });

      const updated: User = {
        ...user,
        regionCode: String(selectedDistrict.region_id),
        regionName,
      };

      saveUser(updated);
      onSaved(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "저장에 실패했습니다");
    } finally {
      setLoading(false);
    }
  }

  return {
    regionList,
    selectedSido,
    setSelectedSido,
    selectedRegionId,
    setSelectedRegionId,
    getRegions,
    loading,
    error,
    setError,
    user,
    districtList,
    selectedDistrict,
    updateRegion,
  };
}
