import type { FormEvent } from 'react'

import Status from '../../components/Status'
import { useApi } from '../../lib/live'
import { Message, useAction } from './common'

type StaffUser = { id: number; username: string; display_name: string; role: string; court: number | null; active: boolean }

export default function Staff() {
  const { token, run, message } = useAction()
  const { data, loading, error, reload } = useApi<StaffUser[]>('/admin/staff', token)
  const add = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const form = event.currentTarget
    const values = new FormData(form)
    const body = {
      username: values.get('username'),
      display_name: values.get('display_name'),
      password: values.get('password'),
      role: values.get('role'),
      court: values.get('court') ? Number(values.get('court')) : null,
    }
    if (await run('/admin/staff', 'POST', body, () => `Added ${body.username}`)) {
      form.reset()
      reload()
    }
  }
  const patch = async (user: StaffUser, body: Record<string, unknown>, text: string) => {
    if (await run(`/admin/staff/${user.id}`, 'PATCH', body, () => text)) reload()
  }
  return (
    <>
      <Message message={message} />
      <Status loading={loading} error={error} />
      <table>
        <thead>
          <tr><th>User</th><th>Role</th><th>Court</th><th>Active</th><th /></tr>
        </thead>
        <tbody>
          {data?.map((u) => (
            <tr key={u.id}>
              <td>{u.display_name}<br /><small>{u.username}</small></td>
              <td>{u.role}</td>
              <td>
                <select aria-label={`Court for ${u.username}`} value={u.court ?? ''} onChange={(e) =>
                  patch(u, e.target.value ? { court: Number(e.target.value) } : { clear_court: true }, `${u.username}: ${e.target.value ? `court ${e.target.value}` : 'any court'}`)
                }>
                  <option value="">Any</option>
                  {Array.from({ length: 9 }, (_, i) => <option key={i + 1}>{i + 1}</option>)}
                </select>
              </td>
              <td>
                <input type="checkbox" aria-label={`${u.username} active`} checked={u.active} onChange={(e) => patch(u, { active: e.target.checked }, `${u.username} ${e.target.checked ? 'enabled' : 'disabled'}`)} />
              </td>
              <td>
                <button type="button" className="link" onClick={() => {
                  const password = window.prompt(`New password or PIN for ${u.username}`)
                  if (password) void patch(u, { password }, `Password changed for ${u.username}`)
                }}>
                  Reset password
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <form onSubmit={add} className="stack">
        <h2>Add a judge or admin</h2>
        <label>Username<input name="username" required pattern="[A-Za-z0-9_\-]+" /></label>
        <label>Name<input name="display_name" /></label>
        <label>Password or PIN<input name="password" required minLength={4} /></label>
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
            {Array.from({ length: 9 }, (_, i) => <option key={i + 1}>{i + 1}</option>)}
          </select>
        </label>
        <button type="submit">Add</button>
      </form>
    </>
  )
}
