import { useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { getToken } from '../api'

/**
 * Live-updates channel for one board. Messages are treated purely as
 * invalidation signals (see ARCHITECTURE.md): any event for this board
 * invalidates the tasks query and TanStack Query refetches.
 * Reconnects with capped exponential backoff if the connection drops.
 */
export function useBoardSocket(projectId: number) {
  const queryClient = useQueryClient()

  useEffect(() => {
    let ws: WebSocket | null = null
    let closed = false
    let attempts = 0
    let timer: ReturnType<typeof setTimeout> | undefined

    const connect = () => {
      const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
      const token = getToken() ?? ''
      ws = new WebSocket(
        `${proto}://${window.location.host}/ws/boards/${projectId}?token=${encodeURIComponent(token)}`,
      )
      ws.onopen = () => {
        attempts = 0
        // Catch up on anything missed while disconnected.
        queryClient.invalidateQueries({ queryKey: ['tasks', projectId] })
      }
      ws.onmessage = () => {
        queryClient.invalidateQueries({ queryKey: ['tasks', projectId] })
      }
      ws.onclose = () => {
        if (closed) return
        const delay = Math.min(1000 * 2 ** attempts, 15000)
        attempts += 1
        timer = setTimeout(connect, delay)
      }
    }

    connect()
    return () => {
      closed = true
      clearTimeout(timer)
      ws?.close()
    }
  }, [projectId, queryClient])
}
