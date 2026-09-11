import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuthContext } from "../AuthScreen/AuthContext";
import BackButton from "../../components/common/BackButton";
import { ChevronRightIcon, ModifyIcon } from "@/components/common/Icons";

const MOCK_HISTORY = [
  {
    itemName: "투명 페트병",
    itemCategory: "플라스틱류",
    emoji: "🍶",
    tip: "라벨 제거 후 압착 → 투명 페트 전용함",
  },
  {
    itemName: "알루미늄 캔",
    itemCategory: "금속류",
    emoji: "🥤",
    tip: "내용물 비우고 찌그러트려 → 금속류 수거함",
  },
  {
    itemName: "종이팩",
    itemCategory: "종이류",
    emoji: "🥛",
    tip: "헹군 뒤 납작하게 펴서 → 종이팩 전용함",
  },
  {
    itemName: "스티로폼",
    itemCategory: "스티로폼류",
    emoji: "📦",
    tip: "테이프·스티커 모두 제거 → 스티로폼 전용함",
  },
  {
    itemName: "유리병",
    itemCategory: "유리류",
    emoji: "🍾",
    tip: "뚜껑 분리 후 헹궈서 → 유리류 수거함",
  },
];

const MOCK_POINTS = 1_240;

const CATEGORY_COLOR: Record<string, string> = {
  플라스틱류: "bg-blue-100 text-blue-700",
  금속류: "bg-slate-100 text-slate-700",
  "종이류 (종이팩)": "bg-yellow-100 text-yellow-700",
  스티로폼류: "bg-orange-100 text-orange-700",
  유리류: "bg-cyan-100 text-cyan-700",
};

export default function MyPageScreen() {
  const { user } = useAuthContext();
  const navigate = useNavigate();
  const [editingName, setEditingName] = useState(false);
  const [name, setName] = useState(user?.email.split("@")[0] ?? "");

  if (!user) return null;

  function handleChangeRegion() {
    navigate("/region");
  }

  return (
    <div className="flex flex-col h-full bg-muted">
      {/* Header */}
      <div className="bg-primary text-primary-foreground px-5 pt-12 pb-6">
        <div className="flex items-center gap-3 mb-6">
          <BackButton onClick={() => navigate("/home")} ariaLabel="뒤로 가기" />
          <h1 className="text-base font-bold flex-1">마이페이지</h1>
        </div>

        {/* Profile */}
        <div className="flex items-center gap-4">
          <div className="w-16 h-16 rounded-2xl bg-primary-foreground/15 flex items-center justify-center flex-shrink-0">
            <span className="text-2xl font-bold text-primary-foreground">
              {name.charAt(0).toUpperCase()}
            </span>
          </div>
          <div className="flex-1 min-w-0">
            {editingName ? (
              <input
                autoFocus
                value={name}
                onChange={(e) => setName(e.target.value)}
                onBlur={() => setEditingName(false)}
                onKeyDown={(e) => e.key === "Enter" && setEditingName(false)}
                className="text-lg font-bold bg-primary-foreground/10 text-primary-foreground rounded-lg px-2 py-0.5 w-full outline-none border border-primary-foreground/30"
              />
            ) : (
              <div className="flex items-center gap-2">
                <p className="text-lg font-bold text-primary-foreground truncate">
                  {name}
                </p>
                <button
                  onClick={() => setEditingName(true)}
                  className="opacity-60 active:opacity-100 transition-opacity flex-shrink-0"
                  aria-label="이름 수정"
                >
                  <ModifyIcon />
                </button>
              </div>
            )}
            <p className="text-xs text-primary-foreground/60 mt-0.5 truncate">
              {user.email}
            </p>
          </div>
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto no-scrollbar px-4 py-4 flex flex-col gap-3">
        {/* Points + total */}
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-background rounded-2xl p-4 border border-border flex flex-col gap-1">
            <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
              포인트
            </p>
            <p className="text-2xl font-bold text-primary font-mono">
              {MOCK_POINTS.toLocaleString()} P
            </p>
          </div>
          <div className="bg-background rounded-2xl p-4 border border-border flex flex-col gap-1">
            <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
              지역 정보
            </p>
            <button
              onClick={handleChangeRegion}
              className="w-full flex items-center gap-3 py-2 active:bg-muted transition-colors"
            >
              <p className="text-sm font-semibold text-foreground">
                {user.regionName || "지역 미설정"}
              </p>

              <ChevronRightIcon />
            </button>
          </div>
        </div>

        {/* Frequently disposed */}
        <div className="bg-background rounded-2xl border border-border overflow-hidden">
          <div className="px-4 py-3 border-b border-border">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              자주 배출하는 품목
            </p>
            <p className="text-xs text-muted-foreground mt-1 leading-relaxed">
              자주 배출하는데 방법이 헷갈리는 품목을 등록해 두세요.
            </p>
          </div>
          <div className="flex flex-col">
            {MOCK_HISTORY.map((item, i) => {
              const color =
                CATEGORY_COLOR[item.itemCategory] ??
                "bg-muted text-muted-foreground";
              return (
                <div
                  key={item.itemName}
                  className={`flex items-center gap-3 px-4 py-3.5 ${i < MOCK_HISTORY.length - 1 ? "border-b border-border" : ""}`}
                >
                  <span className="text-xl flex-shrink-0 w-7 text-center">
                    {item.emoji}
                  </span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <p className="text-sm font-semibold text-foreground truncate">
                        {item.itemName}
                      </p>
                      <span
                        className={`text-[9px] font-semibold px-1.5 py-0.5 rounded-full flex-shrink-0 ${color}`}
                      >
                        {item.itemCategory}
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground leading-snug">
                      {item.tip}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <p className="text-center text-[10px] text-muted-foreground pb-2">
          분리쏙 v0.1.0 · 목업 데이터 기준
        </p>
      </div>
    </div>
  );
}
