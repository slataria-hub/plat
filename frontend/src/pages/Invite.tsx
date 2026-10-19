import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { api } from '../api/client'
import { useAuth } from '../hooks/useAuth'

export default function Invite() {
  const { token } = useParams()
  const { user } = useAuth()
  const nav = useNavigate()
  const [msg, setMsg] = useState('Принятие приглашения…')
  const [err, setErr] = useState('')

  useEffect(() => {
    if (!token) return
    if (!user) {
      setMsg('Войдите или зарегистрируйтесь под email приглашения, затем откройте ссылку снова.')
      return
    }
    api.acceptShare(token)
      .then(() => {
        setMsg('Доступ получен')
        setTimeout(() => nav('/'), 1500)
      })
      .catch((e) => setErr(e.message || 'Ошибка'))
  }, [token, user])

  return (
    <div className="auth-page">
      <div className="auth-card">
        <h1>Приглашение</h1>
        {err && <div className="error-box">{err}</div>}
        <p>{msg}</p>
        {!user && <Link to="/login">Войти</Link>}
      </div>
    </div>
  )
}
