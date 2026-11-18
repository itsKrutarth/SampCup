import { KeyRound, Pencil, Save, UserPlus, X } from 'lucide-react'
import { useState, type FormEvent } from 'react'

import Status from '../../components/Status'
import { useApi } from '../../lib/live'
import { Message, useAction } from './common'

type StaffUser = {
  id: number
  username: string
  role: string
  court: number | null
  active: boolean
  must_change_password: boolean
}

const COURTS = Array.from({ length: 9 }, (_, i) => i + 1)

function roleLine(user: StaffUser): string {
  if (user.role === 'admin') return 'Admin'
  return user.court ? `Court ${user.court}` : 'Any court'
}

export default function Staff() {
  const { token, run, message } = useAction()
  const { data, loading, error, reload } = useApi<StaffUser[]>('/admin/staff', token)
  const [editing, setEditing] = useState<{ id: number; field: 'username' | 'password' } | null>(null)

  const patch = async (user: StaffUser, body: Record<string, unknown>, text: string) => {
    if (await run(`/admin/staff/${user.id}`, 'PATCH', body, () => text)) {
      setEditing(null)
      reload()
    }
  }
  const submitEdit = (event: FormEvent<HTMLFormElement>, user: StaffUser) => {
    event.preventDefault()
    const value = String(new FormData(event.currentTarget).get('value') ?? '').trim()
    if (editing?.field === 'username') void patch(user, { username: value }, `Renamed to ${value.toLowerCase()}`)
    else void patch(user, { password: value }, `New password set for ${user.username}. They choose their own at next login.`)
  }
  const add = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const form = event.currentTarget
    const values = new FormData(form)
    const body = {
      username: values.get('username'),
      password: values.get('password'),
      role: values.get('role'),
      court: values.get('court') ? Number(values.get('court')) : null,
    }
    if (await run('/admin/staff', 'POST', body, () => `Added ${String(body.username).toLowerCase()}`)) {
      form.reset()
      reload()
    }
  }

  return (
    <>
      <Message message={message} />
      <Status loading={loading} error={error} />
      <p className="hint">
        Usernames are unique and used to log in. A password or PIN you set is temporary: the person chooses their own the
        first time they log in.
      </p>
      <div className="table-wrap">
        <table className="cards">
          <thead>
            <tr>
              <th>User</th>
              <th>Court</th>
              <th>Active</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {data?.map((u) => (
              <tr key={u.id} className={u.active ? '' : 'inactive'}>
                <td className="user-cell primary">
                  {editing?.id === u.id && editing.field === 'username' ? (
                    <form className="inline-form" onSubmit={(e) => submitEdit(e, u)} aria-label={`Rename ${u.username}`}>
                      <input name="value" defaultValue={u.username} required pattern="[A-Za-z0-9_\-]+" aria-label="New username" autoCapitalize="none" />
                      <button type="submit">
                        <Save size={16} />
                        Save
                      </button>
                      <button type="button" className="link" onClick={() => setEditing(null)} aria-label="Cancel">
                        <X size={16} />
                      </button>
                    </form>
                  ) : (
                    <>
                      <strong>{u.username}</strong>
                      <small>
                        {roleLine(u)}
                        {u.must_change_password && ' · temporary password'}
                      </small>
                    </>
                  )}
                </td>
                <td data-label="Court">
                  {u.role === 'judge' ? (
                    <select
                      aria-label={`Court for ${u.username}`}
                      value={u.court ?? ''}
                      onChange={(e) =>
                        patch(
                          u,
                          e.target.value ? { court: Number(e.target.value) } : { clear_court: true },
                          `${u.username}: ${e.target.value ? `court ${e.target.value}` : 'any court'}`,
                        )
                      }
                    >
                      <option value="">Any</option>
                      {COURTS.map((c) => (
                        <option key={c}>{c}</option>
                      ))}
                    </select>
                  ) : (
                    <span className="muted">-</span>
                  )}
                </td>
                <td data-label="Active">
                  <input
                    type="checkbox"
                    aria-label={`${u.username} active`}
                    checked={u.active}
                    onChange={(e) => patch(u, { active: e.target.checked }, `${u.username} ${e.target.checked ? 'enabled' : 'disabled'}`)}
                  />
                </td>
                <td>
                  {editing?.id === u.id && editing.field === 'password' ? (
                    <form className="inline-form" onSubmit={(e) => submitEdit(e, u)} aria-label={`New password for ${u.username}`}>
                      <input name="value" required minLength={u.role === 'admin' ? 8 : 4} aria-label="Temporary password or PIN" autoComplete="off" />
                      <button type="submit">
                        <KeyRound size={16} />
                        Set
                      </button>
                      <button type="button" className="link" onClick={() => setEditing(null)} aria-label="Cancel">
                        <X size={16} />
                      </button>
                    </form>
                  ) : (
                    <div className="toolbar">
                      <button type="button" className="link" onClick={() => setEditing({ id: u.id, field: 'username' })}>
                        <Pencil size={14} />
                        Rename
                      </button>
                      <button type="button" className="link" onClick={() => setEditing({ id: u.id, field: 'password' })}>
                        <KeyRound size={14} />
                        Set password
                      </button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <form onSubmit={add} className="stack card">
        <h2>
          <UserPlus size={20} /> Add a judge or admin
        </h2>
        <label>
          Username
          <input name="username" required pattern="[A-Za-z0-9_\-]+" autoCapitalize="none" />
        </label>
        <label>
          Temporary password or PIN
          <input name="password" required minLength={4} autoComplete="off" />
        </label>
        <label>
          Role
          <select name="role" defaultValue="judge">
            <option value="judge">judge</option>
            <option value="admin">admin (password 8+ characters)</option>
          </select>
        </label>
        <label>
          Court
          <select name="court" defaultValue="">
            <option value="">Any</option>
            {COURTS.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </label>
        <button type="submit">
          <UserPlus size={18} />
          Add
        </button>
      </form>
    </>
  )
}
