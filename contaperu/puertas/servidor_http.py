"""Puerta HTTP: la API del motor por HTTP, sin estado, con el contrato OpenConta (hito B4).

Es la puerta de entrada para un ERP nuevo escrito en cualquier lenguaje: llama por HTTP y recibe el asiento o el archivo,
sin instalar Python. Las rutas salen de la tabla de operaciones (`api.OPERACIONES`), así que dicen exactamente lo que
publica `/openconta.json`:

    POST /v1/exportar          {"documento": {...}, "driver": "concar", "configuracion": {...}}
    GET  /v1/drivers
    GET  /openconta.json       el contrato, en formato OpenAPI 3.1
    GET  /salud

Se arranca así:

    contaperu-http                                   # en 127.0.0.1:8080
    contaperu-http --host 0.0.0.0 --dominio contaperu.ejemplo.com

**Sin estado y sin nada que proteger dentro**: no guarda nada, no lee disco ni sale a la red, y cada petición trae todo
lo que necesita. Lo que sí hace, igual que el servidor MCP (`puertas/comun.py`):

- **Defensa del `Host`**: responde 421 a un nombre que no declaró. Es la defensa contra el DNS rebinding; detrás de un
  proxy hay que declarar el nombre público con `--dominio`.
- **Topes**:
  - el cuerpo de una petición se lee por trozos y se corta al pasar de 10 MiB (413);
  - el archivo que devuelve `exportar` tiene un tope de 4 MiB, como por el MCP;
  - se atienden a lo sumo `MAXIMO_CONEXIONES` peticiones a la vez (503 si llegan más);
  - una conexión inactiva se cierra a los `ESPERA_INACTIVA` segundos.

  El tiempo para leer una petición lenta lo pone el proxy, porque uvicorn no lo tiene.
- **Rechazos RFC 9457** (`application/problem+json`): 400 si el cuerpo no es un objeto JSON, 422 si el motor no puede
  hacerlo —con la `clave` estable del error—, 421 y 413 como arriba, y 500 sin enseñar el detalle.

Sin CORS: una página web ajena no debería llamar a este servidor desde el navegador de nadie. La autenticación, si hace
falta, es del proxy que lo publica.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Iterable

from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from .. import api
from .comun import (ESPERA_INACTIVA, MAXIMO_ARCHIVO, MAXIMO_CONEXIONES, MAXIMO_PETICION, hosts_permitidos,
                    peso_de_base64)

__all__ = ["DefensaDeHost", "PUERTO", "crear_app", "main"]

PUERTO = 8080
PROBLEMA = "application/problem+json"
# El tipo JSON de cada `type` de la entrada de una operación: lo que se comprueba antes de llamar a la api.
_TIPOS = {"object": dict, "array": list, "string": str, "boolean": bool, "integer": int, "null": type(None)}


def _problema(estado: int, titulo: str, detalle: str, clave: str) -> JSONResponse:
    return JSONResponse({"type": "about:blank", "status": estado, "title": titulo, "detail": detalle, "clave": clave},
                        status_code=estado, media_type=PROBLEMA)


def _host_permitido(host: str, permitidos: Iterable[str]) -> bool:
    """`localhost:*` admite `localhost` con cualquier puerto o sin él; un nombre sin `:*`, solo ese nombre."""
    for permitido in permitidos:
        if permitido.endswith(":*"):
            base = permitido[:-2]
            if host == base or (host.startswith(base + ":") and host[len(base) + 1:].isdigit()):
                return True
        elif host == permitido:
            return True
    return False


class DefensaDeHost:
    """Responde 421 a una petición cuyo `Host` no es uno de los permitidos, antes de que llegue a ninguna ruta."""

    def __init__(self, app, permitidos: Iterable[str]):
        self.app = app
        self.permitidos = list(permitidos)

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] == "http":
            host = dict(scope.get("headers") or []).get(b"host", b"").decode("latin-1")
            if not _host_permitido(host, self.permitidos):
                respuesta = _problema(421, "Host no permitido",
                                      "Este servidor no atiende ese nombre. Al publicarlo detrás de un proxy, declara el "
                                      "nombre público con --dominio.", "host_no_permitido")
                await respuesta(scope, receive, send)
                return
        await self.app(scope, receive, send)


class _Excedido(Exception):
    pass


async def _leer_cuerpo(request: Request, maximo: int) -> bytes:
    """El cuerpo, por trozos: se corta en cuanto pasa del tope, sin esperar a recibirlo entero."""
    largo = request.headers.get("content-length", "")
    if largo.isdigit() and int(largo) > maximo:
        raise _Excedido
    datos = bytearray()
    async for trozo in request.stream():
        datos += trozo
        if len(datos) > maximo:
            raise _Excedido
    return bytes(datos)


def _parametros_invalidos(op, argumentos: dict) -> str:
    """Lo que no cuadra con la entrada de la operación, en una frase; vacío si nada. Solo la forma: lo demás lo valida
    la api, una sola vez."""
    entrada = op.entrada
    desconocidos = sorted(set(argumentos) - set(entrada["properties"]))
    if desconocidos:
        return f"`{op.nombre}` no recibe {', '.join(desconocidos)}; recibe {', '.join(entrada['properties'])}"
    faltan = [nombre for nombre in entrada["required"] if nombre not in argumentos]
    if faltan:
        return f"a `{op.nombre}` le falta {', '.join(faltan)}"
    for nombre, valor in argumentos.items():
        declarado = entrada["properties"][nombre].get("type")
        tipos = tuple(_TIPOS[t] for t in ([declarado] if isinstance(declarado, str) else declarado or []))
        if tipos and (not isinstance(valor, tipos) or (isinstance(valor, bool) and bool not in tipos)):
            return f"`{nombre}` tiene que ser {' o '.join([declarado] if isinstance(declarado, str) else declarado)}"
    return ""


def _llamar(op, argumentos: dict) -> Any:
    resultado = op.funcion(**argumentos)
    if op.nombre == "exportar":
        pesa = peso_de_base64(resultado.get("contenido_base64") or "", resultado.get("zip_base64") or "")
        if pesa > MAXIMO_ARCHIVO:
            raise api.DocumentoInvalido(f"El archivo pesa {pesa // (1024 * 1024)} MB y el tope por llamada es "
                                        f"{MAXIMO_ARCHIVO // (1024 * 1024)} MB. Divide el periodo en lotes más pequeños.")
    return resultado


def _ruta(op, maximo_peticion: int) -> Route:
    async def atender(request: Request) -> Response:
        if op.metodo == "POST":
            try:
                datos = await _leer_cuerpo(request, maximo_peticion)
            except _Excedido:
                return _problema(413, "Petición demasiado grande",
                                 f"El cuerpo pasa del tope de {maximo_peticion // (1024 * 1024) or maximo_peticion} "
                                 f"{'MiB' if maximo_peticion >= 1024 * 1024 else 'bytes'} por petición.",
                                 "peticion_demasiado_grande")
            try:
                argumentos = json.loads(datos.decode("utf-8")) if datos else None
            except (UnicodeDecodeError, ValueError):
                argumentos = None
            if not isinstance(argumentos, dict):
                return _problema(400, "Cuerpo mal formado", "El cuerpo tiene que ser un objeto JSON en UTF-8.",
                                 "cuerpo_mal_formado")
        else:
            argumentos = dict(request.query_params)
        invalidos = _parametros_invalidos(op, argumentos)
        if invalidos:
            return _problema(422, "Parámetros inválidos", invalidos, "parametros_invalidos")
        try:
            resultado = await run_in_threadpool(_llamar, op, argumentos)
        except Exception as error:     # lo que el motor rechaza es un 422 con su clave; lo demás, un 500 sin detalle
            cuerpo = api.problema(error)
            return JSONResponse(cuerpo, status_code=cuerpo["status"], media_type=PROBLEMA)
        return JSONResponse(resultado)

    atender.__name__ = op.nombre
    return Route(op.ruta, atender, methods=[op.metodo])


async def _salud(request: Request) -> Response:
    return JSONResponse({"estado": "ok", "motor": api.__version__, "open_accounting": api.OPEN_ACCOUNTING})


async def _openconta(request: Request) -> Response:
    return JSONResponse(api.contrato_openconta())


async def _http_exception(request: Request, error: HTTPException) -> Response:
    titulos = {404: ("No encontrado", "ruta_desconocida"), 405: ("Método no permitido", "metodo_no_permitido")}
    titulo, clave = titulos.get(error.status_code, ("Error HTTP", "error_http"))
    return _problema(error.status_code, titulo, f"{request.method} {request.url.path}: {titulo.lower()}. Las rutas están "
                     "en /openconta.json.", clave)


def crear_app(*, dominios: Iterable[str] = (), maximo_peticion: int = MAXIMO_PETICION) -> Starlette:
    """La aplicación ASGI de la puerta: las rutas de la tabla, `/salud` y `/openconta.json`, detrás de la defensa del
    `Host` (los locales y cada `dominios` declarado)."""
    rutas = [_ruta(op, maximo_peticion) for op in api.OPERACIONES]
    rutas += [Route("/salud", _salud, methods=["GET"]), Route("/openconta.json", _openconta, methods=["GET"])]
    return Starlette(routes=rutas, middleware=[Middleware(DefensaDeHost, permitidos=hosts_permitidos(dominios))],
                     exception_handlers={HTTPException: _http_exception})


def main(argv: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(
        prog="contaperu-http",
        description="Puerta HTTP del núcleo contable del Perú, con el contrato OpenConta. Sin estado, sin red, sin base "
                    "de datos.")
    analizador.add_argument("--host", default="127.0.0.1")
    analizador.add_argument("--puerto", type=int, default=PUERTO)
    analizador.add_argument("--dominio", action="append", default=[], metavar="NOMBRE",
                            help="nombre público por el que se sirve, si va detrás de un proxy (repetible). Sin esto "
                                 "solo se atienden peticiones a localhost")
    analizador.add_argument("--version", action="version", version=f"contaperu {api.__version__}")
    args = analizador.parse_args(argv)
    if not args.dominio and args.host not in ("127.0.0.1", "localhost", "::1"):
        print("aviso: sin --dominio solo se atienden peticiones cuyo Host sea localhost; desde fuera responde 421. Al "
              "publicarlo detrás de un proxy hay que declarar el nombre público:  --dominio contaperu.ejemplo.com",
              file=sys.stderr)
    import uvicorn

    uvicorn.run(crear_app(dominios=args.dominio), host=args.host, port=args.puerto, server_header=False,
                proxy_headers=False, limit_concurrency=MAXIMO_CONEXIONES, timeout_keep_alive=ESPERA_INACTIVA)
    return 0


if __name__ == "__main__":
    sys.exit(main())
