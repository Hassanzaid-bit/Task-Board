import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api'
import type { Project } from '../types'

export default function ProjectsPage() {
  const queryClient = useQueryClient()
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [showForm, setShowForm] = useState(false)

  const { data: projects, isPending, isError, error } = useQuery({
    queryKey: ['projects'],
    queryFn: () => api.get<Project[]>('/api/v1/projects'),
  })

  const createProject = useMutation({
    mutationFn: (body: { name: string; description: string }) =>
      api.post<Project>('/api/v1/projects', body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      setName('')
      setDescription('')
      setShowForm(false)
    },
  })

  function handleCreate(e: FormEvent) {
    e.preventDefault()
    createProject.mutate({ name, description })
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1>Projects</h1>
        <button className="btn primary" onClick={() => setShowForm((v) => !v)}>
          {showForm ? 'Cancel' : 'New project'}
        </button>
      </div>

      {showForm && (
        <form className="panel project-form" onSubmit={handleCreate}>
          <label>
            Name
            <input
              required
              maxLength={200}
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Website revamp"
            />
          </label>
          <label>
            Description
            <textarea
              maxLength={2000}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What is this project about?"
            />
          </label>
          {createProject.isError && (
            <p className="form-error" role="alert">{createProject.error.message}</p>
          )}
          <button type="submit" className="btn primary" disabled={createProject.isPending}>
            {createProject.isPending ? 'Creating…' : 'Create project'}
          </button>
        </form>
      )}

      {isPending && <p className="state-message">Loading projects…</p>}
      {isError && <p className="state-message error">Could not load projects: {error.message}</p>}
      {projects?.length === 0 && (
        <div className="empty-state">
          <p>No projects yet.</p>
          <p className="hint">Create your first project to get a board going.</p>
        </div>
      )}

      <div className="project-grid">
        {projects?.map((p) => (
          <Link key={p.id} to={`/projects/${p.id}`} className="project-card">
            <h2>{p.name}</h2>
            {p.description && <p className="project-desc">{p.description}</p>}
            <span className="badge">
              {p.task_count} {p.task_count === 1 ? 'task' : 'tasks'}
            </span>
          </Link>
        ))}
      </div>
    </div>
  )
}
