import { useEffect } from "react";
import { useAuth } from "./useAuth";
import { LoadingIcon, RecycleIcon } from "../../components/common/Icons";

export default function AuthScreen() {
  const {
    handleSubmit,
    formError,
    successMessage,
    email,
    password,
    confirm,
    resetForm,
    setEmail,
    setPassword,
    setConfirm,
    mode,
    user,
    setMode,
    setFormError,
    setSuccessMessage,
    loading,
  } = useAuth();

  if (user) {
    // return <Navigate to={resolveHomeRoute(user)} replace />;
  }

  useEffect(() => {
    setEmail("");
    setPassword("");
    setConfirm("");
  }, [mode]);

  const displayError = formError;

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
            resetForm();
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
            setFormError("");
            setSuccessMessage("");
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
            placeholder="8자 이상"
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

        {successMessage && (
          <p className="text-sm text-primary bg-green-50 px-4 py-3 rounded-lg border border-green-100">
            {successMessage}
          </p>
        )}

        {displayError && (
          <p className="text-sm text-destructive bg-red-50 px-4 py-3 rounded-lg border border-red-100">
            {displayError}
          </p>
        )}

        <button
          type="submit"
          disabled={loading}
          className="w-full py-4 mt-2 bg-primary text-primary-foreground rounded-xl font-semibold text-base shadow-sm active:scale-[0.98] transition-all disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {loading ? (
            <span className="flex items-center justify-center gap-2">
              <LoadingIcon />
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
