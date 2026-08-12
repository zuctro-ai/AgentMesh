import asyncio
import os
import signal
from grpc_service.server import create_grpc_server


async def main():
    port = int(os.getenv("GRPC_PORT", "50051"))
    server = create_grpc_server(port=port)
    await server.start()
    print(f"🛡️ [AgentMesh gRPC Microservice] Server running on port [::{port}]")

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    await stop.wait()
    print("Shutting down gRPC microservice...")
    await server.stop(5)


if __name__ == "__main__":
    asyncio.run(main())
