/**
 * useSocket.js — React hook for a shared Socket.IO connection
 *
 * Usage:
 *   const { socket, connected } = useSocket();
 *
 *   useEffect(() => {
 *     if (!socket) return;
 *     socket.on('pending_update', handler);
 *     return () => socket.off('pending_update', handler);
 *   }, [socket]);
 *
 * The socket is created once per page session and shared via module scope.
 * It automatically sends the httpOnly aegis_token cookie in the handshake
 * (browsers include cookies with withCredentials=true on the upgrade request).
 *
 * The hook returns `connected: false` while connecting or if the server is
 * unreachable, so callers can fall back to polling gracefully.
 */

import { useEffect, useState } from 'react';
import { io } from 'socket.io-client';

const SOCKET_URL = 'http://localhost:5000';

// Single shared socket instance — avoids reconnecting on every render
let _socket = null;

function getSocket() {
  if (!_socket) {
    _socket = io(SOCKET_URL, {
      withCredentials: true,          // send the aegis_token cookie on handshake
      transports: ['websocket', 'polling'],  // prefer WS, fall back to long-poll
      autoConnect: true,
      reconnectionAttempts: 5,
      reconnectionDelay: 2000,
    });
  }
  return _socket;
}

export function useSocket() {
  const socket = getSocket();
  const [connected, setConnected] = useState(socket.connected);

  useEffect(() => {
    const onConnect    = () => setConnected(true);
    const onDisconnect = () => setConnected(false);

    socket.on('connect',    onConnect);
    socket.on('disconnect', onDisconnect);

    // Sync initial state in case socket already connected before this effect ran
    setConnected(socket.connected);

    return () => {
      socket.off('connect',    onConnect);
      socket.off('disconnect', onDisconnect);
    };
  }, [socket]);

  return { socket, connected };
}
