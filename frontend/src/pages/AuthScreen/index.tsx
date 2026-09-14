import { useEffect, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import type { AxiosError } from "axios";
import { v4 as uuidv4 } from "uuid";
import type { AuthMode } from "../../types";
import type {
  SignupPayload,
  SignupResponse,
  LoginResponse,
  ApiErrorBody,
  User,
} from "../../types/index";
import { saveToken, saveUser } from "../../utils/storage";
import { LoadingIcon, RecycleIcon } from "../../components/common/Icons";
import { useAuthContext, resolveHomeRoute } from "./AuthContext";
import useAxios from "../../hooks/useAxios";

// 로그인 응답에만 access_token이 있으므로 이걸로 구분한다.
function isLoginResponse(
  data: LoginResponse | SignupResponse,
): data is LoginResponse {
  return "access_token" in data;
}

// 백엔드의 {user_id, email, region} 형태를 화면에서 쓰는 User로 변환.
// region_id 체계는 아직 화면 쪽에서 문자열 code로 다루고 있어 임시로 문자열화한다.
function mapUser(apiUser: LoginResponse["user"]): User {
  return {
    id: String(apiUser.user_id),
    email: apiUser.email,
    regionCode: apiUser.region ? String(apiUser.region.region_id) : undefined,
    regionName: apiUser.region
      ? `${apiUser.region.sido_name} ${apiUser.region.sgg_name}`
      : undefined,
  };
}

export default function AuthScreen() {
  const { user, setUser } = useAuthContext();
  const navigate = useNavigate();
  const [mode, setMode] = useState<AuthMode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [formError, setFormError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");

  const { loading, refetch: authRequest } = useAxios<
    LoginResponse | SignupResponse
  >("", { method: "post" }, false);

  if (user) {
    // return <Navigate to={resolveHomeRoute(user)} replace />;
  }

  function resetForm() {
    setEmail("");
    setPassword("");
    setConfirm("");
    setMode("login");
    setFormError("");
    setSuccessMessage("");
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFormError("");
    setSuccessMessage("");

    if (!email.trim() || !password.trim()) {
      setFormError("이메일과 비밀번호를 입력해 주세요");
      return;
    }
    if (mode === "signup" && password !== confirm) {
      setFormError("비밀번호가 일치하지 않습니다");
      return;
    }
    // 명세: password 8~72자
    if (password.length < 8 || password.length > 72) {
      setFormError("비밀번호는 8자 이상 72자 이하여야 합니다");
      return;
    }

    const endpoint =
      mode === "login" ? "/api/v1/auth/login" : "/api/v1/auth/signup";

    try {
      const payload: SignupPayload = { email: email.trim(), password };

      const data = await authRequest({
        url: endpoint,
        data: payload,
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
          "X-Request-ID": uuidv4(),
        },
      });

      if (mode === "signup") {
        // 서비스 이용은 로그인 후에만 가능 — 가입 완료 후 자동 로그인하지 않고 로그인 화면으로 전환
        setMode("login");
        setPassword("");
        setConfirm("");
        setSuccessMessage("회원가입이 완료되었습니다. 로그인해 주세요.");
        return;
      }

      if (!isLoginResponse(data)) {
        setFormError("로그인에 실패했습니다");
        return;
      }

      saveToken(data.access_token);
      const loggedInUser = mapUser(data.user);
      saveUser(loggedInUser);
      setUser(loggedInUser);
      // 지역이 설정되어 있으면 바로 촬영 화면으로, 아니면 지역 설정 화면으로 (resolveHomeRoute가 분기)
      navigate(resolveHomeRoute(loggedInUser), { replace: true });
    } catch (err) {
      const axiosErr = err as AxiosError<ApiErrorBody>;
      const body = axiosErr.response?.data;

      if (body?.code === "AUTH_EMAIL_EXISTS") {
        setFormError("이미 가입된 이메일입니다.");
      } else if (body?.code === "REQUEST_VALIDATION_ERROR" && body.details) {
        // 필드별 에러 메시지 중 첫 번째만 표시 (원하면 전체 목록으로 확장 가능)
        setFormError(body.details[0]?.message ?? body.message);
      } else if (body?.message) {
        setFormError(body.message);
      } else {
        setFormError("오류가 발생했습니다");
      }
    }
  }

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
