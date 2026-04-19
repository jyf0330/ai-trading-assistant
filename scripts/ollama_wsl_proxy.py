#!/usr/bin/env python3
import asyncio
import signal
import sys

TARGET_HOST = sys.argv[1] if len(sys.argv) > 1 else '172.26.208.1'
TARGET_PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 11434
LISTEN_HOST = sys.argv[3] if len(sys.argv) > 3 else '127.0.0.1'
LISTEN_PORT = int(sys.argv[4]) if len(sys.argv) > 4 else 11434


async def pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while not reader.at_eof():
            data = await reader.read(65536)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


async def handle(client_reader: asyncio.StreamReader, client_writer: asyncio.StreamWriter) -> None:
    upstream_reader, upstream_writer = await asyncio.open_connection(TARGET_HOST, TARGET_PORT)
    await asyncio.gather(
        pipe(client_reader, upstream_writer),
        pipe(upstream_reader, client_writer),
    )


async def main() -> None:
    server = await asyncio.start_server(handle, LISTEN_HOST, LISTEN_PORT)
    async with server:
        await server.serve_forever()


if __name__ == '__main__':
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: sys.exit(0))
    asyncio.run(main())
