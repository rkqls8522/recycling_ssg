// 폐기물 분류 체계 (class_id ↔ 대분류/소분류).
// 백엔드 data/taxonomy/waste_classes.json과 동일한 소스에서 생성 — 값을 바꿀 땐
// 백엔드 taxonomy와 어긋나지 않도록 함께 맞춰야 한다.
export interface WasteClass {
  classId: number;
  majorCategory: string;
  minorCategory: string;
}

export const WASTE_CLASSES: WasteClass[] = [
  { classId: 0, majorCategory: "고철류", minorCategory: "고철" },
  { classId: 1, majorCategory: "고철류", minorCategory: "비철금속" },
  { classId: 2, majorCategory: "나무", minorCategory: "나무" },
  { classId: 3, majorCategory: "도기류", minorCategory: "도기" },
  { classId: 4, majorCategory: "비닐", minorCategory: "비닐" },
  { classId: 5, majorCategory: "스티로폼", minorCategory: "스티로폼" },
  { classId: 6, majorCategory: "유리병", minorCategory: "유리병" },
  { classId: 7, majorCategory: "의류", minorCategory: "의류" },
  { classId: 8, majorCategory: "종이류", minorCategory: "책" },
  { classId: 9, majorCategory: "종이류", minorCategory: "박스류" },
  { classId: 10, majorCategory: "종이류", minorCategory: "신문지" },
  { classId: 11, majorCategory: "종이류", minorCategory: "종이" },
  { classId: 12, majorCategory: "캔류", minorCategory: "캔" },
  { classId: 13, majorCategory: "페트병", minorCategory: "페트병" },
  { classId: 14, majorCategory: "플라스틱류", minorCategory: "플라스틱" },
  { classId: 15, majorCategory: "플라스틱류", minorCategory: "장난감" },
  { classId: 16, majorCategory: "형광등", minorCategory: "형광등" },
];

// 대분류 → 소분류 목록 — FavoriteModal 셀렉트 옵션에 사용 (WASTE_CLASSES 등장 순서 유지)
export const CATEGORIES: Record<string, string[]> = WASTE_CLASSES.reduce(
  (acc, { majorCategory, minorCategory }) => {
    (acc[majorCategory] ??= []).push(minorCategory);
    return acc;
  },
  {} as Record<string, string[]>,
);

// 대분류 목록 (등장 순서 유지)
export const MAJOR_CATEGORIES = Object.keys(CATEGORIES);

// 대분류 + 소분류 조합으로 class_id를 찾는다. 일치하는 항목이 없으면 undefined.
export function getClassId(
  majorCategory: string,
  minorCategory: string,
): number | undefined {
  return WASTE_CLASSES.find(
    (c) => c.majorCategory === majorCategory && c.minorCategory === minorCategory,
  )?.classId;
}
