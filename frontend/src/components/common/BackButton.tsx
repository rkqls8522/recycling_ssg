interface Props {
  onClick: () => void
  ariaLabel: string
}

// Rounded icon button used in colored header bars (bg-primary etc.) across
// ResultScreen, PhotoCaptureScreen/CaptureView and AgentThinkingView.
export default function BackButton({ onClick, ariaLabel }: Props) {
  return (
    <button
      onClick={onClick}
      className="w-9 h-9 rounded-xl bg-primary-foreground/10 flex items-center justify-center active:bg-primary-foreground/20 transition-colors"
      aria-label={ariaLabel}
    >
      <svg viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5" aria-hidden="true">
        <path
          fillRule="evenodd"
          d="M17 10a.75.75 0 0 1-.75.75H5.612l4.158 3.96a.75.75 0 1 1-1.04 1.08l-5.5-5.25a.75.75 0 0 1 0-1.08l5.5-5.25a.75.75 0 1 1 1.04 1.08L5.612 9.25H16.25A.75.75 0 0 1 17 10z"
          clipRule="evenodd"
        />
      </svg>
    </button>
  )
}
