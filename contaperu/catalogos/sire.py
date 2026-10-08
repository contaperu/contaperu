"""El SIRE, descrito: el CANAL —a qué rutas se sube un registro— y el FORMATO —qué columna es cada campo—.

Los dos describen sin ejecutar. El motor no se conecta a SUNAT y no va a conectarse: lo que hay aquí es la
descripción de una API y de un formato ajenos, para que quien escriba su propio conector no tenga que reunirla
otra vez a mano.
"""
from __future__ import annotations

from .. import _datos
from ._fuente import mapa_de_formato

# El motor NO sale a la red y no va a salir: `tests/test_frontera.py` prohíbe importar httpx o
# socket, y `conftest.py` mata cualquier conexión. Esto no es un cliente: es la DESCRIPCIÓN de una
# API ajena —rutas, parámetros obligatorios, estados de ticket y códigos de retorno— para que quien
# escriba su propio conector no tenga que reunirla otra vez desde dos PDF que se contradicen.
#
# Es el mismo papel que ya cumplen los formatos de CONCAR, CONTASIS y STARSOFT: describir un sistema
# ajeno columna a columna sin hablar con él. Y responde al criterio del hito D7 de la hoja de ruta:
# «si la normalización se separa del transporte, la lectura de bytes puede entrar al motor y solo el
# transporte queda fuera». El transporte, las credenciales y el estado siguen fuera, y para siempre.
_API_SIRE = _datos.leer_json("datos/sunat/sire_api.json")


def api_sire() -> dict:
    """El canal del SIRE como datos: hosts, los dos grants, rutas por libro, la metadata de
    TUS, los estados del ticket y los códigos de retorno, cada bloque con su fuente.

    Quien lo use pone el transporte. Aquí no hay ni una petición."""
    return dict(_API_SIRE)


_CAMPOS_SIRE = mapa_de_formato("datos/sunat/sire_campos.json", "SIRE")
# El nombre del libro de SUNAT según el registro que se trabaja: el mismo par de siglas que usa el canal.
REGISTRO_SIRE = {True: "rvie", False: "rce"}

# El del PLE va aparte y no comparte estructura con el del SIRE más que por fuera, porque uno se LEE y el otro se
# ESCRIBE: donde el del SIRE dice `lectura` y `vuelve`, el del PLE dice `escritura` y `visto`. El `_nota` de cada



def campos_del_sire() -> dict:
    """El formato del SIRE columna a columna, con su fuente: por cada campo del anexo, su número, su
    nombre, el campo del documento donde cae —o el motivo por el que no cae— y si el TXT de reemplazo
    lo devuelve.

    Una columna que el motor no lee NO se pierde: la fila entera viaja en `datos_originales["sire"]`."""
    return dict(_CAMPOS_SIRE)


def columnas_del_sire(es_venta: bool) -> list[dict]:
    """Las columnas de un registro, en el orden del anexo."""
    return list(_CAMPOS_SIRE["libros"][REGISTRO_SIRE[es_venta]]["campos"])


def nombres_del_sire(es_venta: bool) -> list[str]:
    """Los nombres de SUNAT de los campos INFORMADOS de un registro, para que un informe diga «IGV» y
    no «campo 17». Viven aquí una sola vez: el mapa es la fuente."""
    libro = _CAMPOS_SIRE["libros"][REGISTRO_SIRE[es_venta]]
    return [c["nombre"] for c in libro["campos"] if c["n"] <= libro["campos_informados"]]

