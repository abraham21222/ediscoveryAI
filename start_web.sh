#!/bin/bash
# Start the e-discovery web dashboard

cd "$(dirname "$0")"

echo "============================================================"
echo "🌐 Starting E-Discovery Web Dashboard"
echo "============================================================"
echo ""
echo "Dashboard will be available at:"
echo "  http://localhost:8080"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

python3 web/app.py

