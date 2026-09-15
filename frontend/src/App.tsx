import { useEffect, useRef, useState } from "react"
import type { ClassificationResult, Screen, User } from "./types"
import { getUser, isAuthenticated, clearSession } from "./lib/storage"
import AuthScreen from "./components/AuthScreen"
import RegionScreen from "./components/RegionScreen"
import HomeScreen from "./components/HomeScreen"
import PhotoCaptureScreen from "./components/PhotoCaptureScreen"
import ResultScreen from "./components/ResultScreen"

// App screens:
// auth → region (first setup) → home → capture → result
// home also has: change region → region screen
type AppScreen = Screen | "capture"

export default function App() {
  const [screen, setScreen] = useState<AppScreen>("auth")
  const [user, setUser] = useState<User | null>(null)
  const [result, setResult] = useState<ClassificationResult | null>(null)
  const [resultImageUrl, setResultImageUrl] = useState<string | null>(null)
  const [changingRegion, setChangingRegion] = useState(false)
  const [captureDemo, setCaptureDemo] = useState<"analyzing" | "agent_thinking" | "fail" | "uncertain" | undefined>()
  const prevImageUrl = useRef<string | null>(null)

  // Restore session on mount
  useEffect(() => {
    if (isAuthenticated()) {
      const saved = getUser()
      if (saved) {
        setUser(saved)
        setScreen(saved.regionCode ? "home" : "region")
      }
    }
  }, [])

  // Revoke old object URLs to avoid memory leaks
  useEffect(() => {
    if (prevImageUrl.current && prevImageUrl.current !== resultImageUrl) {
      URL.revokeObjectURL(prevImageUrl.current)
    }
    prevImageUrl.current = resultImageUrl
  }, [resultImageUrl])

  function handleAuthSuccess(loggedInUser: User) {
    setUser(loggedInUser)
    setScreen(loggedInUser.regionCode ? "home" : "region")
  }

  function handleRegionSaved(updatedUser: User) {
    setUser(updatedUser)
    setChangingRegion(false)
    setScreen("home")
  }

  function handleViewGuidelines(r: ClassificationResult, imageUrl: string) {
    setResult(r)
    setResultImageUrl(imageUrl)
    setScreen("result")
  }

  function handleChangeRegion() {
    setChangingRegion(true)
    setScreen("region")
  }

  function handleLogout() {
    clearSession()
    setUser(null)
    setResult(null)
    setResultImageUrl(null)
    setScreen("auth")
  }

  const mobileWrapper =
    "relative mx-auto w-full max-w-[430px] h-full overflow-hidden bg-background shadow-2xl"

  return (
    <div className="h-full bg-muted flex items-center justify-center">
      <div className={mobileWrapper}>

        {screen === "auth" && (
          <div className="h-full overflow-y-auto no-scrollbar">
            <AuthScreen onSuccess={handleAuthSuccess} />
          </div>
        )}

        {screen === "region" && user && (
          <div className="h-full overflow-y-auto no-scrollbar">
            <RegionScreen
              user={user}
              onSaved={handleRegionSaved}
              isFirstSetup={!changingRegion}
            />
          </div>
        )}

        {/* Home: landing pad with header, region status, and launch button */}
        {screen === "home" && user && (
          <HomeScreen
            user={user}
            onResult={(r, url) => {
              setResult(r)
              setResultImageUrl(url)
              setScreen("result")
            }}
            onChangeRegion={handleChangeRegion}
            onLogout={handleLogout}
            onStartCapture={() => { setCaptureDemo("uncertain"); setScreen("capture") }}
            onDemoAnalyzing={() => { setCaptureDemo("analyzing"); setScreen("capture") }}
            onDemoAgentThinking={() => { setCaptureDemo("agent_thinking"); setScreen("capture") }}
            onDemoFail={() => { setCaptureDemo("fail"); setScreen("capture") }}
          />
        )}

        {/* Capture: full 5-state photo capture flow */}
        {screen === "capture" && user && (
          <PhotoCaptureScreen
            user={user}
            onViewGuidelines={handleViewGuidelines}
            onBack={() => setScreen("home")}
            demoState={captureDemo}
          />
        )}

        {screen === "result" && result && resultImageUrl && (
          <ResultScreen
            result={result}
            imageUrl={resultImageUrl}
            onBack={() => setScreen("capture")}
          />
        )}

      </div>
    </div>
  )
}
