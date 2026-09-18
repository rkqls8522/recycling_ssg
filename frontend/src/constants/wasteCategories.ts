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
  { classId: 1, majorCategory: "고철류", minorCategory: "골프채" },
  { classId: 2, majorCategory: "고철류", minorCategory: "기타" },
  { classId: 3, majorCategory: "고철류", minorCategory: "비철금속" },
  { classId: 4, majorCategory: "고철류", minorCategory: "전기프라이팬" },
  { classId: 5, majorCategory: "고철류", minorCategory: "주전자" },
  { classId: 6, majorCategory: "고철류", minorCategory: "철옷걸이" },
  { classId: 7, majorCategory: "고철류", minorCategory: "프라이팬" },
  { classId: 8, majorCategory: "나무", minorCategory: "기타" },
  { classId: 9, majorCategory: "나무", minorCategory: "나무행거" },
  { classId: 10, majorCategory: "나무", minorCategory: "도마" },
  { classId: 11, majorCategory: "나무", minorCategory: "액자" },
  { classId: 12, majorCategory: "나무", minorCategory: "장식품" },
  { classId: 13, majorCategory: "나무", minorCategory: "주걱" },
  { classId: 14, majorCategory: "나무", minorCategory: "주방용품" },
  { classId: 15, majorCategory: "나무", minorCategory: "포장재" },
  { classId: 16, majorCategory: "도기류", minorCategory: "그릇류" },
  { classId: 17, majorCategory: "도기류", minorCategory: "기타" },
  { classId: 18, majorCategory: "도기류", minorCategory: "뚝배기" },
  { classId: 19, majorCategory: "도기류", minorCategory: "받침" },
  { classId: 20, majorCategory: "도기류", minorCategory: "병" },
  { classId: 21, majorCategory: "도기류", minorCategory: "장식품" },
  { classId: 22, majorCategory: "도기류", minorCategory: "주전자" },
  { classId: 23, majorCategory: "도기류", minorCategory: "컵" },
  { classId: 24, majorCategory: "도기류", minorCategory: "항아리" },
  { classId: 25, majorCategory: "도기류", minorCategory: "화분" },
  { classId: 26, majorCategory: "비닐", minorCategory: "과자봉지" },
  { classId: 27, majorCategory: "비닐", minorCategory: "기타" },
  { classId: 28, majorCategory: "비닐", minorCategory: "리필용기" },
  { classId: 29, majorCategory: "비닐", minorCategory: "봉투" },
  { classId: 30, majorCategory: "비닐", minorCategory: "에어캡" },
  { classId: 31, majorCategory: "비닐", minorCategory: "일회용덮개" },
  { classId: 32, majorCategory: "비닐", minorCategory: "포장제" },
  { classId: 33, majorCategory: "스티로폼", minorCategory: "네모트레이" },
  { classId: 34, majorCategory: "스티로폼", minorCategory: "보호재" },
  { classId: 35, majorCategory: "스티로폼", minorCategory: "스티로폼" },
  { classId: 36, majorCategory: "스티로폼", minorCategory: "포장용기" },
  { classId: 37, majorCategory: "유리병", minorCategory: "기타" },
  { classId: 38, majorCategory: "유리병", minorCategory: "기타술병" },
  { classId: 39, majorCategory: "유리병", minorCategory: "맥주병" },
  { classId: 40, majorCategory: "유리병", minorCategory: "물병" },
  { classId: 41, majorCategory: "유리병", minorCategory: "박카스병" },
  { classId: 42, majorCategory: "유리병", minorCategory: "소주병" },
  { classId: 43, majorCategory: "유리병", minorCategory: "음료수병" },
  { classId: 44, majorCategory: "유리병", minorCategory: "주방용기" },
  { classId: 45, majorCategory: "의류", minorCategory: "기타" },
  { classId: 46, majorCategory: "의류", minorCategory: "기타의류" },
  { classId: 47, majorCategory: "의류", minorCategory: "레깅스" },
  { classId: 48, majorCategory: "의류", minorCategory: "면의류" },
  { classId: 49, majorCategory: "의류", minorCategory: "상의" },
  { classId: 50, majorCategory: "의류", minorCategory: "외투" },
  { classId: 51, majorCategory: "의류", minorCategory: "원피스" },
  { classId: 52, majorCategory: "의류", minorCategory: "하의" },
  { classId: 53, majorCategory: "의류", minorCategory: "합성섬유" },
  { classId: 54, majorCategory: "종이류", minorCategory: "기타" },
  { classId: 55, majorCategory: "종이류", minorCategory: "노트" },
  { classId: 56, majorCategory: "종이류", minorCategory: "상자류" },
  { classId: 57, majorCategory: "종이류", minorCategory: "신문지" },
  { classId: 58, majorCategory: "종이류", minorCategory: "신발상자" },
  { classId: 59, majorCategory: "종이류", minorCategory: "음료수곽" },
  { classId: 60, majorCategory: "종이류", minorCategory: "종이봉투" },
  { classId: 61, majorCategory: "종이류", minorCategory: "책자" },
  { classId: 62, majorCategory: "종이류", minorCategory: "포장상자" },
  { classId: 63, majorCategory: "캔류", minorCategory: "기타" },
  { classId: 64, majorCategory: "캔류", minorCategory: "맥주캔" },
  { classId: 65, majorCategory: "캔류", minorCategory: "스팸류" },
  { classId: 66, majorCategory: "캔류", minorCategory: "음료수캔" },
  { classId: 67, majorCategory: "캔류", minorCategory: "참기름캔" },
  { classId: 68, majorCategory: "캔류", minorCategory: "커피캔" },
  { classId: 69, majorCategory: "캔류", minorCategory: "통조림캔" },
  { classId: 70, majorCategory: "페트병", minorCategory: "기타" },
  { classId: 71, majorCategory: "페트병", minorCategory: "일회용음료수잔" },
  { classId: 72, majorCategory: "페트병", minorCategory: "페트병" },
  { classId: 73, majorCategory: "플라스틱류", minorCategory: "기타" },
  { classId: 74, majorCategory: "플라스틱류", minorCategory: "대용량플라스틱통" },
  { classId: 75, majorCategory: "플라스틱류", minorCategory: "밀폐용기" },
  { classId: 76, majorCategory: "플라스틱류", minorCategory: "바구니" },
  { classId: 77, majorCategory: "플라스틱류", minorCategory: "욕실용품" },
  { classId: 78, majorCategory: "플라스틱류", minorCategory: "장난감" },
  { classId: 79, majorCategory: "형광등", minorCategory: "LED전구" },
  { classId: 80, majorCategory: "형광등", minorCategory: "기타" },
  { classId: 81, majorCategory: "형광등", minorCategory: "백열전구" },
  { classId: 82, majorCategory: "형광등", minorCategory: "안정기내장형" },
  { classId: 83, majorCategory: "형광등", minorCategory: "직관형" },
  { classId: 84, majorCategory: "형광등", minorCategory: "콤팩트형" },
  { classId: 85, majorCategory: "형광등", minorCategory: "환형" },
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
