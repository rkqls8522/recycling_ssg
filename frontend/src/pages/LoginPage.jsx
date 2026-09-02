import { useState } from "react";
import MobileLayout from "../components/layout/MobileLayout";
import Input from "../components/common/Input";
import Button from "../components/common/Button";

function LoginPage() {
  const [activeTab, setActiveTab] = useState("login");

  return (
    <MobileLayout>
      {/* 프로필 이미지 */}
      <div className="avatar">
        <div className="mask mask-squircle mt-30 w-24">
          <img
            src="/re.png"
            alt="프로필"
          />
        </div>
      </div>

      {/* 제목 */}
      <h1 className="mt-5 text-center text-[24px] font-bold">
        분리쏙
      </h1>

      <h3 className="text-center text-[15px] text-[#a3a3a3]">
        스마트 분리배출 가이드
      </h3>

      {/* 로그인 탭 + 입력 */}
      <div className="mt-10 flex flex-col items-center">

        {/* 탭 */}
        <div className="tabs tabs-box w-[350px]">
          <input
            type="radio"
            name="my_tabs_1"
            className="tab flex-1"
            aria-label="로그인"
            checked={activeTab === "login"}
            onChange={() => setActiveTab("login")}
          />

          <input
            type="radio"
            name="my_tabs_1"
            className="tab flex-1"
            aria-label="회원가입"
            checked={activeTab === "signup"}
            onChange={() => setActiveTab("signup")}
          />
        </div>

        {/* 입력 폼 */}
        <div className="card bg-base-100 w-full max-w-sm shrink-0">
          <div className="card-body">
            <fieldset className="fieldset">
              <Input
                label="이메일"
                type="email"
                placeholder="example@email.com"
              />

              <Input
                label="비밀번호"
                type="password"
                placeholder="6자 이상"
              />

              {/* 회원가입일 때만 표시 */}
              {activeTab === "signup" && (
                <Input
                  label="비밀번호 재확인"
                  type="password"
                  placeholder="비밀번호를 다시 입력해주세요"
                />
              )}

              <div className="mt-10">
                <a className="link link-hover">
                  비밀번호를 잊으셨나요?
                </a>
              </div>

              <Button>
                {activeTab === "login" ? "로그인" : "회원가입"}
              </Button>
            </fieldset>
          </div>
        </div>
      </div>
    </MobileLayout>
  );
}

export default LoginPage;