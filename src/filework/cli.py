import argparse
import json
from pathlib import Path

from .agent import run
from .documents import Workspace


def main():
    parser = argparse.ArgumentParser(description="Filework invoice assistant")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve", help="Open the local interface")
    serve.add_argument("--port", type=int, default=8765)
    task = sub.add_parser("run", help="Preview a task without writing any report")
    task.add_argument("request")
    task.add_argument("--workspace", type=Path, default=Path("demo/documents"))
    task.add_argument("--mode", choices=["baseline", "llm"], default="baseline")
    args = parser.parse_args()
    if args.command == "serve":
        import uvicorn
        from .server import create_app
        uvicorn.run(create_app(), host="127.0.0.1", port=args.port)
    else:
        result = run(args.request, Workspace(args.workspace), args.mode)
        print(json.dumps(result, indent=2))
        if result["status"] == "failed":
            raise SystemExit(1)


if __name__ == "__main__":
    main()
