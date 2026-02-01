import { useEffect } from 'react'
import { Outlet } from 'react-router-dom'
import { syncDemoMode } from '../lib/demo-mode'

export default function RootLayout() {
  useEffect(() => {
    syncDemoMode()
  }, [])

  return (
    <div className="antialiased" style={{ fontFamily: 'var(--font-spline)' }}>
      <Outlet />
    </div>
  )
}
