"""La tabla de operaciones: cada operación de la API con la ruta HTTP y el nombre del MCP por los que se expone.

Es la fuente única de las puertas: el servidor HTTP arma sus rutas desde aquí y el contrato OpenConta se genera desde
aquí. `tests/test_api.py` comprueba que el MCP expone exactamente estas herramientas y recursos.

Quedan fuera las que solo tienen sentido en Python: `leer_archivos` y `comparar_sire` reciben bytes con nombre de
archivo, `exportar_archivo` devuelve bytes, y `errores_de_configuracion` ya está dentro de cada operación.
"""
from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Callable

from . import operaciones


@dataclass(frozen=True)
class Operacion:
    nombre: str            # el de la función en `contaperu.api`
    metodo: str            # GET si no recibe nada, POST si recibe un cuerpo
    ruta: str              # la ruta HTTP
    herramienta: str = ""  # la herramienta del MCP que la expone, si es una herramienta
    recurso: str = ""      # el recurso del MCP que la expone, si es un recurso

    @property
    def funcion(self) -> Callable:
        return getattr(operaciones, self.nombre)

    @property
    def descripcion(self) -> str:
        return inspect.getdoc(self.funcion) or ""


OPERACIONES: tuple[Operacion, ...] = (
    Operacion("leer_xml", "POST", "/v1/leer_xml", herramienta="leer_xml_ubl"),
    Operacion("leer_propuesta_sire", "POST", "/v1/leer_propuesta_sire", herramienta="leer_propuesta_sire"),
    Operacion("revisar", "POST", "/v1/revisar", herramienta="validar_comprobantes"),
    Operacion("normalizar_detracciones", "POST", "/v1/normalizar_detracciones", herramienta="normalizar_detracciones"),
    Operacion("diagnosticar", "POST", "/v1/diagnosticar", herramienta="diagnosticar"),
    Operacion("generar_asiento", "POST", "/v1/generar_asiento", herramienta="generar_asiento"),
    Operacion("exportar", "POST", "/v1/exportar", herramienta="exportar"),
    Operacion("cuadrar", "POST", "/v1/cuadrar", herramienta="validar_partida_doble"),
    Operacion("buscar_cuenta_pcge", "POST", "/v1/buscar_cuenta_pcge", herramienta="buscar_cuenta_pcge"),
    Operacion("adaptar_pcge", "POST", "/v1/adaptar_pcge", herramienta="adaptar_pcge2026"),
    Operacion("configuracion_por_defecto", "GET", "/v1/configuracion/por_defecto",
              herramienta="configuracion_por_defecto"),
    Operacion("describir_configuracion", "GET", "/v1/configuracion", recurso="contaperu://configuracion"),
    Operacion("drivers_disponibles", "GET", "/v1/drivers", recurso="contaperu://drivers"),
    Operacion("catalogos_sunat", "GET", "/v1/catalogos/sunat", recurso="contaperu://catalogos/sunat"),
    Operacion("catalogo_pcge", "GET", "/v1/catalogos/pcge2026", recurso="contaperu://catalogos/pcge2026"),
    Operacion("esquema_open_accounting", "GET", "/v1/estandar/open-accounting.schema.json",
              recurso="contaperu://estandar/open-accounting"),
)


def operacion(nombre: str) -> Operacion:
    for op in OPERACIONES:
        if op.nombre == nombre:
            return op
    raise KeyError(nombre)
