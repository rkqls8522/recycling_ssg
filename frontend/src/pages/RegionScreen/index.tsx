import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { v4 as uuidv4 } from "uuid";
import {
  type UserRegionResponse,
  type GetRegionResponse,
  type RegionItem,
  type User,
} from "../../types";
import { saveUser } from "../../utils/storage";
import { useAuthContext } from "../AuthScreen/AuthContext";
import useAxios from "@/hooks/useAxios";
import { ChevronIcon, MapPinIcon } from "@/components/common/Icons";
import { authHeaders } from "@/utils/get-auth-headers";

// 서울/경기 외 지역이 API에 추가돼도 자연스럽게 붙도록 우선순위만 지정
// (SIDO_ORDER에 없는 값은 목록 뒤쪽에 그대로 붙는다)
const SIDO_ORDER = ["서울특별시", "경기도"];

export default function RegionScreen() {
  const { user, setUser } = useAuthContext();
  const navigate = useNavigate();
  const [regionList, setRegionList] = useState<GetRegionResponse>();
  const [selectedSido, setSelectedSido] = useState("");
  const [selectedRegionId, setSelectedRegionId] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  if (!user) return null;

  const { refetch: regionRequest } = useAxios<GetRegionResponse>(
    "",
    { method: "get" },
    false,
  );

  const { refetch: updateUserRegion } = useAxios<UserRegionResponse>(
    "", // URL (또는 변수로 지정할 경로)
    { method: "patch" },
    false, // manual (자동 실행 여부)
  );

  const isFirstSetup = !user.regionCode;

  // 1차 셀렉트: /api/v1/regions 응답에서 sido_name만 중복 없이 뽑는다 (서울특별시 / 경기도)
  const sidoList = useMemo(() => {
    if (!regionList) return [];
    const unique = Array.from(
      new Set(regionList.items.map((item) => item.sido_name)),
    );
    return unique.sort(
      (a, b) => SIDO_ORDER.indexOf(a) - SIDO_ORDER.indexOf(b),
    );
  }, [regionList]);

  // 2차 셀렉트: 선택된 시/도에 속한 시/군/구 목록 (region_id 기준)
  const districtList = useMemo<RegionItem[]>(() => {
    if (!regionList || !selectedSido) return [];
    return regionList.items.filter((item) => item.sido_name === selectedSido);
  }, [regionList, selectedSido]);

  const selectedDistrict =
    districtList.find((d) => String(d.region_id) === selectedRegionId) ??
    null;

  function onSaved(updated: User) {
    setUser(updated);
    navigate("/home");
  }

  async function getRegions() {
    const endpoint = "/api/v1/regions";

    const data = await regionRequest({
      url: endpoint,
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        "X-Request-ID": uuidv4(),
      },
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

  useEffect(() => {
    getRegions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="flex flex-col h-full overflow-y-auto no-scrollbar bg-background">
      {/* Header */}
      <div className="bg-primary px-6 pt-14 pb-8">
        <div className="flex items-center gap-3 text-primary-foreground mb-2">
          <MapPinIcon />
          <span className="text-xs font-semibold uppercase tracking-widest opacity-70">
            {isFirstSetup ? "첫 번째 설정" : "지역 변경"}
          </span>
        </div>
        <h1 className="text-2xl font-bold text-primary-foreground leading-tight">
          지역을 선택해 주세요
        </h1>
        <p className="text-sm text-primary-foreground/70 mt-2 leading-relaxed">
          선택한 지역의 분리배출 기준으로 안내해 드립니다.
          <br />한 번 설정하면 다음 방문 시 자동 적용됩니다.
        </p>
      </div>

      {/* Selects */}
      <div className="px-6 pt-8 flex flex-col gap-4 flex-1">
        {/* Province */}
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
            시 / 도
          </label>
          <div className="relative">
            <select
              value={selectedSido}
              onChange={(e) => {
                setSelectedSido(e.target.value);
                setSelectedRegionId("");
                setError("");
              }}
              disabled={!regionList}
              className="w-full appearance-none px-4 py-4 rounded-xl border border-border bg-card text-foreground text-base focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-all disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <option value="">
                {regionList ? "시/도 선택" : "불러오는 중..."}
              </option>
              {sidoList.map((sido) => (
                <option key={sido} value={sido}>
                  {sido}
                </option>
              ))}
            </select>
            <div className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2">
              <ChevronIcon />
            </div>
          </div>
        </div>

        {/* District */}
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
            시 / 군 / 구
          </label>
          <div className="relative">
            <select
              value={selectedRegionId}
              onChange={(e) => {
                setSelectedRegionId(e.target.value);
                setError("");
              }}
              disabled={!selectedSido}
              className="w-full appearance-none px-4 py-4 rounded-xl border border-border bg-card text-foreground text-base focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-all disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <option value="">
                {selectedSido ? "시/군/구 선택" : "먼저 시/도를 선택하세요"}
              </option>
              {districtList.map((d) => (
                <option key={d.region_id} value={d.region_id}>
                  {d.sgg_name}
                </option>
              ))}
            </select>
            <div className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2">
              <ChevronIcon />
            </div>
          </div>
        </div>

        {/* Preview */}
        {selectedSido && selectedDistrict && (
          <div className="flex items-center gap-3 px-4 py-3.5 bg-accent rounded-xl border border-accent-foreground/10">
            <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center text-primary flex-shrink-0">
              <MapPinIcon />
            </div>
            <div>
              <p className="text-xs text-muted-foreground">선택된 지역</p>
              <p className="text-sm font-semibold text-foreground">
                {selectedDistrict.sido_name} {selectedDistrict.sgg_name}
              </p>
            </div>
          </div>
        )}

        {error && (
          <p className="text-sm text-destructive bg-red-50 px-4 py-3 rounded-lg border border-red-100">
            {error}
          </p>
        )}

        {/* Info note */}
        <div className="px-4 py-3 bg-muted rounded-xl mt-2">
          <p className="text-xs text-muted-foreground leading-relaxed">
            현재 서울시와 경기도만 제공
          </p>
        </div>
      </div>

      {/* Bottom CTA */}
      <div className="px-6 pb-8 pt-4">
        <button
          onClick={() => updateRegion()}
          disabled={loading || !selectedSido || !selectedDistrict}
          className="w-full py-4 bg-primary text-primary-foreground rounded-xl font-semibold text-base shadow-sm active:scale-[0.98] transition-all disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {loading ? (
            <span className="flex items-center justify-center gap-2">
              <svg
                className="animate-spin h-4 w-4"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                />
              </svg>
              저장 중...
            </span>
          ) : (
            "이 지역으로 설정하기"
          )}
        </button>
      </div>
    </div>
  );
}
