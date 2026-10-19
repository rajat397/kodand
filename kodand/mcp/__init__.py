"""
kodand.mcp - MCP server for kodand (stdio only)
Provides memory operations via the Model Context Protocol.
Recall everywhere, enforcement only where hooks exist.
"""

import asyncio
import json
import sys
from typing import Any, Dict

from kodand.store import get_store
from kodand.recall import create_recall_engine
from kodand.trust import TrustSurface
from kodand.warmstart import create_warm_start
from kodand.harness_adapter import create_adapter


class KodandMCPServer:
    """MCP server for kodand.
    
    Provides memory operations via the Model Context Protocol.
    Recall everywhere (read path), enforcement only where hooks exist.
    """
    
    def __init__(self, repo_path: str = None):
        self.repo_path = repo_path or os.getcwd()
        self.store = get_store(self.repo_path)
        self.recall_engine = create_recall_engine(self.repo_path)
        self.trust_surface = TrustSurface(self.repo_path)
        self.warmstart = create_warm_start(self.repo_path)
        self.adapter = create_adapter(self.repo_path)
    
    async def handle_request(self, request: dict) -> dict:
        """Handle an MCP request."""
        method = request.get("method", "")
        params = request.get("params", {})
        
        try:
            if method == "initialize":
                return {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {
                            "tools": {},
                            "resources": {},
                        },
                        "serverInfo": {"name": "kodand", "version": "0.1.0"},
                    },
                }
            
            elif method == "tools/list":
                return {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "result": {
                        "tools": [
                            {
                                "name": "kodand_remember",
                                "description": "Store a memory entry",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo_id": {"type": "string"},
                                        "title": {"type": "string"},
                                        "content": {"type": "string"},
                                        "scope": {"type": "string", "default": "repo"},
                                        "kind": {"type": "string", "default": "reference"},
                                        "confidence": {"type": "string", "default": "medium"},
                                        "locator": {"type": "string", "default": ""},
                                    },
                                    "required": ["repo_id", "title", "content"],
                                },
                            },
                            {
                                "name": "kodand_recall",
                                "description": "Search and recall memories",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo_id": {"type": "string"},
                                        "query": {"type": "string"},
                                        "limit": {"type": "integer", "default": 10},
                                        "scope": {"type": "string"},
                                    },
                                    "required": ["repo_id"],
                                },
                            },
                            {
                                "name": "kodand_prospective",
                                "description": "Prospective recall based on context",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo_id": {"type": "string"},
                                        "file_path": {"type": "string"},
                                        "symbol": {"type": "string"},
                                        "command": {"type": "string"},
                                    },
                                    "required": ["repo_id"],
                                },
                            },
                            {
                                "name": "kodand_trust_list",
                                "description": "List trust surface entries",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo_id": {"type": "string"},
                                        "scope": {"type": "string"},
                                    },
                                    "required": ["repo_id"],
                                },
                            },
                            {
                                "name": "kodand_trust_inspect",
                                "description": "Inspect a memory entry",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo_id": {"type": "string"},
                                        "entry_id": {"type": "integer"},
                                    },
                                    "required": ["repo_id", "entry_id"],
                                },
                            },
                            {
                                "name": "kodand_warm_start",
                                "description": "Get warm start context for session start",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo_id": {"type": "string"},
                                    },
                                    "required": ["repo_id"],
                                },
                            },
                        ],
                    },
                }
            
            elif method == "tools/call":
                return await self._handle_tool_call(params)
            
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "error": {"code": -32601, "message": f"Method not found: {method}"},
                }
        
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "error": {"code": -32603, "message": str(e)},
            }

    async def _handle_tool_call(self, params: dict) -> dict:
        """Handle tool call requests."""
        name = params.get("name", "")
        args = params.get("arguments", {})
        
        if name == "kodand_remember":
            entry = self.store.remember(
                content=args.get("content", ""),
                surface="text",
                locator=args.get("locator", ""),
                scope=args.get("scope", "repo"),
                session_id="mcp",
            )
            return {
                "jsonrpc": "2.0",
                "id": params.get("id"),
                "result": {"content": [{"type": "text", "text": json.dumps(entry)}]},
            }
        
        elif name == "kodand_recall":
            results = self.recall_engine.recall(
                query=args.get("query", ""),
                k=args.get("limit", 10),
                scope=args.get("scope"),
            )
            return {
                "jsonrpc": "2.0",
                "id": params.get("id"),
                "result": {"content": [{"type": "text", "text": json.dumps(results)}]},
            }
        
        elif name == "kodand_prospective":
            results = self.recall_engine.prospective_recall(context)
            return {
                "jsonrpc": "2.0",
                "id": params.get("id"),
                "result": {"content": [{"type": "text", "text": json.dumps(results)}]},
            }
        
        elif name == "kodand_trust_list":
            entries = self.trust_surface.list()
            return {
                "jsonrpc": "2.0",
                "id": params.get("id"),
                "result": {"content": [{"type": "text", "text": json.dumps(entries)}]},
            }
        
        elif name == "kodand_trust_inspect":
            entry = self.trust_surface.inspect(args.get("entry_id"))
            return {
                "jsonrpc": "2.0",
                "id": params.get("id"),
                "result": {"content": [{"type": "text", "text": json.dumps(entry)}]},
            }
        
        elif name == "kodand_warm_start":
            context = self.warmstart.get_warm_context()
            return {
                "jsonrpc": "2.0",
                "id": params.get("id"),
                "result": {"content": [{"type": "text", "text": text}]},
            }
        
        else:
            return {
                "jsonrpc": "2.0",
                "id": params.get("id"),
                "error": {"code": -32602, "message": f"Unknown tool: {name}"},
            }

    async def run_stdio(self):
        """Run the MCP server over stdio."""
        while True:
            try:
                line = sys.stdin.readline()
                if not line:
                    break
                request = json.loads(line)
                response = await self.handle_request(request)
                print(json.dumps(response), flush=True)
            except json.JSONDecodeError:
                print(json.dumps({"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}}), flush=True)
            except Exception as e:
                print(json.dumps({"jsonrpc": "2.0", "error": {"code": -32603, "message": str(e)}}), flush=True)


import os


def main():
    """Entry point for the MCP server."""
    import asyncio
    import sys
    
    repo_path = sys.argv[1] if len(sys.argv) > 1 else None
    server = KodandMCPServer(repo_path)
    asyncio.run(server.run_stdio())


if __name__ == "__main__":
    main()