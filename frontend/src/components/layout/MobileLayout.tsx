import type { ReactNode } from "react"

interface Props {
  children: ReactNode
}

// Centers app content in a fixed-width mobile frame (max 430px), used as the
// single top-level shell in App.tsx.
export default function MobileLayout({ children }: Props) {
  return (
    <div className="h-full bg-muted flex items-center justify-center">
      <div className="relative mx-auto w-full max-w-[430px] h-full overflow-hidden bg-background shadow-2xl">
        {children}
      </div>
    </div>
  )
}
