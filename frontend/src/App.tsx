import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './hooks/useAuth'
import Layout from './components/Layout'
import Login from './pages/Login'
import Register from './pages/Register'
import Dashboard from './pages/Dashboard'
import Readings from './pages/Readings'
import Bills from './pages/Bills'
import BillDetail from './pages/BillDetail'
import Analytics from './pages/Analytics'
import More from './pages/More'
import BillCreate from './pages/BillCreate'
import Widget from './pages/Widget'
import Invite from './pages/Invite'

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="auth-page"><p>Загрузка…</p></div>
  if (!user) return <Navigate to="/login" replace />
  return <>{children}</>
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/invite/:token" element={<Invite />} />
      <Route
        path="/"
        element={
          <PrivateRoute>
            <Layout />
          </PrivateRoute>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="readings" element={<Readings />} />
        <Route path="bills" element={<Bills />} />
        <Route path="bills/new" element={<BillCreate />} />
        <Route path="bills/:id" element={<BillDetail />} />
        <Route path="analytics" element={<Analytics />} />
        <Route path="more" element={<More />} />
        <Route path="widget" element={<Widget />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  )
}
