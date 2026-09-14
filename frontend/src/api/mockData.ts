import type { Province, DisposalGuideline } from "../types";

export const CATEGORY_COLOR: Record<string, string> = {
  플라스틱류: "bg-blue-100 text-blue-700",
  유리류: "bg-cyan-100 text-cyan-700",
  금속류: "bg-slate-100 text-slate-700",
  "종이류 (종이팩)": "bg-yellow-100 text-yellow-700",
  스티로폼류: "bg-orange-100 text-orange-700",
};

export const DEMO_IMAGE =
  "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='400' height='400'%3E%3Crect width='400' height='400' fill='%23f3f4f6'/%3E%3Ctext x='200' y='200' text-anchor='middle' dy='.3em' fill='%239ca3af' font-size='18' font-family='sans-serif'%3E샘플 이미지%3C/text%3E%3C/svg%3E";

export type WasteKey =
  | "transparent_pet"
  | "glass_bottle"
  | "aluminum_can"
  | "paper_carton"
  | "styrofoam"
  | "paper"
  | "plastic_container";

export interface WasteItem {
  itemName: string;
  itemCategory: string;
  itemCategoryEn: WasteKey;
  baseConfidence: number;
  guidelines: Record<string, DisposalGuideline>;
  defaultGuideline: DisposalGuideline;
}

const defaultSourceByCode = (
  regionCode: string,
): { source: string; sourceUrl: string } => {
  if (regionCode.startsWith("11440"))
    return {
      source: "마포구청 분리배출 안내 (2024)",
      sourceUrl: "https://www.mapo.go.kr",
    };
  if (regionCode.startsWith("11680"))
    return {
      source: "강남구청 분리배출 안내 (2024)",
      sourceUrl: "https://www.gangnam.go.kr",
    };
  if (regionCode.startsWith("11"))
    return {
      source: "서울특별시 자원순환과 (2024)",
      sourceUrl: "https://news.seoul.go.kr/env",
    };
  if (regionCode.startsWith("41111"))
    return {
      source: "수원시 자원순환과 분리배출 지침 (2024)",
      sourceUrl: "https://www.suwon.go.kr",
    };
  if (regionCode.startsWith("41"))
    return {
      source: "경기도 환경국 분리배출 안내 (2024)",
      sourceUrl: "https://www.gg.go.kr",
    };
  if (regionCode.startsWith("26350"))
    return {
      source: "해운대구청 생활폐기물 분리배출 지침 (2024)",
      sourceUrl: "https://www.haeundae.go.kr",
    };
  if (regionCode.startsWith("26"))
    return {
      source: "부산광역시 환경정책과 (2024)",
      sourceUrl: "https://www.busan.go.kr",
    };
  return {
    source: "환경부 분리배출 가이드라인 (2024)",
    sourceUrl: "https://www.me.go.kr",
  };
};

export function getGuidelineForRegion(
  item: WasteItem,
  regionCode: string,
): DisposalGuideline {
  if (item.guidelines[regionCode]) {
    return item.guidelines[regionCode];
  }
  // Try province-level fallback
  const provinceCode = regionCode.slice(0, 2);
  const provinceMatch = Object.keys(item.guidelines).find((k) =>
    k.startsWith(provinceCode),
  );
  if (provinceMatch) {
    return item.guidelines[provinceMatch];
  }
  const { source, sourceUrl } = defaultSourceByCode(regionCode);
  return { ...item.defaultGuideline, source, sourceUrl };
}
