import { Outlet } from 'react-router-dom'

export default function LessonsLayout() {
  // Removed sidebar - go straight into lesson view
  return (
    <div className="min-h-[calc(100vh-5rem)]">
      <Outlet />
    </div>
  )
}
