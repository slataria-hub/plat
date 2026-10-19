import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import type { Property, BillListItem } from '../types'
import { MONTHS } from '../types'

export default function Bills() {
  const [properties, setProperties] = useState<Property[]>([])
  const [propertyId, setPropertyId] = useState<number | null>(null)
  const [bills, setBills] = useState<BillListItem[]>([])
  const [year, setYear] = useState<number | ''>('')
  const [sort, setSort] = useState('period_desc')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.listProperties().then((p) => {
      setProperties(p)
      if (p.length) setPropertyId(p[0].id)
    })
  }, [])

  useEffect(() => {
    if (!propertyId) return
    setLoading(true)
    const params: Record<string, string | number> = { limit: 50 }
    if (year) params.year = year
    params.sort = sort
    api.listBills(propertyId, params).then(setBills).finally(() => setLoading(false))
  }, [propertyId, year, sort])

  return (
    <div>
      <div className="section-header">
        <h1>Квитанции</h1>
        <Link to="/bills/new" className="btn primary">+ Добавить</Link>
      </div>

      <div className="filters-row">
        {properties.length > 1 && (
          <select className="select-pill" value={propertyId ?? ''} onChange={(e) => setPropertyId(Number(e.target.value))}>
            {properties.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        )}
        <select className="select-pill" value={year} onChange={(e) => setYear(e.target.value ? Number(e.target.value) : '')}>
          <option value="">Все годы</option>
          {[2026, 2025, 2024, 2023].map((y) => <option key={y} value={y}>{y}</option>)}
        </select>
        <select className="select-pill" value={sort} onChange={(e) => setSort(e.target.value)}>
          <option value="period_desc">Сначала новые</option>
          <option value="period_asc">Сначала старые</option>
          <option value="amount_desc">Сумма ↓</option>
          <option value="amount_asc">Сумма ↑</option>
        </select>
      </div>

      {loading ? <div className="skeleton" /> : (
        <div className="bill-list">
          {bills.map((b) => (
            <Link key={b.id} to={`/bills/${b.id}`} className="bill-card">
              <div className="bill-card-top">
                <span className="bill-provider">{b.provider}</span>
                <span className={`status-badge status-${b.status}`}>{b.status}</span>
              </div>
              <div className="bill-card-period">{MONTHS[b.period_month]} {b.period_year}</div>
              <div className="bill-card-bottom">
                <span className="bill-amount">{b.total_accrued.toLocaleString('ru-RU')} ₽</span>
                {b.total_paid > 0 && (
                  <span className="muted">оплачено {b.total_paid.toLocaleString('ru-RU')} ₽</span>
                )}
                {b.items_count > 0 && <span className="muted">{b.items_count} услуг</span>}
              </div>
            </Link>
          ))}
          {bills.length === 0 && <p className="muted">Квитанций нет</p>}
        </div>
      )}
    </div>
  )
}
