import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronRightIcon, ModifyIcon } from "@/components/common/Icons";
import { useAuthContext } from "../AuthScreen/AuthContext";
import { useMypage } from "./useMypage";
import BackButton from "../../components/common/BackButton";

export default function MyPageScreen() {
  const { user } = useAuthContext();
  const navigate = useNavigate();
  const [editingName, setEditingName] = useState(false);
  const [name, setName] = useState(user?.email.split("@")[0] ?? "");

  const MOCK_POINTS = 1024;

  const { favorites, loadFavorites, logout } = useMypage();

  console.log("user", user);
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
              <p className="btn btn-xs btn-ghost">+</p>
            </div>
          </div>
          <div className="flex flex-col">
            {favorites?.items.map((item, i) => {
              return (
                <div
                  key={item.favorite_id}
                  className={"flex items-center gap-3 px-4 py-3.5"}
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <p className="text-sm font-semibold text-foreground truncate">
                        {item.minor_category}
                      </p>
                      <span
                        className={
                          "text-[9px] font-semibold px-1.5 py-0.5 rounded-full flex-shrink-0"
                        }
                      >
                        {item.major_category}
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground leading-snug">
                      {/* {item.tip} */}
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
