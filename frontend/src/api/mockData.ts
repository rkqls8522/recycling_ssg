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

export const PROVINCES: Province[] = [
  {
    code: "11",
    name: "서울특별시",
    districts: [
      { code: "11110", name: "종로구" },
      { code: "11140", name: "중구" },
      { code: "11170", name: "용산구" },
      { code: "11200", name: "성동구" },
      { code: "11215", name: "광진구" },
      { code: "11230", name: "동대문구" },
      { code: "11260", name: "중랑구" },
      { code: "11290", name: "성북구" },
      { code: "11305", name: "강북구" },
      { code: "11320", name: "도봉구" },
      { code: "11350", name: "노원구" },
      { code: "11380", name: "은평구" },
      { code: "11410", name: "서대문구" },
      { code: "11440", name: "마포구" },
      { code: "11470", name: "양천구" },
      { code: "11500", name: "강서구" },
      { code: "11530", name: "구로구" },
      { code: "11545", name: "금천구" },
      { code: "11560", name: "영등포구" },
      { code: "11590", name: "동작구" },
      { code: "11620", name: "관악구" },
      { code: "11650", name: "서초구" },
      { code: "11680", name: "강남구" },
      { code: "11710", name: "송파구" },
      { code: "11740", name: "강동구" },
    ],
  },
  {
    code: "41",
    name: "경기도",
    districts: [
      { code: "41111", name: "수원시" },
      { code: "41131", name: "성남시" },
      { code: "41150", name: "의정부시" },
      { code: "41171", name: "안양시" },
      { code: "41190", name: "부천시" },
      { code: "41210", name: "광명시" },
      { code: "41220", name: "평택시" },
      { code: "41250", name: "동두천시" },
      { code: "41271", name: "안산시" },
      { code: "41281", name: "고양시" },
      { code: "41290", name: "과천시" },
      { code: "41310", name: "구리시" },
      { code: "41360", name: "남양주시" },
      { code: "41370", name: "오산시" },
      { code: "41390", name: "시흥시" },
      { code: "41410", name: "군포시" },
      { code: "41430", name: "의왕시" },
      { code: "41450", name: "하남시" },
      { code: "41461", name: "용인시" },
      { code: "41480", name: "파주시" },
      { code: "41500", name: "이천시" },
      { code: "41550", name: "안성시" },
      { code: "41570", name: "김포시" },
      { code: "41590", name: "화성시" },
      { code: "41610", name: "광주시" },
      { code: "41630", name: "양주시" },
      { code: "41650", name: "포천시" },
      { code: "41670", name: "여주시" },
      { code: "41800", name: "연천군" },
      { code: "41820", name: "가평군" },
      { code: "41830", name: "양평군" },
    ],
  },
];

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

export const WASTE_ITEMS: WasteItem[] = [
  {
    itemName: "투명 페트병",
    itemCategory: "플라스틱류",
    itemCategoryEn: "transparent_pet",
    baseConfidence: 92,
    guidelines: {
      "11440": {
        steps: [
          "내용물을 완전히 비우고 물로 깨끗이 헹궈 주세요",
          "라벨(비닐 스티커)을 완전히 제거해 주세요",
          "뚜껑을 분리해 주세요 (뚜껑은 일반 플라스틱 수거함에 배출)",
          "찌그러트려 부피를 최소화한 후 투명 페트병 전용 수거함에 배출하세요",
        ],
        notes: [
          "투명(무색) 페트병만 전용함 배출 — 색이 있는 페트병은 플라스틱류 수거함",
          "음식물이 남은 경우 재활용 불가 → 종량제 봉투에 배출",
          "마포구 공동주택은 단지 내 전용 수거함 위치를 사전 확인 요망",
        ],
        collectionDays: "화·목·토 (주 3회)",
        source: "마포구청 분리배출 안내 (2024)",
        sourceUrl: "https://www.mapo.go.kr",
      },
      "41111": {
        steps: [
          "내용물을 비우고 물로 헹궈 주세요",
          "라벨과 뚜껑을 분리해 제거해 주세요 (뚜껑은 플라스틱류로 별도 배출)",
          "압착하여 부피를 줄여 주세요",
          "투명 페트병 전용 수거함 또는 플라스틱 혼합 수거함에 배출하세요",
        ],
        notes: [
          "수원시는 공동주택과 단독주택 배출 방법이 다를 수 있습니다",
          "단독주택은 지정 요일에 문 앞 배출",
          "음식물 오염 페트병은 종량제 봉투에 배출",
        ],
        collectionDays: "화·금 (주 2회, 단독주택 기준)",
        source: "수원시 자원순환과 분리배출 지침 (2024)",
        sourceUrl: "https://www.suwon.go.kr",
      },
      "26350": {
        steps: [
          "음료를 완전히 비운 후 물로 헹궈 주세요",
          "라벨 스티커 및 뚜껑을 분리해 주세요",
          "압축하여 부피를 줄여 주세요",
          "투명 페트병 전용 분리수거함에 넣어 주세요",
        ],
        notes: [
          "해운대구 일부 지역(좌동·우동)은 거점 수거함 이용",
          "음식물이 남은 경우 재활용 불가 → 종량제 봉투 배출",
          "색이 있는 페트병은 일반 플라스틱 수거함 배출",
        ],
        collectionDays: "월·수·금 (주 3회)",
        source: "해운대구청 생활폐기물 분리배출 지침 (2024)",
        sourceUrl: "https://www.haeundae.go.kr",
      },
    },
    defaultGuideline: {
      steps: [
        "내용물을 비우고 물로 헹궈 주세요",
        "라벨과 뚜껑을 분리해 제거해 주세요",
        "압착하여 부피를 줄여 주세요",
        "투명 페트병 전용 수거함에 배출하세요",
      ],
      notes: [
        "색이 있는 페트병은 플라스틱류 수거함 배출",
        "음식물 오염 시 종량제 봉투에 배출",
      ],
      collectionDays: "지자체별 상이 — 지역 안내문 확인 요망",
      source: "환경부 분리배출 가이드라인 (2024)",
      sourceUrl: "https://www.me.go.kr",
    },
  },
  {
    itemName: "유리병",
    itemCategory: "유리류",
    itemCategoryEn: "glass_bottle",
    baseConfidence: 88,
    guidelines: {
      "11440": {
        steps: [
          "병 안에 남은 내용물을 완전히 비워 주세요",
          "금속 뚜껑이나 플라스틱 뚜껑을 분리해 주세요 (각각 해당 분리수거함에 배출)",
          "라벨은 제거하지 않아도 됩니다",
          "깨지지 않게 주의하며 유리류 수거함에 배출하세요",
        ],
        notes: [
          "빈용기 보증금 대상 (소주·맥주 등)은 마트·편의점 반환 시 환불 가능",
          "깨진 유리병은 신문지로 감싸 종량제 봉투에 배출",
          "도자기·내열유리·크리스탈은 유리류 불가 → 종량제 봉투",
        ],
        collectionDays: "수·토 (주 2회)",
        source: "마포구청 분리배출 안내 (2024)",
        sourceUrl: "https://www.mapo.go.kr",
      },
      "41111": {
        steps: [
          "내용물을 완전히 비워 주세요",
          "뚜껑을 분리해 주세요",
          "유리병 전용 수거함에 배출하세요",
        ],
        notes: [
          "소주·맥주병 등 보증금 대상 병은 슈퍼·편의점에서 환불",
          "깨진 유리는 종이에 싸서 종량제 봉투에 배출",
          "내열유리·도자기는 재활용 불가",
        ],
        collectionDays: "수·토 (주 2회)",
        source: "수원시 자원순환과 분리배출 지침 (2024)",
        sourceUrl: "https://www.suwon.go.kr",
      },
      "26350": {
        steps: [
          "내용물을 비우고 병을 가볍게 헹궈 주세요",
          "뚜껑을 분리 배출해 주세요",
          "유리류 수거함에 세워서 배출하세요",
        ],
        notes: [
          "보증금 대상 병은 인근 마트·주류 판매점에서 환불 가능",
          "깨진 유리는 반드시 신문지나 상자에 감싸 종량제 봉투에 배출",
        ],
        collectionDays: "화·금 (주 2회)",
        source: "해운대구청 생활폐기물 분리배출 지침 (2024)",
        sourceUrl: "https://www.haeundae.go.kr",
      },
    },
    defaultGuideline: {
      steps: [
        "내용물을 완전히 비워 주세요",
        "뚜껑을 분리해 주세요",
        "유리류 수거함에 배출하세요",
      ],
      notes: [
        "보증금 대상 병은 구매처에서 환불 가능",
        "깨진 유리는 종이에 싸서 종량제 봉투에 배출",
      ],
      collectionDays: "지자체별 상이",
      source: "환경부 분리배출 가이드라인 (2024)",
      sourceUrl: "https://www.me.go.kr",
    },
  },
  {
    itemName: "알루미늄 캔",
    itemCategory: "금속류",
    itemCategoryEn: "aluminum_can",
    baseConfidence: 95,
    guidelines: {
      "11440": {
        steps: [
          "내용물을 완전히 비워 주세요",
          "물로 한 번 헹궈 주세요",
          "가능하면 찌그러트려 부피를 줄여 주세요",
          "금속류 수거함에 배출하세요",
        ],
        notes: [
          "캔 안의 내용물(음식물·음료)이 남으면 재활용 불가",
          "뚜껑이 있는 경우 함께 금속류 배출 가능",
          "도료칠이 된 캔도 금속류로 배출 가능",
        ],
        collectionDays: "화·목·토 (주 3회)",
        source: "마포구청 분리배출 안내 (2024)",
        sourceUrl: "https://www.mapo.go.kr",
      },
      "41111": {
        steps: [
          "내용물을 비우고 헹궈 주세요",
          "찌그러트려 부피를 줄여 주세요",
          "캔류 수거함에 배출하세요",
        ],
        notes: [
          "내용물 잔여 시 종량제 봉투 배출",
          "스프레이 캔은 구멍을 뚫어 가스를 완전히 제거 후 배출",
        ],
        collectionDays: "화·금 (주 2회)",
        source: "수원시 자원순환과 분리배출 지침 (2024)",
        sourceUrl: "https://www.suwon.go.kr",
      },
      "26350": {
        steps: [
          "내용물을 완전히 비워 주세요",
          "헹군 후 찌그러트려 주세요",
          "금속류 수거함에 배출하세요",
        ],
        notes: [
          "스프레이 캔은 잔여 가스를 완전 제거 후 배출",
          "부탄가스 캔은 구멍을 뚫어 환기 후 배출",
        ],
        collectionDays: "월·수·금 (주 3회)",
        source: "해운대구청 생활폐기물 분리배출 지침 (2024)",
        sourceUrl: "https://www.haeundae.go.kr",
      },
    },
    defaultGuideline: {
      steps: [
        "내용물을 비우고 헹궈 주세요",
        "찌그러트려 부피를 줄여 주세요",
        "금속류 수거함에 배출하세요",
      ],
      notes: [
        "내용물 잔여 시 재활용 불가",
        "스프레이 캔은 가스 완전 제거 후 배출",
      ],
      collectionDays: "지자체별 상이",
      source: "환경부 분리배출 가이드라인 (2024)",
      sourceUrl: "https://www.me.go.kr",
    },
  },
  {
    itemName: "종이팩",
    itemCategory: "종이류 (종이팩)",
    itemCategoryEn: "paper_carton",
    baseConfidence: 87,
    guidelines: {
      "11440": {
        steps: [
          "내용물을 완전히 비우고 물로 헹궈 주세요",
          "펼쳐서 납작하게 만들어 주세요",
          "종이팩 전용 수거함에 배출하세요 (일반 폐지 수거함과 별도)",
        ],
        notes: [
          "종이팩은 일반 종이류와 분리 배출 — 혼합 시 재활용 가치 저하",
          "마포구 일부 거점에 종이팩 전용 수거함 설치",
          "우유팩·주스팩·두유팩 모두 동일하게 처리",
        ],
        collectionDays: "수·토 (주 2회)",
        specialInstructions:
          "종이팩 전용함이 없는 경우 깨끗이 씻어 폐지류로 배출 가능",
        source: "마포구청 분리배출 안내 (2024)",
        sourceUrl: "https://www.mapo.go.kr",
      },
      "41111": {
        steps: [
          "내용물을 비우고 헹궈 주세요",
          "납작하게 펴서 종이팩 전용 수거함에 배출하세요",
        ],
        notes: [
          "종이팩은 일반 종이류와 별도 배출",
          "전용함 없을 시 깨끗이 씻어 폐지류로 배출",
        ],
        collectionDays: "수·토 (주 2회)",
        source: "수원시 자원순환과 분리배출 지침 (2024)",
        sourceUrl: "https://www.suwon.go.kr",
      },
      "26350": {
        steps: [
          "내용물을 비우고 물로 헹궈 주세요",
          "납작하게 펼쳐 주세요",
          "종이팩 전용함 또는 폐지류 수거함에 배출하세요",
        ],
        notes: [
          "종이팩 전용함 위치는 해운대구청 홈페이지 참조",
          "오염된 팩은 종량제 봉투에 배출",
        ],
        collectionDays: "화·목 (주 2회)",
        source: "해운대구청 생활폐기물 분리배출 지침 (2024)",
        sourceUrl: "https://www.haeundae.go.kr",
      },
    },
    defaultGuideline: {
      steps: [
        "내용물을 비우고 헹궈 주세요",
        "납작하게 펼쳐 주세요",
        "종이팩 전용 수거함에 배출하세요",
      ],
      notes: ["일반 종이류와 분리 배출 필요", "전용함 없을 시 폐지류로 배출"],
      collectionDays: "지자체별 상이",
      source: "환경부 분리배출 가이드라인 (2024)",
      sourceUrl: "https://www.me.go.kr",
    },
  },
  {
    itemName: "스티로폼",
    itemCategory: "스티로폼류",
    itemCategoryEn: "styrofoam",
    baseConfidence: 91,
    guidelines: {
      "11440": {
        steps: [
          "이물질(테이프·스티커·음식물)을 모두 제거해 주세요",
          "가능한 경우 작게 부숴 부피를 줄여 주세요",
          "스티로폼 전용 수거함에 배출하세요",
        ],
        notes: [
          "이물질이 묻거나 오염된 스티로폼은 재활용 불가 → 종량제 봉투",
          "은박·색이 있는 스티로폼은 재활용 불가 → 종량제 봉투",
          "마포구는 아파트 단지 내 전용 수거함 비치",
        ],
        collectionDays: "월·목 (주 2회)",
        source: "마포구청 분리배출 안내 (2024)",
        sourceUrl: "https://www.mapo.go.kr",
      },
      "41111": {
        steps: [
          "이물질·스티커를 제거해 주세요",
          "깨끗한 상태에서 스티로폼 전용 수거함에 배출하세요",
        ],
        notes: [
          "오염된 스티로폼 → 종량제 봉투",
          "색스티로폼·은박 완충재 → 종량제 봉투",
        ],
        collectionDays: "월·목 (주 2회)",
        source: "수원시 자원순환과 분리배출 지침 (2024)",
        sourceUrl: "https://www.suwon.go.kr",
      },
      "26350": {
        steps: [
          "스티커와 이물질을 제거해 주세요",
          "깨끗한 스티로폼만 전용 수거함에 배출하세요",
        ],
        notes: ["오염 시 종량제 봉투 배출", "은박·색스티로폼 → 종량제 봉투"],
        collectionDays: "화·금 (주 2회)",
        source: "해운대구청 생활폐기물 분리배출 지침 (2024)",
        sourceUrl: "https://www.haeundae.go.kr",
      },
    },
    defaultGuideline: {
      steps: [
        "이물질·스티커·음식물을 제거해 주세요",
        "작게 부숴 부피를 줄여 주세요",
        "스티로폼 전용 수거함에 배출하세요",
      ],
      notes: [
        "오염된 스티로폼은 재활용 불가",
        "색·은박 스티로폼은 종량제 봉투 배출",
      ],
      collectionDays: "지자체별 상이",
      source: "환경부 분리배출 가이드라인 (2024)",
      sourceUrl: "https://www.me.go.kr",
    },
  },
  {
    itemName: "플라스틱 용기",
    itemCategory: "플라스틱류",
    itemCategoryEn: "plastic_container",
    baseConfidence: 83,
    guidelines: {
      "11440": {
        steps: [
          "내용물을 완전히 비우고 물로 헹궈 주세요",
          "라벨을 제거해 주세요 (제거가 어려우면 그대로도 가능)",
          "플라스틱류 수거함에 배출하세요",
        ],
        notes: [
          "오염이 심한 플라스틱(기름 등)은 종량제 봉투 배출",
          "PVC 재질(창문 틀·호스 등)은 재활용 불가",
          "이물질이 끼어 세척이 어려운 경우 종량제 봉투 배출",
        ],
        collectionDays: "화·목·토 (주 3회)",
        source: "마포구청 분리배출 안내 (2024)",
        sourceUrl: "https://www.mapo.go.kr",
      },
      "41111": {
        steps: [
          "내용물을 비우고 헹궈 주세요",
          "라벨 제거 후 플라스틱류 수거함에 배출하세요",
        ],
        notes: ["기름진 용기는 세척 후 배출", "PVC 재질 불가"],
        collectionDays: "화·금 (주 2회)",
        source: "수원시 자원순환과 분리배출 지침 (2024)",
        sourceUrl: "https://www.suwon.go.kr",
      },
      "26350": {
        steps: [
          "내용물을 비우고 헹궈 주세요",
          "가능하면 라벨을 제거해 주세요",
          "플라스틱류 수거함에 배출하세요",
        ],
        notes: ["오염 심한 경우 종량제 봉투", "PVC 재질 재활용 불가"],
        collectionDays: "월·수·금 (주 3회)",
        source: "해운대구청 생활폐기물 분리배출 지침 (2024)",
        sourceUrl: "https://www.haeundae.go.kr",
      },
    },
    defaultGuideline: {
      steps: [
        "내용물을 비우고 헹궈 주세요",
        "라벨을 제거해 주세요",
        "플라스틱류 수거함에 배출하세요",
      ],
      notes: ["오염 심한 경우 종량제 봉투 배출", "PVC 재질 재활용 불가"],
      collectionDays: "지자체별 상이",
      source: "환경부 분리배출 가이드라인 (2024)",
      sourceUrl: "https://www.me.go.kr",
    },
  },
];

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

export function getRandomWasteItem(): WasteItem {
  return WASTE_ITEMS[Math.floor(Math.random() * WASTE_ITEMS.length)];
}
