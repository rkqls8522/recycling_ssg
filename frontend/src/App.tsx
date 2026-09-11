import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./pages/AuthScreen/AuthContext";
import RequireAuth from "./pages/AuthScreen/RequireAuth";
import RootRedirect from "./pages/AuthScreen/RootRedirect";
import MobileLayout from "./components/layout/MobileLayout";
import AuthScreen from "./pages/AuthScreen";
import RegionScreen from "./pages/RegionScreen";
import HomeScreen from "./pages/HomeScreen";
import PhotoCaptureScreen from "./pages/PhotoCaptureScreen";
import ResultScreen from "./pages/ResultScreen";

// Routes:
// / → redirect based on auth state
// /login → auth (login/signup)
// /region, /home, /capture, /result → require a logged-in user
export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <MobileLayout>
          <Routes>
            <Route path="/" element={<RootRedirect />} />
            <Route path="/login" element={<AuthScreen />} />
            <Route element={<RequireAuth />}>
              <Route path="/region" element={<RegionScreen />} />
              <Route path="/home" element={<HomeScreen />} />
              <Route path="/capture" element={<PhotoCaptureScreen />} />
              <Route path="/result" element={<ResultScreen />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </MobileLayout>
      </AuthProvider>
    </BrowserRouter>
  );
}
