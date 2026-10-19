import { useEffect, useState } from 'react'
import { useAuth } from '../hooks/useAuth'
import { api } from '../api/client'
import type { Property } from '../types'
import { MONTHS } from '../types'

export default function More() {
  const { user, logout } = useAuth()
  const [properties, setProperties] = useState<Property[]>([])
  const [showForm, setShowForm] = useState(false)
  const [name, setName] = useState('')
  const [address, setAddress] = useState('')
  const [account, setAccount] = useState('')
  const [exporting, setExporting] = useState<number | null>(null)
  const [backingUp, setBackingUp] = useState(false)
  const [importing, setImporting] = useState<number | null>(null)
  const [importMsg, setImportMsg] = useState('')
  const [activePid, setActivePid] = useState<number | null>(null)
  const [settings, setSettings] = useState<any>(null)
  const [accounts, setAccounts] = useState<any[]>([])
  const [shares, setShares] = useState<any[]>([])
  const [portals, setPortals] = useState<any>(null)
  const [notes, setNotes] = useState<any[]>([])
  const [noteText, setNoteText] = useState('')
  const [noteMonth, setNoteMonth] = useState(new Date().getMonth() + 1)
  const [noteYear, setNoteYear] = useState(new Date().getFullYear())
  const [accProvider, setAccProvider] = useState('')
  const [accNumber, setAccNumber] = useState('')
  const [accUrl, setAccUrl] = useState('')
  const [shareEmail, setShareEmail] = useState('')
  const [shared, setShared] = useState<any[]>([])
  const [msg, setMsg] = useState('')

  const load = () => api.listProperties().then((p) => {
    setProperties(p)
    if (p.length && !activePid) setActivePid(p[0].id)
  })
  useEffect(() => { load(); api.sharedWithMe().then(setShared).catch(() => {}) }, [])

  useEffect(() => {
    if (!activePid) return
    api.getSettings(activePid).then(setSettings).catch(() => {})
    api.listAccounts(activePid).then(setAccounts).catch(() => setAccounts([]))
    api.listShares(activePid).then(setShares).catch(() => setShares([]))
    api.portals(activePid).then(setPortals).catch(() => {})
    api.listNotes(activePid).then(setNotes).catch(() => setNotes([]))
  }, [activePid])

  const create = async (e: React.FormEvent) => {
    e.preventDefault()
    await api.createProperty({ name, address: address || undefined, account_number: account || undefined })
    setShowForm(false)
    setName(''); setAddress(''); setAccount('')
    load()
  }

  const downloadExcel = async (p: Property) => {
    setExporting(p.id)
    try {
      const token = localStorage.getItem('token')
      const res = await fetch(api.exportExcelUrl(p.id), { headers: { Authorization: `Bearer ${token}` } })
      if (!res.ok) throw new Error('Ошибка')
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `meterapp_${p.name.replace(/\s+/g, '_')}.xlsx`
      a.click()
      URL.revokeObjectURL(url)
    } catch { alert('Не удалось скачать') }
    finally { setExporting(null) }
  }

  const downloadPdf = async (p: Property) => {
    const token = localStorage.getItem('token')
    const res = await fetch(api.exportPdfUrl(p.id, noteYear), { headers: { Authorization: `Bearer ${token}` } })
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `meterapp_${p.id}_${noteYear}.pdf`
    a.click()
    URL.revokeObjectURL(url)
  }

  const downloadBackup = async () => {
    setBackingUp(true)
    try {
      const token = localStorage.getItem('token')
      const res = await fetch(api.backupZipUrl(), { headers: { Authorization: `Bearer ${token}` } })
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'meterapp_backup.zip'
      a.click()
      URL.revokeObjectURL(url)
    } catch { alert('Ошибка бэкапа') }
    finally { setBackingUp(false) }
  }

  const onImport = async (p: Property, file: File) => {
    setImporting(p.id)
    setImportMsg('')
    try {
      const report = await api.importExcel(p.id, file)
      const s = report.summary || {}
      setImportMsg(`Импорт: показаний +${s.readings_created || 0}, квитанций +${s.bills_created || 0}`)
    } catch (e: any) {
      setImportMsg(e.message || 'Ошибка')
    } finally { setImporting(null) }
  }

  const saveSettings = async () => {
    if (!activePid || !settings) return
    await api.patchSettings(activePid, {
      reminder_day: Number(settings.reminder_day),
      reminder_enabled: !!settings.reminder_enabled,
      reconcile_threshold: Number(settings.reconcile_threshold),
    })
    setMsg('Настройки сохранены')
  }

  const addAccount = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!activePid) return
    await api.createAccount(activePid, {
      provider: accProvider,
      account_number: accNumber || undefined,
      portal_url: accUrl || undefined,
      category: 'other',
    })
    setAccProvider(''); setAccNumber(''); setAccUrl('')
    setAccounts(await api.listAccounts(activePid))
  }

  const addShare = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!activePid) return
    const r = await api.createShare(activePid, shareEmail)
    setMsg(`Приглашение: токен ${r.invite_token}. Путь: ${r.invite_path}`)
    setShareEmail('')
    setShares(await api.listShares(activePid))
  }

  const saveNote = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!activePid) return
    await api.saveNote(activePid, { year: noteYear, month: noteMonth, text: noteText })
    setNoteText('')
    setNotes(await api.listNotes(activePid))
    setMsg('Заметка сохранена')
  }

  return (
    <div>
      <h1 className="page-title">Ещё</h1>
      <p className="muted">{user?.email}</p>
      {msg && <div className="info-box mt">{msg}</div>}

      <h2 className="section-title">Квартиры</h2>
      {properties.map((p) => (
        <div key={p.id} className={`card property-card ${activePid === p.id ? 'card-active' : ''}`} onClick={() => setActivePid(p.id)}>
          <div className="card-title">{p.name}</div>
          {p.address && <div className="muted">{p.address}</div>}
          <div className="btn-row" onClick={(e) => e.stopPropagation()}>
            <button className="btn secondary small" disabled={exporting === p.id} onClick={() => downloadExcel(p)}>Excel ↓</button>
            <button className="btn secondary small" onClick={() => downloadPdf(p)}>PDF ↓</button>
            <label className="btn secondary small" style={{ cursor: 'pointer' }}>
              {importing === p.id ? '…' : 'Импорт ↑'}
              <input type="file" accept=".xlsx,.xlsm" hidden disabled={!!importing}
                onChange={(e) => { const f = e.target.files?.[0]; if (f) onImport(p, f); e.target.value = '' }} />
            </label>
          </div>
        </div>
      ))}
      {importMsg && <div className="info-box mt">{importMsg}</div>}

      {!showForm ? (
        <button className="btn primary mt" onClick={() => setShowForm(true)}>+ Квартира</button>
      ) : (
        <form className="card form-card mt" onSubmit={create}>
          <label>Название<input value={name} onChange={(e) => setName(e.target.value)} required /></label>
          <label>Адрес<input value={address} onChange={(e) => setAddress(e.target.value)} /></label>
          <label>Лицевой счёт<input value={account} onChange={(e) => setAccount(e.target.value)} /></label>
          <div className="btn-row">
            <button type="submit" className="btn primary">Сохранить</button>
            <button type="button" className="btn secondary" onClick={() => setShowForm(false)}>Отмена</button>
          </div>
        </form>
      )}

      {activePid && settings && (
        <>
          <h2 className="section-title">Напоминания (выбранный объект)</h2>
          <div className="card form-card">
            <label>День месяца для напоминания
              <input type="number" min={1} max={28} value={settings.reminder_day}
                onChange={(e) => setSettings({ ...settings, reminder_day: e.target.value })} />
            </label>
            <label>
              <input type="checkbox" checked={!!settings.reminder_enabled}
                onChange={(e) => setSettings({ ...settings, reminder_enabled: e.target.checked })} /> Включено
            </label>
            <label>Порог сверки (м³ / кВт·ч)
              <input type="number" step="0.1" value={settings.reconcile_threshold}
                onChange={(e) => setSettings({ ...settings, reconcile_threshold: e.target.value })} />
            </label>
            <button type="button" className="btn primary" onClick={saveSettings}>Сохранить настройки</button>
          </div>
        </>
      )}

      {activePid && (
        <>
          <h2 className="section-title">Заметки к периоду</h2>
          <form className="card form-card" onSubmit={saveNote}>
            <div className="btn-row">
              <select value={noteMonth} onChange={(e) => setNoteMonth(Number(e.target.value))}>
                {MONTHS.map((m, i) => i > 0 && <option key={i} value={i}>{m}</option>)}
              </select>
              <select value={noteYear} onChange={(e) => setNoteYear(Number(e.target.value))}>
                {[2026, 2025, 2024].map((y) => <option key={y} value={y}>{y}</option>)}
              </select>
            </div>
            <label>Текст
              <textarea value={noteText} onChange={(e) => setNoteText(e.target.value)} rows={3} style={{ width: '100%' }} />
            </label>
            <button type="submit" className="btn primary">Сохранить заметку</button>
          </form>
          {notes.slice(0, 5).map((n) => (
            <div key={n.id} className="item-row">
              <span>{MONTHS[n.month]} {n.year}: {n.text.slice(0, 60)}</span>
            </div>
          ))}

          <h2 className="section-title">Лицевые счета / провайдеры</h2>
          {accounts.map((a) => (
            <div key={a.id} className="item-row">
              <span>{a.provider} {a.account_number && `· ${a.account_number}`}</span>
              <button className="btn secondary small" onClick={async () => {
                await api.deleteAccount(activePid, a.id)
                setAccounts(await api.listAccounts(activePid))
              }}>✕</button>
            </div>
          ))}
          <form className="card form-card" onSubmit={addAccount}>
            <label>Провайдер<input value={accProvider} onChange={(e) => setAccProvider(e.target.value)} required /></label>
            <label>Л/С<input value={accNumber} onChange={(e) => setAccNumber(e.target.value)} /></label>
            <label>Ссылка на ЛК<input value={accUrl} onChange={(e) => setAccUrl(e.target.value)} placeholder="https://" /></label>
            <button type="submit" className="btn primary">Добавить счёт</button>
          </form>

          <h2 className="section-title">Личные кабинеты</h2>
          <p className="muted small">{portals?.message}</p>
          {(portals?.defaults || []).map((p: any, i: number) => (
            <div key={i} className="item-row">
              <a href={p.url} target="_blank" rel="noreferrer">{p.name}</a>
            </div>
          ))}

          <h2 className="section-title">Семейный доступ (просмотр)</h2>
          {shares.map((s) => (
            <div key={s.id} className="item-row">
              <span>{s.guest_email} {s.accepted ? '✓' : '(ожидает)'} · {s.invite_token.slice(0, 8)}…</span>
            </div>
          ))}
          <form className="card form-card" onSubmit={addShare}>
            <label>Email гостя<input type="email" value={shareEmail} onChange={(e) => setShareEmail(e.target.value)} required /></label>
            <button type="submit" className="btn primary">Пригласить</button>
          </form>
        </>
      )}

      {shared.length > 0 && (
        <>
          <h2 className="section-title">Доступно мне</h2>
          {shared.map((s) => (
            <div key={s.property_id} className="item-row">{s.property_name} ({s.role})</div>
          ))}
        </>
      )}

      <h2 className="section-title">Данные</h2>
      <button className="btn secondary" disabled={backingUp} onClick={downloadBackup}>
        {backingUp ? '…' : 'Полный бэкап (ZIP)'}
      </button>
      <p className="muted small mt">
        <a href="/widget">Виджет-сводка</a> — краткие данные для быстрого просмотра (можно добавить на домашний экран как PWA).
      </p>

      <button className="btn danger mt" onClick={logout}>Выйти</button>
    </div>
  )
}
