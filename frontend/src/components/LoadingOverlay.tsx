interface LoadingOverlayProps {
  message?: string
}

export function LoadingOverlay({ message = 'Loading…' }: LoadingOverlayProps) {
  return (
    <div className="loading-overlay">
      <div className="spinner" />
      <span>{message}</span>
    </div>
  )
}