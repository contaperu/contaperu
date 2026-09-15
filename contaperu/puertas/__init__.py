"""Las puertas: los protocolos por los que se llega al motor. Solo hablan con `contaperu.api`.

- `cli`          — la línea de comandos (`contaperu`)
- `servidor_mcp` — el servidor MCP para agentes de IA (`contaperu-mcp`)
- `servidor_http` — la API por HTTP para un ERP en cualquier lenguaje, con el contrato OpenConta (`contaperu-http`)
- `comun`        — lo que comparten: topes y nombres de host permitidos

Una puerta traduce un protocolo; no reimplementa el trabajo. Por eso el mismo documento sale igual por cualquiera
(`tests/test_frontera.py`).
"""
