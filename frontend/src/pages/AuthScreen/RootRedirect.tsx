import { Navigate } from "react-router-dom"
import { useAuthContext, resolveHomeRoute } from "./AuthContext"

// "/" 진입 시 로그인 상태에 따라 적절한 화면으로 보낸다.
export default function RootRedirect() {
  const { user } = useAuthContext()
  return <Navigate to={user ? resolveHomeRoute(user) : "/login"} replace />
}
