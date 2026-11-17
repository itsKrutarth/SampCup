import type { FormEvent } from 'react'

import Status from '../../components/Status'
import { useApi } from '../../lib/live'
import type { Announcement } from '../../lib/types'
import { Message, useAction } from './common'

export default function Announcements() {
  const { token, run, message } = useAction()
  const { data, loading, error, reload } = useApi<Announcement[]>('/admin/announcements', token)
  const add = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const form = event.currentTarget
    const body = Object.fromEntries(new FormData(form))
    if (await run('/admin/announcements', 'POST', body, () => 'Announcement posted')) {
      form.reset()
      reload()
    }
  }
  return (
    <>
      <form onSubmit={add} className="stack">
        <h2>New announcement</h2>
        <p className="hint">Shows as a banner on every page and on the projector until you hide it.</p>
        <label>Title<input name="title" required maxLength={120} /></label>
        <label>Details<textarea name="body" maxLength={2000} /></label>
        <button type="submit">Post</button>
      </form>
      <Message message={message} />
      <Status loading={loading} error={error} />
      <ul className="plain">
        {data?.map((a) => (
          <li key={a.id} className={a.active ? '' : 'inactive'}>
            <strong>{a.title}</strong> {a.body}{' '}
            <button type="button" className="link" onClick={async () => {
              if (await run(`/admin/announcements/${a.id}`, 'PATCH', { active: !a.active }, () => (a.active ? 'Hidden' : 'Shown again'))) reload()
            }}>
              {a.active ? 'Hide' : 'Show'}
            </button>
            <button type="button" className="link danger" onClick={async () => {
              if ((await run(`/admin/announcements/${a.id}`, 'DELETE', undefined, () => 'Deleted')) !== undefined) reload()
            }}>
              Delete
            </button>
          </li>
        ))}
      </ul>
    </>
  )
}
