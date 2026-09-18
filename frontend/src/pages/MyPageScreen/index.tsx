import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  AddIcon,
  ChevronRightIcon,
  ModifyIcon,
} from "@/components/common/Icons";
import { useAuthContext } from "../AuthScreen/AuthContext";
import { useMypage } from "./useMypage";
import BackButton from "../../components/common/BackButton";
import { useFavorite, CATEGORY_EMOJI, CATEGORY_COLOR } from "./useFavorite";
import { FavoriteModal } from "./FavoriteModal";

export default function MyPageScreen() {
  const { user } = useAuthContext();
  const navigate = useNavigate();
  const [editingName, setEditingName] = useState(false);
  const [name, setName] = useState(user?.email.split("@")[0] ?? "");

  const MOCK_POINTS = 1024;

  const { favorites, favoritesLoading, loadFavorites, logout } = useMypage();
  const {
    openModal,
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
    handleDelete,
    deleteLoading,
    alreadyRegistered,
  } = useFavorite(
    loadFavorites,
    favorites?.items.map((item) => item.class_id),
  );

  const favoritesUpdating = favoritesLoading;

  if (!user) return null;

  function handleChangeRegion() {
    navigate("/region");
  }

  useEffect(() => {
    loadFavorites();
  }, []);

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
          <button className="btn btn-xs btn-ghost" onClick={logout}>
            <div className="text-sm text-white">로그아웃</div>
          </button>
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
            <div className="flex justify-between items-center">
              <p className="text-xs text-muted-foreground mt-1 leading-relaxed">
                자주 배출하는데 방법이 헷갈리는 품목을 등록해 두세요.
              </p>
              <button
                onClick={openModal}
                className="w-7 h-7 rounded-lg bg-primary flex items-center justify-center flex-shrink-0 active:scale-90 transition-transform mt-0.5 cursor-pointer"
                aria-label="품목 추가"
              >
                <AddIcon />
              </button>
            </div>
          </div>
          <div className="flex flex-col">
            {favoritesUpdating
              ? [0, 1, 2].map((i) => (
                  <div
                    key={i}
                    className="flex items-center gap-3 px-4 py-3.5 animate-pulse"
                  >
                    <div className="flex-1 min-w-0 flex justify-between items-center">
                      <div className="flex items-center gap-2">
                        <span className="w-12 h-4 rounded-full bg-muted" />
                        <span className="w-24 h-4 rounded bg-muted" />
                      </div>
                      <span className="w-3 h-3 rounded bg-muted" />
                    </div>
                  </div>
                ))
              : favorites?.items.map((item) => {
                  return (
                    <div
                      key={item.favorite_id}
                      className={"flex items-center gap-3 px-4 py-3.5"}
                    >
                      <div className="flex-1 min-w-0 flex justify-between">
                        <div className="flex items-center gap-2 mb-1">
                          <span
                            className={`text-[9px] font-semibold px-1.5 py-0.5 rounded-full flex-shrink-0 ${
                              CATEGORY_COLOR[item.major_category] ??
                              "bg-muted text-muted-foreground"
                            }`}
                          >
                            {CATEGORY_EMOJI[item.major_category] ?? ""}{" "}
                            {item.major_category}
                          </span>
                          <p className="text-sm font-semibold text-foreground truncate">
                            {item.minor_category}
                          </p>
                        </div>
                        <button
                          className="cursor-pointer btn btn-ghost btn-xs text-gray-400"
                          onClick={() => handleDelete(item.favorite_id)}
                          disabled={deleteLoading}
                        >
                          x
                        </button>
                      </div>
                    </div>
                  );
                })}
            <FavoriteModal
              modalOpen={modalOpen}
              setModalOpen={setModalOpen}
              mainCategories={mainCategories}
              subCategories={subCategories}
              selectedMain={selectedMain}
              setSelectedMain={setSelectedMain}
              selectedSub={selectedSub}
              setSelectedSub={setSelectedSub}
              handleAdd={handleAdd}
              addLoading={addLoading}
              alreadyRegistered={alreadyRegistered}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
