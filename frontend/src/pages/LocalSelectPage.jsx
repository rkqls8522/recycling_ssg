import { useState } from "react";
import Header from "../components/common/Header";
import { SelectInput } from "../components/common/Input";
import MobileLayout from "../components/layout/MobileLayout";
import Button from "../components/common/Button";

function LocalSelectPage() {
  // 선택한 지역 저장
  const [city, setCity] = useState("");
  const [district, setDistrict] = useState("");

  // 지역 데이터
  const regionData = {
    서울특별시: ["마포구", "강남구", "종로구", "양천구", "관악구"],
    경기도: ["수원시", "성남시", "용인시", "안양시", "화성시"],
  };

  return (
    <MobileLayout>
      {/* 상단 헤더 */}
      <Header
        title="지역을 선택해 주세요"
        subtitle={
          <p>
            선택한 지역의 분리배출 기준으로 안내해 드립니다.
            <br />
            한 번 설정하면 다음 방문 시 자동 적용됩니다.
          </p>
        }
      />

      {/* 지역 선택 */}
      <div className="px-5 mt-6 flex flex-col gap-4">
        <SelectInput
          label="시 / 도"
          value={city}
          onChange={(e) => {
            setCity(e.target.value);
            setDistrict("");
          }}
          options={["서울특별시", "경기도", "부산광역시"]}
        />

        <SelectInput
          label="시 / 군 / 구"
          value={district}
          onChange={(e) => setDistrict(e.target.value)}
          options={regionData[city] || []}
          disabled={!city}
        />
      </div>

      {/* 선택된 지역 */}
      <div className="px-5 flex flex-col gap-4">
        {city && district && (
          <div className="flex items-center gap-5 rounded-xl border border-[#BFE8CF] bg-[#D9F3E3] px-4 py-4 mt-4">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#BFE8CF]">
              📍
            </div>

            <div>
              <p className="text-xs text-gray-500">
                선택된 지역
              </p>

              <p className="text-sm font-bold text-black">
                {city} {district}
              </p>
            </div>
          </div>
        )}

        {/* 안내 문구 */}
        <div className="flex items-center gap-5 rounded-xl bg-[#f2f2f2] px-4 py-4 mt-5">
          <p className="text-xs text-gray-500">
            현재 샘플 데이터로 제공:{" "}
            <strong>서울특별시, 경기도, 부산광역시</strong>
          </p>
        </div>
      </div>

      {/* 하단 고정 버튼 */}
      <div className="absolute bottom-8 left-0 w-full px-5">
        <Button disabled={!city || !district}>
          이 지역으로 설정하기
        </Button>
      </div>
    </MobileLayout>
  );
}

export default LocalSelectPage;