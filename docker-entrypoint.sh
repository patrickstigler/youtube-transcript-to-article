#!/bin/sh
set -e
if [ "${APP_MODE}" = "mcp" ]; then
  # In containers, streamable-http on :8000 is the usual remote MCP transport; override with MCP_TRANSPORT=stdio if needed.
  export MCP_TRANSPORT="${MCP_TRANSPORT:-streamable-http}"
  exec python mcp_server.py
else
  exec python app.py
fi
