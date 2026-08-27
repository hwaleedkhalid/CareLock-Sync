"""
run_server.py — Start uvicorn with a pre-bound SO_REUSEADDR socket (Windows-safe).

On Windows, a crashed process can leave its TCP LISTEN socket in the kernel.
uvicorn's default bind() fails with WinError 10048.  This wrapper pre-creates
the socket with SO_REUSEADDR then hands it directly to uvicorn.Server so no
second bind is attempted.
"""
import asyncio
import socket
import uvicorn

HOST = "0.0.0.0"
PORT = 8003

# Pre-create and bind the socket with SO_REUSEADDR
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind((HOST, PORT))
sock.set_inheritable(True)

print(f"[run_server] Socket bound to {HOST}:{PORT} (fd={sock.fileno()})")

config = uvicorn.Config(
    "api.main:app",
    host=HOST,
    port=PORT,
    log_level="info",
)
server = uvicorn.Server(config)


async def main():
    await server.serve(sockets=[sock])


asyncio.run(main())
