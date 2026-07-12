import { useEffect, useRef, useCallback, useState } from 'react'

type MessageHandler = (data: unknown) => void

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null)
  const [connected, setConnected] = useState(false)
  const handlersRef = useRef<Map<string, MessageHandler[]>>(new Map())

  const connect = useCallback(() => {
    const apiKey = localStorage.getItem('pressarr_api_key')
    const url = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws${apiKey ? `?apikey=${apiKey}` : ''}`

    const ws = new WebSocket(url)

    ws.onopen = () => setConnected(true)

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data)
        const handlers = handlersRef.current.get(message.type) || []
        handlers.forEach((handler) => handler(message.data))
      } catch {
        // ignore malformed messages
      }
    }

    ws.onclose = () => {
      setConnected(false)
      // Auto-reconnect after 5 seconds
      setTimeout(connect, 5000)
    }

    wsRef.current = ws
  }, [])

  useEffect(() => {
    connect()
    return () => {
      wsRef.current?.close()
    }
  }, [connect])

  const on = useCallback((type: string, handler: MessageHandler) => {
    const handlers = handlersRef.current.get(type) || []
    handlers.push(handler)
    handlersRef.current.set(type, handlers)

    return () => {
      const current = handlersRef.current.get(type) || []
      handlersRef.current.set(type, current.filter((h) => h !== handler))
    }
  }, [])

  return { connected, on }
}
