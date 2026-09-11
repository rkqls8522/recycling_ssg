import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import type { AuthMode } from "../../types";
import { login, signup } from "../../api/api";
import { getUser } from "../../utils/storage";
import { RecycleIcon } from "../../components/common/Icons";
import { useAuthContext, resolveHomeRoute } from "./AuthContext";

export default function AuthScreen() {
  const { user, setUser } = useAuthContext();
  const navigate = useNavigate();
  const [mode, setMode] = useState<AuthMode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  if (user) {
    return <Navigate to={resolveHomeRoute(user)} replace />;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");

    if (!email.trim() || !password.trim()) {
      setError("이메일과 비밀번호를 입력해 주세요");
      return;
    }
    if (mode === "signup" && password !== confirm) {
      setError("비밀번호가 일치하지 않습니다");
      return;
    }
    if (password.length < 6) {
      setError("비밀번호는 6자 이상이어야 합니다");
      return;
    }

    setLoading(true);
    try {
      const fn = mode === "login" ? login : signup;
      await fn({ email: email.trim(), password });
      const loggedInUser = getUser();
      if (loggedInUser) {
        setUser(loggedInUser);
        navigate(resolveHomeRoute(loggedInUser), { replace: true });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "오류가 발생했습니다");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="h-full overflow-y-auto no-scrollbar">
      {/* Header */}
      <div className="flex flex-col items-center pt-14 pb-8 px-6">
        <div className="w-16 h-16 rounded-2xl bg-primary flex items-center justify-center mb-4 text-primary-foreground shadow-lg">
          <RecycleIcon />
        </div>
        <h1 className="text-2xl font-bold text-foreground tracking-tight">
          분리쏙
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          스마트 분리배출 가이드
        </p>
      </div>

      {/* Tab toggle */}
      <div className="flex mx-6 mb-8 rounded-xl bg-muted p-1 gap-1">
        <button
          type="button"
          onClick={() => {
            setMode("login");
            setError("");
          }}
          className={`flex-1 py-2.5 rounded-lg text-sm font-semibold transition-all ${
            mode === "login"
              ? "bg-white shadow-sm text-foreground"
              : "text-muted-foreground"
          }`}
        >
          로그인
        </button>
        <button
          type="button"
          onClick={() => {
            setMode("signup");
            setError("");
          }}
          className={`flex-1 py-2.5 rounded-lg text-sm font-semibold transition-all ${
            mode === "signup"
              ? "bg-white shadow-sm text-foreground"
              : "text-muted-foreground"
          }`}
        >
          회원가입
        </button>
      </div>

      {/* Form */}
      <form onSubmit={handleSubmit} className="px-6 flex flex-col gap-3">
        <div className="flex flex-col gap-1">
          <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
            이메일
          </label>
          <input
            type="email"
            autoComplete="email"
            placeholder="example@email.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full px-4 py-3.5 rounded-xl border border-border bg-card text-foreground text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-all"
          />
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
            비밀번호
          </label>
          <input
            type="password"
            autoComplete={
              mode === "login" ? "current-password" : "new-password"
            }
            placeholder="6자 이상"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full px-4 py-3.5 rounded-xl border border-border bg-card text-foreground text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-all"
          />
        </div>

        {mode === "signup" && (
          <div className="flex flex-col gap-1">
            <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              비밀번호 확인
            </label>
            <input
              type="password"
              autoComplete="new-password"
              placeholder="비밀번호 재입력"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              className="w-full px-4 py-3.5 rounded-xl border border-border bg-card text-foreground text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-all"
            />
          </div>
        )}

        {error && (
          <p className="text-sm text-destructive bg-red-50 px-4 py-3 rounded-lg border border-red-100">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={loading}
          className="w-full py-4 mt-2 bg-primary text-primary-foreground rounded-xl font-semibold text-base shadow-sm active:scale-[0.98] transition-all disabled:opacity-60 disabled:cursor-not-allowed"
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
              처리 중...
            </span>
          ) : mode === "login" ? (
            "로그인"
          ) : (
            "회원가입"
          )}
        </button>
      </form>
    </div>
  );
}
