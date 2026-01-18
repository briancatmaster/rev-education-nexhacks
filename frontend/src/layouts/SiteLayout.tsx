import { Outlet } from 'react-router-dom'

export default function SiteLayout() {
  return (
    <div className="min-h-screen">
      <Outlet />
    </div>
  )
}
