"""ConsolePoker — main entry point.

Usage:
    python main.py server [--host HOST] [--port PORT] [--template TEMPLATE] [--max-players N]
    python main.py client [--host HOST] [--port PORT]
    python main.py host   [--port PORT] [--max-players N] [--template TEMPLATE]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading

# Ensure the project root is on the path
sys.path.insert(0, os.path.dirname(__file__))

from console_poker.logging_utils import configure_server_logging


def _load_template(name: str) -> dict:
    base = os.path.join(os.path.dirname(__file__), "console_poker", "data")
    path = os.path.join(base, f"{name}.json")
    if not os.path.exists(path):
        path = name  # treat as direct file path
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def cmd_server(args) -> None:
    """Run a standalone server."""
    import logging
    log_path = configure_server_logging()
    template = _load_template(args.template)
    logging.getLogger(__name__).info("Server logging to %s", log_path)
    from console_poker.server.service import serve
    serve(host=args.host, port=args.port, template=template, max_players=args.max_players)


def cmd_client(args) -> None:
    """Run the TUI client."""
    from console_poker.client.app import PokerApp
    app = PokerApp()
    # Pre-fill connection info via env vars (convenient for testing)
    app.run()


def cmd_host(args) -> None:
    """Run as host: embed server + launch client."""
    import logging
    log_path = configure_server_logging()
    template = _load_template(args.template)
    logging.getLogger(__name__).info("Host server logging to %s", log_path)

    # Start embedded server in background thread
    from console_poker.server.service import serve
    server_thread = threading.Thread(
        target=serve,
        kwargs={"host": "0.0.0.0", "port": args.port, "template": template,
                "max_players": args.max_players},
        daemon=True,
    )
    server_thread.start()
    print(f"[Host] 内嵌服务端已启动，端口 {args.port}")

    # Launch client connecting to localhost
    from console_poker.client.app import PokerApp
    app = PokerApp()
    app.run()


def main() -> None:
    parser = argparse.ArgumentParser(prog="console_poker", description="ConsolePoker 启动入口")
    subparsers = parser.add_subparsers(dest="command")

    # server sub-command
    sp_server = subparsers.add_parser("server", help="启动独立服务端")
    sp_server.add_argument("--host", default="0.0.0.0")
    sp_server.add_argument("--port", type=int, default=50051)
    sp_server.add_argument("--template", default="classic")
    sp_server.add_argument("--max-players", type=int, default=8)

    # client sub-command
    sp_client = subparsers.add_parser("client", help="启动客户端")
    sp_client.add_argument("--host", default="127.0.0.1")
    sp_client.add_argument("--port", type=int, default=50051)

    # host sub-command
    sp_host = subparsers.add_parser("host", help="房主模式（内嵌服务端+客户端）")
    sp_host.add_argument("--port", type=int, default=50051)
    sp_host.add_argument("--max-players", type=int, default=8)
    sp_host.add_argument("--template", default="classic")

    args = parser.parse_args()

    if args.command == "server":
        cmd_server(args)
    elif args.command == "client":
        cmd_client(args)
    elif args.command == "host":
        cmd_host(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
