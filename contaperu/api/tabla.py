"""La tabla de operaciones: cada operación de la API con su entrada, su salida y la ruta HTTP y el nombre del MCP por los
que se expone (hito B1).

Es la fuente única de las puertas: el servidor HTTP arma sus rutas desde aquí y el contrato OpenConta se genera desde
aquí (`api/openconta.py`). La entrada de cada operación es un JSON Schema 2020-12 que sale de su firma —cada parámetro
con su esquema, obligatorio si no tiene valor por defecto— y la salida apunta a su esquema en `api/esquemas/`, que a su
vez apunta al del estándar cuando habla de un documento, un libro o una línea. `tests/test_api.py` comprueba que el MCP
expone exactamente estas herramientas y recursos; `tests/test_openconta.py`, que las respuestas reales validan.

Quedan fuera las que solo tienen sentido en Python: `leer_archivos` y `comparar_sire` reciben bytes con nombre de
archivo, `exportar_archivo` devuelve bytes, `errores_de_configuracion` ya está dentro de cada operación, y
`contrato_openconta` es el propio contrato, que la puerta HTTP sirve en `/openconta.json`.

Y `config_aplicada` (1.2), por una razón distinta: **solo le sirve a quien puede llamar a las funciones que la
consumen** —`asiento.faltantes_para`, `asiento.sub_diario`, `asiento.cuenta_tercero`…—, y esas son de la librería.
Por HTTP y por MCP la misma pregunta ya tiene respuesta, y mejor: `diagnosticar`, que dice qué falta y a quién
pedírselo sin que nadie tenga que interpretar una configuración.
"""
from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Callable

from .._version import OPEN_ACCOUNTING
from . import operaciones

# El esquema del estándar, por su `$id` (el de `estandar/open-accounting.schema.json`).
# El identificador canónico del estándar cuelga de SU tag, no del de la librería. Se construye desde la constante
# y no se escribe a mano: estaba a mano —y repetida en los esquemas de `api/esquemas/`— y por eso la 1.0 estuvo a
# punto de salir citando el tag de la 0.3. Un test comprueba que ningún `$ref` al estándar cite otro tag.
ESTANDAR = (f"https://raw.githubusercontent.com/contaperu/contaperu/open-accounting-{OPEN_ACCOUNTING}"
            "/estandar/open-accounting.schema.json")
# Y los de la api, por el suyo (`api/esquemas/<nombre>.schema.json`).
BASE_ESQUEMAS = "https://raw.githubusercontent.com/contaperu/contaperu/main/contaperu/api/esquemas/"


def esquema_de_la_api(nombre: str) -> dict:
    return {"$ref": f"{BASE_ESQUEMAS}{nombre}.schema.json"}


# El esquema de cada parámetro de la api, por su nombre: el mismo nombre significa lo mismo en toda operación.
PARAMETROS: dict[str, dict] = {
    "documento": {"type": "object", "$ref": ESTANDAR, "description": "Un documento `open-accounting`."},
    "contenido": {"type": "string", "description": "El archivo: texto tal cual o, con `es_base64`, en base64."},
    "libro": {"type": "object", "$ref": f"{ESTANDAR}#/$defs/libro", "description": "La cabecera: RUC, periodo y si son ventas o compras."},
    "es_base64": {"type": "boolean", "default": False, "description": "`contenido` viene en base64 (un ZIP, siempre)."},
    "driver": {"type": "string", "description": "El sistema de destino (`drivers_disponibles`)."},
    "configuracion": {"type": "object", **esquema_de_la_api("configuracion"), "description": "La configuración contable del contribuyente."},
    "imputacion": {"type": "object", **esquema_de_la_api("imputacion"), "description": "Lo decidido para cada documento, por `id_externo`."},
    "correlativos": {"type": "object", "additionalProperties": {"type": "integer", "minimum": 1},
                     "description": "Por qué número empieza cada sub-diario; sin él, en 1."},
    "claves_previas": {"type": "array", **esquema_de_la_api("claves_previas"),
                       "description": "Lo ya anotado en otros periodos del mismo RUC."},
    "incluir_observados": {"type": "boolean", "default": False,
                           "description": "Generar aunque haya comprobantes con observaciones que bloquean."},
    "fecha": {"type": ["string", "null"], "format": "date", "description": "La fecha de la exportación (AAAA-MM-DD)."},
    "lineas": {"type": "array", "items": {"$ref": f"{ESTANDAR}#/$defs/linea"}, "description": "Las líneas del asiento."},
    "texto": {"type": "string", "default": "", "description": "Parte del nombre de la cuenta."},
    "codigo": {"type": "string", "default": "", "description": "El código de la cuenta."},
}


@dataclass(frozen=True)
class Operacion:
    nombre: str            # el de la función en `contaperu.api`
    metodo: str            # GET si no exige nada, POST si recibe un cuerpo
    ruta: str              # la ruta HTTP
    salida: str = ""       # su esquema en `api/esquemas/`; vacío, un objeto sin más
    herramienta: str = ""  # la herramienta del MCP que la expone, si es una herramienta
    recurso: str = ""      # el recurso del MCP que la expone, si es un recurso

    @property
    def funcion(self) -> Callable:
        return getattr(operaciones, self.nombre)

    @property
    def descripcion(self) -> str:
        return inspect.getdoc(self.funcion) or ""

    @property
    def resumen(self) -> str:
        """La primera frase de la descripción."""
        primera = " ".join(self.descripcion.split("\n\n")[0].split())
        return primera.split(". ")[0].rstrip(".") + "."

    @property
    def entrada(self) -> dict:
        """El JSON Schema 2020-12 de lo que recibe: un objeto con un campo por parámetro."""
        parametros = list(inspect.signature(self.funcion).parameters.values())
        return {"type": "object", "additionalProperties": False,
                "required": [p.name for p in parametros if p.default is inspect.Parameter.empty],
                "properties": {p.name: PARAMETROS[p.name] for p in parametros}}

    @property
    def esquema_de_salida(self) -> dict:
        return esquema_de_la_api(self.salida) if self.salida else {"type": "object"}


OPERACIONES: tuple[Operacion, ...] = (
    Operacion("leer_xml", "POST", "/v1/leer_xml", "documento_anotado", herramienta="leer_xml_ubl"),
    Operacion("leer_propuesta_sire", "POST", "/v1/leer_propuesta_sire", "documento_anotado",
              herramienta="leer_propuesta_sire"),
    Operacion("revisar", "POST", "/v1/revisar", "documento_anotado", herramienta="validar_comprobantes"),
    Operacion("normalizar_detracciones", "POST", "/v1/normalizar_detracciones", "documento_anotado",
              herramienta="normalizar_detracciones"),
    Operacion("diagnosticar", "POST", "/v1/diagnosticar", "diagnostico", herramienta="diagnosticar"),
    Operacion("generar_asiento", "POST", "/v1/generar_asiento", "asiento", herramienta="generar_asiento"),
    Operacion("exportar", "POST", "/v1/exportar", "exportacion", herramienta="exportar"),
    Operacion("cuadrar", "POST", "/v1/cuadrar", "cuadre", herramienta="validar_partida_doble"),
    Operacion("buscar_cuenta_pcge", "POST", "/v1/buscar_cuenta_pcge", "cuenta_pcge", herramienta="buscar_cuenta_pcge"),
    Operacion("adaptar_pcge", "POST", "/v1/adaptar_pcge", "adaptacion_pcge", herramienta="adaptar_pcge2026"),
    Operacion("configuracion_por_defecto", "GET", "/v1/configuracion/por_defecto", "configuracion",
              herramienta="configuracion_por_defecto"),
    Operacion("describir_configuracion", "GET", "/v1/configuracion", recurso="contaperu://configuracion"),
    Operacion("drivers_disponibles", "GET", "/v1/drivers", "drivers", recurso="contaperu://drivers"),
    Operacion("catalogos_sunat", "GET", "/v1/catalogos/sunat", "catalogos_sunat", recurso="contaperu://catalogos/sunat"),
    Operacion("catalogos_del_estandar", "GET", "/v1/catalogos/estandar", "catalogos_del_estandar",
              recurso="contaperu://catalogos/estandar"),
    Operacion("catalogo_pcge", "GET", "/v1/catalogos/pcge2026", recurso="contaperu://catalogos/pcge2026"),
    Operacion("esquema_open_accounting", "GET", "/v1/estandar/open-accounting.schema.json",
              recurso="contaperu://estandar/open-accounting"),
    Operacion("esquema_diagnostico", "GET", "/v1/esquemas/diagnostico.schema.json",
              recurso="contaperu://esquemas/diagnostico"),
)


def operacion(nombre: str) -> Operacion:
    for op in OPERACIONES:
        if op.nombre == nombre:
            return op
    raise KeyError(nombre)
