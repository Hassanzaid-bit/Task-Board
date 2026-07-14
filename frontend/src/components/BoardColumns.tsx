import { DragDropContext, Draggable, Droppable, type DropResult } from '@hello-pangea/dnd'
import { STATUS_LABELS, TASK_STATUSES, type Task, type TaskStatus } from '../types'

type Props = {
  tasks: Task[]
  onMove: (task: Task, newStatus: TaskStatus) => void
  onOpen: (task: Task) => void
}

function formatDue(dueDate: string): { label: string; overdue: boolean } {
  const due = new Date(dueDate + 'T23:59:59')
  return {
    label: due.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' }),
    overdue: due < new Date(),
  }
}

export default function BoardColumns({ tasks, onMove, onOpen }: Props) {
  function handleDragEnd(result: DropResult) {
    if (!result.destination) return
    const newStatus = result.destination.droppableId as TaskStatus
    const task = tasks.find((t) => t.id === Number(result.draggableId))
    if (task && task.status !== newStatus) onMove(task, newStatus)
  }

  return (
    <DragDropContext onDragEnd={handleDragEnd}>
      <div className="board">
        {TASK_STATUSES.map((status) => {
          const columnTasks = tasks.filter((t) => t.status === status)
          const statusIndex = TASK_STATUSES.indexOf(status)
          const prev = TASK_STATUSES[statusIndex - 1]
          const next = TASK_STATUSES[statusIndex + 1]

          return (
            <section key={status} className={`column column-${status}`} aria-label={STATUS_LABELS[status]}>
              <header className="column-header">
                <h2>{STATUS_LABELS[status]}</h2>
                <span className="badge">{columnTasks.length}</span>
              </header>
              <Droppable droppableId={status}>
                {(provided, snapshot) => (
                  <div
                    ref={provided.innerRef}
                    {...provided.droppableProps}
                    className={`column-body ${snapshot.isDraggingOver ? 'drag-over' : ''}`}
                  >
                    {columnTasks.length === 0 && <p className="column-empty">No tasks</p>}
                    {columnTasks.map((task, index) => {
                      const due = task.due_date ? formatDue(task.due_date) : null
                      return (
                        <Draggable key={task.id} draggableId={String(task.id)} index={index}>
                          {(dragProvided, dragSnapshot) => (
                            <article
                              ref={dragProvided.innerRef}
                              {...dragProvided.draggableProps}
                              {...dragProvided.dragHandleProps}
                              className={`task-card ${dragSnapshot.isDragging ? 'dragging' : ''}`}
                              onClick={() => onOpen(task)}
                            >
                              <dl className="task-fields">
                                <div className="task-field">
                                  <dt>Title</dt>
                                  <dd className="task-title">{task.title}</dd>
                                </div>
                                <div className="task-field">
                                  <dt>Description</dt>
                                  <dd className="task-description">
                                    {task.description || '—'}
                                  </dd>
                                </div>
                                <div className="task-field">
                                  <dt>Assignee</dt>
                                  <dd>
                                    {task.assignee_name ? (
                                      <span className="assignee">{task.assignee_name}</span>
                                    ) : (
                                      <span className="assignee unassigned">Unassigned</span>
                                    )}
                                  </dd>
                                </div>
                                <div className="task-field">
                                  <dt>Due date</dt>
                                  <dd
                                    className={`due ${due?.overdue && status !== 'done' ? 'overdue' : ''}`}
                                  >
                                    {due?.label ?? '—'}
                                  </dd>
                                </div>
                              </dl>
                              <div className="task-actions" onClick={(e) => e.stopPropagation()}>
                                {prev && (
                                  <button
                                    className="btn tiny"
                                    aria-label={`Move "${task.title}" to ${STATUS_LABELS[prev]}`}
                                    onClick={() => onMove(task, prev)}
                                  >
                                    ←
                                  </button>
                                )}
                                {next && (
                                  <button
                                    className="btn tiny"
                                    aria-label={`Move "${task.title}" to ${STATUS_LABELS[next]}`}
                                    onClick={() => onMove(task, next)}
                                  >
                                    →
                                  </button>
                                )}
                              </div>
                            </article>
                          )}
                        </Draggable>
                      )
                    })}
                    {provided.placeholder}
                  </div>
                )}
              </Droppable>
            </section>
          )
        })}
      </div>
    </DragDropContext>
  )
}
