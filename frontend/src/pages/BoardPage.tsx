import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api'
import BoardColumns from '../components/BoardColumns'
import TaskModal, { type TaskFormValues } from '../components/TaskModal'
import { useBoardSocket } from '../hooks/useBoardSocket'
import { STATUS_LABELS, type Project, type Task, type TaskStatus, type User } from '../types'

export default function BoardPage() {
  const projectId = Number(useParams().projectId)
  const queryClient = useQueryClient()
  const tasksKey = ['tasks', projectId]

  const [search, setSearch] = useState('')
  const [modal, setModal] = useState<{ open: boolean; task: Task | null }>({
    open: false,
    task: null,
  })
  const [moveError, setMoveError] = useState<string | null>(null)

  useBoardSocket(projectId)

  const { data: project } = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => api.get<Project>(`/api/v1/projects/${projectId}`),
  })
  const { data: users } = useQuery({
    queryKey: ['users'],
    queryFn: () => api.get<User[]>('/api/v1/users'),
  })
  const {
    data: tasks,
    isPending,
    isError,
    error,
  } = useQuery({
    queryKey: tasksKey,
    queryFn: () => api.get<Task[]>(`/api/v1/projects/${projectId}/tasks`),
  })

  // Optimistic move: the card jumps immediately, rolls back on server error,
  // and always reconciles with a refetch (see ARCHITECTURE.md §2).
  const moveTask = useMutation({
    mutationFn: ({ task, newStatus }: { task: Task; newStatus: TaskStatus }) =>
      api.patch<Task>(`/api/v1/tasks/${task.id}`, { status: newStatus }),
    onMutate: async ({ task, newStatus }) => {
      await queryClient.cancelQueries({ queryKey: tasksKey })
      const previous = queryClient.getQueryData<Task[]>(tasksKey)
      queryClient.setQueryData<Task[]>(tasksKey, (old) =>
        old?.map((t) => (t.id === task.id ? { ...t, status: newStatus } : t)),
      )
      setMoveError(null)
      return { previous }
    },
    onError: (err, _vars, context) => {
      if (context?.previous) queryClient.setQueryData(tasksKey, context.previous)
      setMoveError(err.message)
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: tasksKey }),
  })

  const saveTask = useMutation({
    mutationFn: (values: TaskFormValues) =>
      modal.task
        ? api.patch<Task>(`/api/v1/tasks/${modal.task.id}`, values)
        : api.post<Task>(`/api/v1/projects/${projectId}/tasks`, values),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: tasksKey })
      setModal({ open: false, task: null })
    },
  })

  const deleteTask = useMutation({
    mutationFn: (taskId: number) => api.delete(`/api/v1/tasks/${taskId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: tasksKey })
      setModal({ open: false, task: null })
    },
  })

  // One search box covering title, description, assignee name, and status
  // (both the raw value and the human label, so "in progress" and "todo" work).
  const visibleTasks = useMemo(() => {
    if (!tasks) return []
    const needle = search.trim().toLowerCase()
    if (!needle) return tasks
    return tasks.filter((t) =>
      `${t.title} ${t.description} ${t.assignee_name ?? ''} ${t.status} ${STATUS_LABELS[t.status]}`
        .toLowerCase()
        .includes(needle),
    )
  }, [tasks, search])

  const isFiltering = search.trim() !== ''

  return (
    <div className="page board-page">
      <div className="page-header">
        <div>
          <Link to="/" className="back-link">← Projects</Link>
          <h1>{project?.name ?? 'Board'}</h1>
        </div>
        <button className="btn primary" onClick={() => setModal({ open: true, task: null })}>
          New task
        </button>
      </div>

      <div className="board-toolbar">
        <input
          type="search"
          placeholder="Search by title, description, assignee, or status…"
          aria-label="Search tasks"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        {isFiltering && (
          <button className="btn ghost" onClick={() => setSearch('')}>
            Clear
          </button>
        )}
      </div>

      {moveError && (
        <p className="state-message error" role="alert">
          Could not move task: {moveError}
        </p>
      )}

      {isPending && <p className="state-message">Loading board…</p>}
      {isError && <p className="state-message error">Could not load board: {error.message}</p>}
      {tasks && tasks.length === 0 && !isFiltering && (
        <div className="empty-state">
          <p>This board is empty.</p>
          <p className="hint">Create the first task to get started.</p>
        </div>
      )}
      {tasks && tasks.length > 0 && visibleTasks.length === 0 && isFiltering && (
        <p className="state-message">No tasks match the current filters.</p>
      )}

      {tasks && tasks.length > 0 && (
        <BoardColumns
          tasks={visibleTasks}
          onMove={(task, newStatus) => moveTask.mutate({ task, newStatus })}
          onOpen={(task) => setModal({ open: true, task })}
        />
      )}

      {modal.open && (
        <TaskModal
          task={modal.task}
          users={users ?? []}
          busy={saveTask.isPending || deleteTask.isPending}
          error={
            saveTask.isError
              ? saveTask.error.message
              : deleteTask.isError
                ? deleteTask.error.message
                : null
          }
          onSave={(values) => saveTask.mutate(values)}
          onDelete={modal.task ? () => deleteTask.mutate(modal.task!.id) : null}
          onClose={() => setModal({ open: false, task: null })}
        />
      )}
    </div>
  )
}
