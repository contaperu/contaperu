"""Los tests corren sin red, y aquí deja de ser una intención para pasar a ser un hecho.

El CI lo pedía en un comentario de YAML —«Sin red y sin credenciales: si un test necesita cualquiera
de las dos, está mal planteado»—, pero nada lo impedía: un test podía abrir un socket y nadie se
enteraría hasta que la suite fallara un día sin internet, o —peor— hasta que pasara en verde
gastando la cuota de una API de verdad.

Importa para lo que este paquete ES. `contaperu` promete en su README «sin base de datos, sin estado,
sin llamadas a la red», y esa promesa es la razón de que el mismo código pueda servir a un estudio
contable, a un desarrollador y a un agente de IA. Un test que salga a internet la rompe en silencio.

Localhost queda permitido a propósito: el servidor MCP se prueba levantándolo contra sí mismo, y eso
no es «la red», es el propio proceso.
"""
from __future__ import annotations

import socket

import pytest

LOCALES = {"127.0.0.1", "::1", "localhost"}


class RedProhibida(RuntimeError):
    """Un test intentó salir a internet. No es un fallo de la red: es un test mal planteado."""


@pytest.fixture(autouse=True, scope="session")
def sin_red():
    """Sustituye `socket.socket.connect` por uno que solo deja pasar localhost.

    Se parchea `connect` y no la clase entera porque crear un socket es inofensivo —`zipfile` y
    `http.client` lo hacen al importarse—; lo que no puede ocurrir es que llegue a conectar.
    """
    original = socket.socket.connect
    original_ex = socket.socket.connect_ex

    def guardia(fn):
        def envuelto(self, direccion, *args, **kwargs):
            destino = direccion[0] if isinstance(direccion, tuple) else direccion
            if str(destino) not in LOCALES:
                raise RedProhibida(
                    f"Un test intentó conectar con {destino!r}. Los tests de contaperu corren sin "
                    "red: si algo la necesita, es que la regla que se está probando no vive donde "
                    "debería — el núcleo no sale a internet.")
            return fn(self, direccion, *args, **kwargs)
        return envuelto

    socket.socket.connect = guardia(original)
    socket.socket.connect_ex = guardia(original_ex)
    try:
        yield
    finally:
        socket.socket.connect = original
        socket.socket.connect_ex = original_ex
