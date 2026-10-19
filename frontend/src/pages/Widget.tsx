import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { METER_TYPE_LABELS } from '../types'

export default function Widget() {
  const [data, setData] = useState<any>(null)
  const [err, setErr] = useState('')

  useEffect(() => {
    api.widget().then(setData).catch((e) => setErr(e.message))
  }, [])

  if (err) return <div className="error-box">{err}</div>
  if (!data) return <p className="muted">Загрузка…</p>

  return (
    <div className="widget-page">
      <h1 className="page-title">Сводка</h1>
      <p className="muted small">на {data.as_of}</p>
      {(data.properties || []).map((p: any) => (
        <div key={p.property_id} className="card property-card">
          <div className="card-title">{p.property_name}</div>
          <div className="stat-row">
            <div className="stat-card">
              <div className="stat-label">К оплате (последний счёт)</div>
              <div className="stat-value">{Number(p.last_bill_due).toLocaleString('ru-RU')} ₽</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Ожидаемо</div>
              <div className="stat-value">{Number(p.expected_payment).toLocaleString('ru-RU')} ₽</div>
            </div>
          </div>
          {(p.meters || []).map((m: any) => (
            <div key={m.id} className="item-row">
              <span>{METER_TYPE_LABELS[m.type] || m.type} · {m.name}</span>
              <span>
                {m.last_value_t1 != null ? m.last_value_t1 : '—'}
                {m.last_value_t2 != null ? ` / ${m.last_value_t2}` : ''}
              </span>
            </div>
          ))}
        </div>
      ))}
      <Link to="/" className="btn secondary mt">В приложение</Link>
    </div>
  )
}
