import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'

const nav = [
  { to: '/', label: 'Главная', icon: '⌂' },
  { to: '/readings', label: 'Показания', icon: '◎' },
  { to: '/bills', label: 'Квитанции', icon: '☰' },
  { to: '/analytics', label: 'Аналитика', icon: '▤' },
  { to: '/more', label: 'Ещё', icon: '⋯' },
]

export default function Layout() {
  const { user } = useAuth()

  return (
    <div className="app-shell">
      <header className="top-bar">
        <div className="brand">MeterApp</div>
        <div className="user-chip">{user?.name || user?.email}</div>
      </header>

      <main className="page">
        <Outlet />
      </main>

      <nav className="bottom-nav">
        {nav.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
          >
            <span className="nav-icon">{item.icon}</span>
            <span className="nav-label">{item.label}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  )
}
