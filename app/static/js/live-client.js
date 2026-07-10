/** Stage 14: shared WebSocket client for the live teacher/student session.
 * Auto-reconnects and queues sends made while briefly disconnected.
 */
function connectLiveSocket(onMessage) {
  const protocol = location.protocol === "https:" ? "wss:" : "ws:";
  let socket = null;
  let shouldReconnect = true;
  const queue = [];

  function flushQueue() {
    while (queue.length && socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify(queue.shift()));
    }
  }

  function open() {
    socket = new WebSocket(`${protocol}//${location.host}/ws/live`);
    socket.addEventListener("open", flushQueue);
    socket.addEventListener("message", (event) => {
      try {
        onMessage(JSON.parse(event.data));
      } catch (err) {
        // malformed frame; ignore
      }
    });
    socket.addEventListener("close", () => {
      if (shouldReconnect) setTimeout(open, 1500);
    });
    socket.addEventListener("error", () => { if (socket) socket.close(); });
  }
  open();

  return {
    send(message) {
      queue.push(message);
      flushQueue();
    },
    close() {
      shouldReconnect = false;
      if (socket) socket.close();
    },
  };
}
