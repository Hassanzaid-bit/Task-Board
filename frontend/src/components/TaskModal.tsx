import { useState, type FormEvent } from 'react'
import { STATUS_LABELS, TASK_STATUSES, type Task, type TaskStatus, type User } from '../types'

export type TaskFormValues = {
  title: string
  description: string
  status: TaskStatus
  assignee_id: number
  due_date: string
}

type Props = {
  task: Task | null // null = creating a new task
  users: User[]
  busy: boolean
  error: string | null
  onSave: (values: TaskFormValues) => void
  onDelete: (() => void) | null
  onClose: () => void
}

/** Today in the user's local timezone, as the YYYY-MM-DD a date input expects. */
function todayISO(): string {
  const now = new Date()
  now.setMinutes(now.getMinutes() - now.getTimezoneOffset())
  return now.toISOString().slice(0, 10)
}

export default function TaskModal({ task, users, busy, error, onSave, onDelete, onClose }: Props) {
  const [title, setTitle] = useState(task?.title ?? '')
  const [description, setDescription] = useState(task?.description ?? '')
  const [status, setStatus] = useState<TaskStatus>(task?.status ?? 'todo')
  const [assigneeId, setAssigneeId] = useState<string>(task?.assignee_id?.toString() ?? '')
  const [dueDate, setDueDate] = useState(task?.due_date ?? '')

  // New tasks can't be scheduled in the past. When editing an already-overdue
  // task, its existing date stays selectable so unrelated edits aren't blocked.
  const today = todayISO()
  const minDueDate = task?.due_date && task.due_date < today ? task.due_date : today

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!assigneeId || !dueDate) return // browser `required` should prevent this
    onSave({
      title: title.trim(),
      description: description.trim(),
      status,
      assignee_id: Number(assigneeId),
      due_date: dueDate,
    })
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal"
        role="dialog"
        aria-label={task ? 'Edit task' : 'New task'}
        onClick={(e) => e.stopPropagation()}
      >
        <header className="modal-header">
          <h2>{task ? 'Edit task' : 'New task'}</h2>
          <button className="btn ghost" aria-label="Close" onClick={onClose}>
            ✕
          </button>
        </header>

        <form onSubmit={handleSubmit}>
          <label>
            Title
            <input
              required
              maxLength={200}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="What needs doing?"
            />
          </label>
          <label>
            Description
            <textarea
              required
              maxLength={5000}
              rows={4}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What is this task about?"
            />
          </label>
          <div className="form-row">
            <label>
              Status
              {/* New tasks always start in To Do; status is only editable afterwards. */}
              <select
                value={status}
                disabled={task === null}
                onChange={(e) => setStatus(e.target.value as TaskStatus)}
              >
                {TASK_STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {STATUS_LABELS[s]}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Assignee
              <select
                required
                value={assigneeId}
                onChange={(e) => setAssigneeId(e.target.value)}
              >
                <option value="" disabled>
                  Select assignee…
                </option>
                {users.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.display_name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Due date
              <input
                type="date"
                required
                min={minDueDate}
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
              />
            </label>
          </div>

          {error && <p className="form-error" role="alert">{error}</p>}

          <footer className="modal-footer">
            {onDelete && (
              <button type="button" className="btn danger" disabled={busy} onClick={onDelete}>
                Delete
              </button>
            )}
            <div className="spacer" />
            <button type="button" className="btn" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn primary" disabled={busy || !title.trim()}>
              {busy ? 'Saving…' : task ? 'Save changes' : 'Create task'}
            </button>
          </footer>
        </form>
      </div>
    </div>
  )
}
