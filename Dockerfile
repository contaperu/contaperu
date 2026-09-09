# Servidor MCP de ContaPeru: contabilidad peruana determinista para agentes de IA.
#
#   docker build -t contaperu-mcp .
#
#   docker run -i --rm contaperu-mcp
#       el MCP por entrada y salida estandar, para un cliente local (Claude Desktop, un IDE)
#
#   docker run --rm -p 8000:8000 contaperu-mcp contaperu-mcp --transporte http --host 0.0.0.0
#       el MCP remoto: Streamable HTTP en /mcp, que es lo que enchufa un conector
#
#   docker run --rm -v "$PWD:/data" contaperu-mcp contaperu desde-json /data/mes.json --salida /data/salida
#       la CLI: exportar a un archivo, sin levantar ningun servidor
#
# La imagen no necesita red, ni credenciales, ni volumenes: el servidor no guarda nada. El
# volumen del tercer ejemplo es solo para que la CLI deje el .xlsx en tu carpeta.
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY estandar ./estandar
COPY contaperu ./contaperu

RUN pip install --no-cache-dir ".[mcp,excel]"

# Sin privilegios: no hace falta ninguno.
RUN useradd --create-home --uid 10001 contaperu
USER contaperu

EXPOSE 8000

# ENTRYPOINT vacio a proposito: con `contaperu-mcp` fijo, la imagen solo sabria ser el servidor
# MCP y para exportar con la CLI habria que pelearse con --entrypoint. Asi, `docker run <imagen>`
# levanta el MCP (el CMD) y `docker run <imagen> contaperu ...` usa la CLI. Una imagen, dos puertas.
ENTRYPOINT []
CMD ["contaperu-mcp"]
