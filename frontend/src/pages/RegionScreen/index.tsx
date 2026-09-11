import { useState } from "react";
import { useNavigate } from "react-router-dom";
import type { User } from "../../types";
import { updateUserRegion } from "../../api/api";
import { saveUser } from "../../utils/storage";
import { PROVINCES } from "../../api/mockData";
import { useAuthContext } from "../AuthScreen/AuthContext";
import { ChevronIcon, MapPinIcon } from "@/components/common/Icons";

export default function RegionScreen() {
  const { user, setUser } = useAuthContext();
  const navigate = useNavigate();
  const [selectedProvince, setSelectedProvince] = useState(() => {
    if (user?.regionCode) {
      return PROVINCES.find((p) => user.regionCode!.startsWith(p.code)) ?? null;
    }
    return null;
  });
  const [selectedDistrictCode, setSelectedDistrictCode] = useState(
    user?.regionCode ?? "",
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  if (!user) return null;

  const isFirstSetup = !user.regionCode;
  const selectedDistrict =
    selectedProvince?.districts.find((d) => d.code === selectedDistrictCode) ??
    null;

  function onSaved(updated: User) {
    setUser(updated);
    navigate("/home");
  }

  async function handleSave() {
    if (!selectedProvince || !selectedDistrictCode) {
      setError("시/도와 시/군/구를 모두 선택해 주세요");
      return;
    }
    setError("");
    setLoading(true);
    try {
      const regionName = `${selectedProvince.name} ${selectedDistrict?.name ?? ""}`;
      await updateUserRegion({ regionCode: selectedDistrictCode, regionName });
      const updated: User = {
        ...user!,
        regionCode: selectedDistrictCode,
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
              value={selectedProvince?.code ?? ""}
              onChange={(e) => {
                const found = PROVINCES.find((p) => p.code === e.target.value);
                setSelectedProvince(found ?? null);
                setSelectedDistrictCode("");
                setError("");
              }}
              className="w-full appearance-none px-4 py-4 rounded-xl border border-border bg-card text-foreground text-base focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-all"
            >
              <option value="">시/도 선택</option>
              {PROVINCES.map((p) => (
                <option key={p.code} value={p.code}>
                  {p.name}
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
              value={selectedDistrictCode}
              onChange={(e) => {
                setSelectedDistrictCode(e.target.value);
                setError("");
              }}
              disabled={!selectedProvince}
              className="w-full appearance-none px-4 py-4 rounded-xl border border-border bg-card text-foreground text-base focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-all disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <option value="">
                {selectedProvince ? "시/군/구 선택" : "먼저 시/도를 선택하세요"}
              </option>
              {selectedProvince?.districts.map((d) => (
                <option key={d.code} value={d.code}>
                  {d.name}
                </option>
              ))}
            </select>
            <div className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2">
              <ChevronIcon />
            </div>
          </div>
        </div>

        {/* Preview */}
        {selectedProvince && selectedDistrict && (
          <div className="flex items-center gap-3 px-4 py-3.5 bg-accent rounded-xl border border-accent-foreground/10">
            <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center text-primary flex-shrink-0">
              <MapPinIcon />
            </div>
            <div>
              <p className="text-xs text-muted-foreground">선택된 지역</p>
              <p className="text-sm font-semibold text-foreground">
                {selectedProvince.name} {selectedDistrict.name}
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
          onClick={handleSave}
          disabled={loading || !selectedProvince || !selectedDistrictCode}
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
