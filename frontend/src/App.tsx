import { Navigate, Outlet, Route, Routes } from 'react-router-dom'
import { useAuth } from './auth'
import BoardPage from './pages/BoardPage'
import LoginPage from './pages/LoginPage'
import ProjectsPage from './pages/ProjectsPage'

function ProtectedLayout() {
  const { user, isAuthenticated, logout } = useAuth()
  if (!isAuthenticated) return <Navigate to="/login" replace />

  return (
    <div className="app-shell">
      <nav className="topbar">
        <span className="topbar-brand">Task Board</span>
        <div className="topbar-user">
          <span>{user?.display_name}</span>
          <button className="btn ghost" onClick={logout}>
            Sign out
          </button>
        </div>
      </nav>
      <main>
        <Outlet />
      </main>
    </div>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedLayout />}>
        <Route path="/" element={<ProjectsPage />} />
        <Route path="/projects/:projectId" element={<BoardPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
