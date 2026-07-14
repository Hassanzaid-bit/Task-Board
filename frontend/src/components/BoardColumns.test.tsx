import { describe, expect, it, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import BoardColumns from './BoardColumns'
import type { Task } from '../types'

function makeTask(overrides: Partial<Task>): Task {
  return {
    id: 1,
    project_id: 1,
    title: 'Task',
    description: '',
    status: 'todo',
    assignee_id: null,
    assignee_name: null,
    due_date: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

const tasks: Task[] = [
  makeTask({ id: 1, title: 'Write the spec', status: 'todo' }),
  makeTask({ id: 2, title: 'Build the API', status: 'in_progress', assignee_name: 'Alice' }),
  makeTask({ id: 3, title: 'Ship it', status: 'done', assignee_name: 'Bob' }),
]

describe('BoardColumns', () => {
  it('renders each task in the column matching its status', () => {
    render(<BoardColumns tasks={tasks} onMove={vi.fn()} onOpen={vi.fn()} />)

    const todo = screen.getByRole('region', { name: 'To Do' })
    const inProgress = screen.getByRole('region', { name: 'In Progress' })
    const done = screen.getByRole('region', { name: 'Done' })

    expect(within(todo).getByText('Write the spec')).toBeInTheDocument()
    expect(within(inProgress).getByText('Build the API')).toBeInTheDocument()
    expect(within(done).getByText('Ship it')).toBeInTheDocument()
    expect(within(todo).queryByText('Ship it')).not.toBeInTheDocument()
  })

  it('moving a task to the next column calls onMove with the new status', async () => {
    const user = userEvent.setup()
    const onMove = vi.fn()
    render(<BoardColumns tasks={tasks} onMove={onMove} onOpen={vi.fn()} />)

    await user.click(
      screen.getByRole('button', { name: 'Move "Write the spec" to In Progress' }),
    )

    expect(onMove).toHaveBeenCalledTimes(1)
    const [movedTask, newStatus] = onMove.mock.calls[0]
    expect(movedTask.id).toBe(1)
    expect(newStatus).toBe('in_progress')
  })

  it('opens a task when its card is clicked', async () => {
    const user = userEvent.setup()
    const onOpen = vi.fn()
    render(<BoardColumns tasks={tasks} onMove={vi.fn()} onOpen={onOpen} />)

    await user.click(screen.getByText('Build the API'))

    expect(onOpen).toHaveBeenCalledTimes(1)
    expect(onOpen.mock.calls[0][0].id).toBe(2)
  })
})
