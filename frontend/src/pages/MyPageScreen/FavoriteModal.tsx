import { ChevronDownIcon } from "@/components/common/Icons";

interface Props {
  modalOpen: boolean;
  setModalOpen: (open: boolean) => void;
  mainCategories: string[];
  subCategories: string[];
  selectedMain: string;
  setSelectedMain: (value: string) => void;
  selectedSub: string;
  setSelectedSub: (value: string) => void;
  handleAdd: () => void;
  addLoading: boolean;
  alreadyRegistered: boolean;
}

export function FavoriteModal({
  modalOpen,
  setModalOpen,
  mainCategories,
  subCategories,
  selectedMain,
  setSelectedMain,
  selectedSub,
  setSelectedSub,
  handleAdd,
  addLoading,
  alreadyRegistered,
}: Props) {
  if (!modalOpen) return null;

  return (
    <>
      {/* 배경 오버레이 */}
      <div
        className="absolute inset-0 z-20 bg-black/40"
        onClick={() => setModalOpen(false)}
      />
      {/* 모달 콘텐츠 */}
      {modalOpen && (
        <div className="absolute bottom-0 left-0 right-0 z-30 rounded-t-3xl bg-background shadow-2xl animate-fade-in-up">
          <div className="flex justify-center pb-1 pt-3">
            <div className="h-1 w-10 rounded-full bg-border" />
          </div>

          <div className="border-b border-border px-5 pb-3 pt-4">
            <p className="text-base font-bold text-foreground">품목 추가</p>
            <p className="mt-0.5 text-xs text-muted-foreground">
              대분류와 소분류를 선택해 주세요
            </p>
          </div>

          <div className="flex flex-col gap-3 px-5 pb-4 pt-5">
            {/* 대분류 */}
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-semibold text-muted-foreground">
                대분류
              </label>
              <div className="relative flex items-center">
                <select
                  value={selectedMain}
                  onChange={(e) => {
                    setSelectedMain(e.target.value);
                    setSelectedSub("");
                  }}
                  className="w-full appearance-none bg-muted border border-border rounded-xl px-4 py-3 text-sm font-medium text-foreground pr-9 outline-none focus:border-primary transition-colors"
                >
                  <option value="">선택하세요</option>
                  {mainCategories.map((cat) => (
                    <option key={cat} value={cat}>
                      {cat}
                    </option>
                  ))}
                </select>
                <ChevronDownIcon />
              </div>
            </div>

            {/* 소분류 */}
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-semibold text-muted-foreground">
                소분류
              </label>
              <div className="relative flex items-center">
                <select
                  value={selectedSub}
                  onChange={(e) => setSelectedSub(e.target.value)}
                  disabled={!selectedMain}
                  className="w-full appearance-none rounded-xl border border-border bg-muted px-4 py-3 pr-9 text-sm font-medium text-foreground outline-none transition-colors disabled:opacity-40 focus:border-primary"
                >
                  <option value="">
                    {selectedMain ? "선택하세요" : "대분류를 먼저 선택하세요"}
                  </option>
                  {subCategories.map((sub) => (
                    <option key={sub} value={sub}>
                      {sub}
                    </option>
                  ))}
                </select>
                <ChevronDownIcon />
              </div>
            </div>

            {alreadyRegistered && (
              <div role="alert" className="alert alert-success alert-soft">
                <span>이미 즐겨찾기에 등록된 품목이에요.</span>
              </div>
            )}

            {/* 추가 버튼 */}
            <button
              onClick={handleAdd}
              disabled={!selectedMain || !selectedSub || alreadyRegistered}
              className="mt-1 w-full rounded-2xl bg-primary py-3.5 text-sm font-semibold text-primary-foreground transition-all active:scale-[0.98] disabled:opacity-40"
            >
              {addLoading ? (
                <span className="loading loading-spinner loading-sm" />
              ) : (
                "추가하기"
              )}
            </button>
          </div>
        </div>
      )}
    </>
  );
}
