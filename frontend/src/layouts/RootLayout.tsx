import { Outlet } from 'react-router-dom'

export default function RootLayout() {
  return (
    <div className="antialiased" style={{ fontFamily: 'var(--font-spline)' }}>
      <Outlet />
    </div>
  )
}
