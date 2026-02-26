import { useEffect, useCallback } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'

import { getQueue, type QueueEntry } from '@/api/queue'
import { useWebSocket } from './useWebSocket'

export function useQueue() {
  const queryClient = useQueryClient()
  const { on } = useWebSocket()

  const { data: queue = [], isLoading, isError } = useQuery({
    queryKey: ['queue'],
    queryFn: getQueue,
    refetchInterval: 5000,
  })

  const invalidate = useCallback(
    () => queryClient.invalidateQueries({ queryKey: ['queue'] }),
    [queryClient],
  )

  useEffect(() => {
    const unsubAdd = on('queue:added', () => invalidate())
    const unsubRemove = on('queue:removed', () => invalidate())
    const unsubUpdate = on('queue:updated', (data) => {
      const updated = data as QueueEntry
      queryClient.setQueryData<QueueEntry[]>(['queue'], (prev) => {
        if (!prev) return prev
        return prev.map((item) => (item.id === updated.id ? updated : item))
      })
    })

    return () => {
      unsubAdd()
      unsubRemove()
      unsubUpdate()
    }
  }, [on, invalidate, queryClient])

  return { queue, isLoading, isError, invalidate }
}
