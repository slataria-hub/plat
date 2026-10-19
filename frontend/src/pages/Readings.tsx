import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { Property, Meter, MeterReading } from '../types'
import { METER_TYPE_LABELS, METER_TYPE_COLORS } from '../types'

export default function Readings() {
  const [properties, setProperties] = useState<Property[]>([])
  const [propertyId, setPropertyId] = useState<number | null>(null)
  const [meters, setMeters] = useState<Meter[]>([])
  const [selectedMeter, setSelectedMeter] = useState<number | null>(null)
  const [readings, setReadings] = useState<MeterReading[]>([])
  const [showForm, setShowForm] = useState(false)
  const [showMeterForm, setShowMeterForm] = useState(false)
  const [form, setForm] = useState({ reading_date: '', value_t1: '', value_t2: '' })
  const [photoLoading, setPhotoLoading] = useState(false)
  const [meterForm, setMeterForm] = useState({
    type: 'cold_water',
    name: 'СУ1',
    tariff_type: 'single',
    serial_number: '',
  })
  const [error, setError] = useState('')

  useEffect(() => {
    api.listProperties().then((p) => {
      setProperties(p)
      if (p.length) setPropertyId(p[0].id)
    })
  }, [])

  useEffect(() => {
    if (!propertyId) return
    api.listMeters(propertyId).then((m) => {
      setMeters(m)
      if (m.length) setSelectedMeter(m[0].id)
      else setSelectedMeter(null)
    })
  }, [propertyId])

  useEffect(() => {
    if (!selectedMeter) { setReadings([]); return }
    api.listReadings(selectedMeter).then(setReadings)
  }, [selectedMeter])

  const meter = meters.find((m) => m.id === selectedMeter)

  const submitReading = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedMeter) return
    setError('')
    try {
      await api.createReading(selectedMeter, {
        meter_id: selectedMeter,
        reading_date: form.reading_date,
        value_t1: parseFloat(form.value_t1),
        value_t2: form.value_t2 ? parseFloat(form.value_t2) : null,
        source: 'manual',
      })
      setShowForm(false)
      setForm({ reading_date: '', value_t1: '', value_t2: '' })
      api.listReadings(selectedMeter).then(setReadings)
      if (propertyId) api.listMeters(propertyId).then(setMeters)
    } catch (err: any) {
      setError(err.message)
    }
  }

  const submitMeter = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!propertyId) return
    setError('')
    try {
      await api.createMeter(propertyId, {
        property_id: propertyId,
        type: meterForm.type,
        name: meterForm.name,
        tariff_type: meterForm.tariff_type,
        serial_number: meterForm.serial_number || null,
      })
      setShowMeterForm(false)
      setMeterForm({ type: 'cold_water', name: 'СУ1', tariff_type: 'single', serial_number: '' })
      const m = await api.listMeters(propertyId)
      setMeters(m)
      if (m.length) setSelectedMeter(m[m.length - 1].id)
    } catch (err: any) {
      setError(err.message)
    }
  }


  const onPhoto = async (file: File) => {
    if (!selectedMeter) return
    setPhotoLoading(true)
    setError('')
    try {
      const token = localStorage.getItem('token')
      const fd = new FormData()
      fd.append('file', file)
      if (form.reading_date) fd.append('reading_date', form.reading_date)
      fd.append('apply', 'false')
      const r = await fetch(`/api/v1/meters/${selectedMeter}/readings/from-photo`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: fd,
      })
      const data = await r.json()
      if (!r.ok) throw new Error(data.detail || 'OCR ошибка')
      if (data.value_t1 != null) {
        setForm((f) => ({
          ...f,
          value_t1: String(data.value_t1),
          value_t2: data.value_t2 != null ? String(data.value_t2) : f.value_t2,
        }))
      }
      if (data.message) setError(data.message) // show as info in error box for now
    } catch (err: any) {
      setError(err.message)
    } finally {
      setPhotoLoading(false)
    }
  }

  return (
    <div>
      <div className="section-header">
        <h1>Показания</h1>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn secondary" onClick={() => { setShowMeterForm(!showMeterForm); setShowForm(false) }}>
            {showMeterForm ? 'Отмена' : '+ Счётчик'}
          </button>
          <button className="btn primary" onClick={() => { setShowForm(!showForm); setShowMeterForm(false) }} disabled={!selectedMeter}>
            {showForm ? 'Отмена' : '+ Показание'}
          </button>
        </div>
      </div>

      {properties.length > 1 && (
        <select className="select-pill mb" value={propertyId ?? ''} onChange={(e) => setPropertyId(Number(e.target.value))}>
          {properties.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
      )}

      {showMeterForm && (
        <form className="card form-card" onSubmit={submitMeter}>
          <h3>Новый счётчик</h3>
          <label>Тип
            <select value={meterForm.type} onChange={(e) => setMeterForm({
              ...meterForm,
              type: e.target.value,
              tariff_type: e.target.value === 'electricity' ? 'day_night' : 'single',
              name: e.target.value === 'electricity' ? 'Основной' : 'СУ1',
            })}>
              <option value="cold_water">Холодная вода</option>
              <option value="hot_water">Горячая вода</option>
              <option value="electricity">Электричество</option>
            </select>
          </label>
          <label>Название
            <input required value={meterForm.name} onChange={(e) => setMeterForm({ ...meterForm, name: e.target.value })} placeholder="СУ1, СУ2, Основной…" />
          </label>
          <label>Тариф
            <select value={meterForm.tariff_type} onChange={(e) => setMeterForm({ ...meterForm, tariff_type: e.target.value })}>
              <option value="single">Однотарифный</option>
              <option value="day_night">День / Ночь</option>
            </select>
          </label>
          <label>Заводской номер
            <input value={meterForm.serial_number} onChange={(e) => setMeterForm({ ...meterForm, serial_number: e.target.value })} placeholder="Необязательно" />
          </label>
          {error && <div className="error-box">{error}</div>}
          <button type="submit" className="btn primary">Создать счётчик</button>
        </form>
      )}

      <div className="chip-row">
        {meters.map((m) => (
          <button
            key={m.id}
            className={`chip${selectedMeter === m.id ? ' active' : ''}`}
            style={{ '--chip-color': METER_TYPE_COLORS[m.type] } as any}
            onClick={() => setSelectedMeter(m.id)}
          >
            {METER_TYPE_LABELS[m.type]} · {m.name}
          </button>
        ))}
      </div>
      {meters.length === 0 && !showMeterForm && (
        <p className="muted mb">Нет счётчиков — нажмите «+ Счётчик»</p>
      )}

      {showForm && meter && (
        <form className="card form-card" onSubmit={submitReading}>
          <h3>Новое показание — {meter.name}</h3>
          <label>Дата<input type="date" required value={form.reading_date} onChange={(e) => setForm({ ...form, reading_date: e.target.value })} /></label>
          <label>{meter.tariff_type === 'day_night' ? 'День' : 'Показание'}
            <input type="number" step="0.001" required value={form.value_t1} onChange={(e) => setForm({ ...form, value_t1: e.target.value })} />
          </label>
          {meter.tariff_type === 'day_night' && (
            <label>Ночь
              <input type="number" step="0.001" required value={form.value_t2} onChange={(e) => setForm({ ...form, value_t2: e.target.value })} />
            </label>
          )}
          <label>Фото счётчика (OCR)
            <input type="file" accept="image/*" capture="environment"
              disabled={photoLoading}
              onChange={(e) => { const f = e.target.files?.[0]; if (f) onPhoto(f) }} />
          </label>
          {photoLoading && <p className="muted">Распознавание фото…</p>}
          {error && <div className="error-box">{error}</div>}
          <button type="submit" className="btn primary">Сохранить</button>
        </form>
      )}

      <div className="reading-list">
        {readings.map((r) => (
          <div key={r.id} className="reading-card">
            <div className="reading-date">{r.reading_date}</div>
            <div className="reading-values">
              <span className="big">{r.value_t1}</span>
              {r.value_t2 != null && <span className="big muted"> / {r.value_t2}</span>}
              <span className="unit">{meter?.unit}</span>
            </div>
            {r.consumption_t1 != null && (
              <div className="reading-cons">
                расход: {r.consumption_t1}
                {r.consumption_t2 != null && ` + ${r.consumption_t2}`}
              </div>
            )}
          </div>
        ))}
        {readings.length === 0 && selectedMeter && <p className="muted">Нет показаний</p>}
      </div>
    </div>
  )
}
