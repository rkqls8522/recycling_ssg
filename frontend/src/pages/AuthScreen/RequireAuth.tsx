import { Navigate, Outlet } from "react-router-dom"
import { useAuthContext } from "./AuthContext"

// user가 없으면 /login으로 돌려보내는 라우트 가드.
// region/home/capture/result 라우트를 이 컴포넌트로 감싼다.
export default function RequireAuth() {
  const { user } = useAuthContext()
  if (!user) return <Navigate to="/login" replace />
  return <Outlet />
}
