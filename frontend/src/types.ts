export type User = {
  id: number
  email: string
  display_name: string
}

export type Project = {
  id: number
  name: string
  description: string
  created_by: number | null
  created_at: string
  task_count: number
}

export type TaskStatus = 'todo' | 'in_progress' | 'done'

export const TASK_STATUSES: TaskStatus[] = ['todo', 'in_progress', 'done']

export const STATUS_LABELS: Record<TaskStatus, string> = {
  todo: 'To Do',
  in_progress: 'In Progress',
  done: 'Done',
}

export type Task = {
  id: number
  project_id: number
  title: string
  description: string
  status: TaskStatus
  assignee_id: number | null
  assignee_name: string | null
  due_date: string | null
  created_at: string
  updated_at: string
}
