import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import type { Property, Meter } from '../types'
import { METER_TYPE_LABELS } from '../types'

export default function Dashboard() {
  const [properties, setProperties] = useState<Property[]>([])
  const [activeId, setActiveId] = useState<number | null>(null)
  const [meters, setMeters] = useState<Meter[]>([])
  const [alerts, setAlerts] = useState<any[]>([])
  const [expected, setExpected] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [quickOpen, setQuickOpen] = useState(false)
  const [quickDate, setQuickDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [quickValues, setQuickValues] = useState<Record<number, { t1: string; t2: string }>>({})
  const [quickMsg, setQuickMsg] = useState('')

  useEffect(() => {
    api.listProperties().then((p) => {
      setProperties(p)
      if (p.length && !activeId) setActiveId(p[0].id)
    }).finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!activeId) return
    setLoading(true)
    Promise.all([
      api.listMeters(activeId),
      api.notifications(activeId).catch(() => ({ items: [] })),
      api.expectedPayment(activeId, 6).catch(() => null),
    ]).then(([m, n, e]) => {
      setMeters(m as Meter[])
      setAlerts((n as any).items || [])
      setExpected(e)
      const vals: Record<number, { t1: string; t2: string }> = {}
      ;(m as Meter[]).forEach((meter) => {
        vals[meter.id] = { t1: '', t2: '' }
      })
      setQuickValues(vals)
    }).finally(() => setLoading(false))
  }, [activeId])

  const submitQuick = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!activeId) return
    setQuickMsg('')
    const items = Object.entries(quickValues)
      .filter(([, v]) => v.t1 !== '')
      .map(([id, v]) => ({
        meter_id: Number(id),
        value_t1: Number(v.t1),
        value_t2: v.t2 !== '' ? Number(v.t2) : undefined,
      }))
    if (!items.length) {
      setQuickMsg('Введите хотя бы одно показание')
      return
    }
    try {
      const r = await api.quickReadings(activeId, { reading_date: quickDate, items })
      setQuickMsg(`Сохранено: ${r.count}`)
      setQuickOpen(false)
      const m = await api.listMeters(activeId)
      setMeters(m as Meter[])
      const n = await api.notifications(activeId).catch(() => ({ items: [] }))
      setAlerts((n as any).items || [])
    } catch (err: any) {
      setQuickMsg(err.message || 'Ошибка')
    }
  }

  if (loading && !properties.length) return <p className="muted">Загрузка…</p>

  return (
    <div>
      <h1 className="page-title">Главная</h1>
      {properties.length > 1 && (
        <select className="select-pill" value={activeId ?? ''} onChange={(e) => setActiveId(Number(e.target.value))}>
          {properties.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
      )}
      {properties.length === 0 && (
        <p className="muted">Добавьте квартиру в разделе «Ещё».</p>
      )}

      {expected && expected.expected > 0 && (
        <div className="card highlight-card mt">
          <div className="stat-label">Ожидаемый платёж (среднее)</div>
          <div className="stat-value">{Number(expected.expected).toLocaleString('ru-RU')} ₽</div>
          <div className="muted small">{expected.message}</div>
        </div>
      )}

      <div className="btn-row mt">
        <button className="btn primary" onClick={() => setQuickOpen(!quickOpen)}>
          {quickOpen ? 'Закрыть ввод' : '⚡ Быстро внести показания'}
        </button>
        <Link className="btn secondary" to="/readings">Все показания</Link>
      </div>

      {quickOpen && (
        <form className="card form-card mt" onSubmit={submitQuick}>
          <label>Дата<input type="date" value={quickDate} onChange={(e) => setQuickDate(e.target.value)} required /></label>
          {meters.map((m) => (
            <div key={m.id} className="quick-meter">
              <div className="card-title">{METER_TYPE_LABELS[m.type] || m.type} · {m.name}</div>
              {m.last_reading && (
                <div className="muted small">Последнее: {m.last_reading.reading_date} → {m.last_reading.value_t1}
                  {m.last_reading.value_t2 != null ? ` / ${m.last_reading.value_t2}` : ''}
                </div>
              )}
              <div className="btn-row">
                <label style={{ flex: 1 }}>T1 / основное
                  <input
                    type="number" step="0.01"
                    value={quickValues[m.id]?.t1 || ''}
                    onChange={(e) => setQuickValues((q) => ({ ...q, [m.id]: { ...q[m.id], t1: e.target.value } }))}
                  />
                </label>
                {m.tariff_type === 'day_night' && (
                  <label style={{ flex: 1 }}>T2 / ночь
                    <input
                      type="number" step="0.01"
                      value={quickValues[m.id]?.t2 || ''}
                      onChange={(e) => setQuickValues((q) => ({ ...q, [m.id]: { ...q[m.id], t2: e.target.value } }))}
                    />
                  </label>
                )}
              </div>
            </div>
          ))}
          {quickMsg && <div className="info-box">{quickMsg}</div>}
          <button type="submit" className="btn primary">Сохранить показания</button>
        </form>
      )}

      {alerts.length > 0 && (
        <div className="alerts-block mt">
          <h2 className="section-title">Уведомления</h2>
          {alerts.slice(0, 8).map((a, i) => (
            <div key={i} className={`alert-card alert-${a.severity}`}>
              <div className="alert-title">{a.title}</div>
              <div className="muted">{a.body}</div>
            </div>
          ))}
        </div>
      )}

      <h2 className="section-title">Счётчики</h2>
      {meters.map((m) => (
        <div key={m.id} className="card property-card">
          <div className="card-title">{METER_TYPE_LABELS[m.type] || m.type} · {m.name}</div>
          {m.last_reading ? (
            <div className="muted">
              {m.last_reading.reading_date}: {m.last_reading.value_t1}
              {m.last_reading.value_t2 != null ? ` / ${m.last_reading.value_t2}` : ''}
              {m.last_reading.consumption_t1 != null && ` (расход ${m.last_reading.consumption_t1})`}
            </div>
          ) : (
            <div className="muted">Нет показаний</div>
          )}
        </div>
      ))}
    </div>
  )
}
