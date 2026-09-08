# Servidor MCP de ContaPeru: contabilidad peruana determinista para agentes de IA.
#
#   docker build -t contaperu-mcp .
#   docker run -i --rm contaperu-mcp                          # por stdio
#   docker run --rm -p 8000:8000 contaperu-mcp --transporte http --host 0.0.0.0
#
# La imagen no necesita red, ni credenciales, ni volumenes: el servidor no guarda nada.
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY estandar ./estandar
COPY contaperu ./contaperu

RUN pip install --no-cache-dir ".[mcp,excel]"

# Sin privilegios: no hace falta ninguno.
RUN useradd --create-home --uid 10001 contaperu
USER contaperu

ENTRYPOINT ["contaperu-mcp"]
