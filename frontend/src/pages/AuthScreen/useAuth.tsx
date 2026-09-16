import { useState } from "react";
import useAxios from "@/hooks/useAxios";
import {
  ApiErrorBody,
  AuthMode,
  LoginResponse,
  SignupPayload,
  SignupResponse,
  User,
} from "@/types";
import { apiHeaders } from "@/utils/header";
import { saveToken, saveUser } from "@/utils/storage";
import { useNavigate } from "react-router-dom";
import { resolveHomeRoute, useAuthContext } from "./AuthContext";
import { AxiosError } from "axios";

export function useAuth() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [formError, setFormError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [mode, setMode] = useState<AuthMode>("login");
  const { user, setUser } = useAuthContext();

  const { loading, refetch: authRequest } = useAxios<
    LoginResponse | SignupResponse
  >("", { method: "post" }, false);

  const navigate = useNavigate();

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

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFormError("");
    setSuccessMessage("");

    if (!email.trim() || !password.trim()) {
      console.log(email, password);
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
        headers: apiHeaders(),
      });

      if (mode === "signup") {
        // 서비스 이용은 로그인 후에만 가능 — 가입 완료 후 자동 로그인하지 않고 로그인 화면으로 전환
        setMode("login");
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

  function resetForm() {
    setEmail("");
    setPassword("");
    setConfirm("");
    setMode("login");
    setFormError("");
    setSuccessMessage("");
  }

  return {
    handleSubmit,
    resetForm,
    formError,
    successMessage,
    email,
    password,
    confirm,
    setEmail,
    setPassword,
    setConfirm,
    mode,
    user,
    setMode,
    setFormError,
    setSuccessMessage,
    loading,
  };
}
