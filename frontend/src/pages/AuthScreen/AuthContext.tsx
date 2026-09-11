import { createContext, useContext, useState, type ReactNode } from "react"
import type { User } from "../../types"
import { getUser, isAuthenticated, clearSession } from "../../utils/storage"

interface AuthContextValue {
  user: User | null
  setUser: (user: User) => void
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

interface Props {
  children: ReactNode
}

// 로그인 상태(user)와 로그아웃을 앱 전체에서 공유하기 위한 컨텍스트.
// localStorage에 저장된 세션이 있으면 첫 렌더링에서 바로 복원한다(깜빡임/리다이렉트 방지).
export function AuthProvider({ children }: Props) {
  const [user, setUser] = useState<User | null>(() => (isAuthenticated() ? getUser() : null))

  function logout() {
    clearSession()
    setUser(null)
  }

  return <AuthContext.Provider value={{ user, setUser, logout }}>{children}</AuthContext.Provider>
}

export function useAuthContext(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error("useAuthContext must be used within an AuthProvider")
  return ctx
}

// 로그인 성공 직후 이동할 경로: 지역이 설정돼 있지 않으면 /region, 아니면 /home.
export function resolveHomeRoute(user: User): string {
  return user.regionCode ? "/home" : "/region"
}
