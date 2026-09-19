"""OpenConta: el contrato de la puerta HTTP del motor, generado desde la tabla de operaciones (hito B3).

OpenConta es el nombre del contrato; su archivo sigue el formato OpenAPI 3.1, para que cualquier herramienta de
integración lo lea y un ERP escrito en cualquier lenguaje genere su cliente. Se genera desde `api.OPERACIONES`, así que
no se escribe a mano y no puede decir algo distinto de lo que hace la api:

- cada operación es una ruta, con su entrada como cuerpo JSON (o como parámetros, si es un GET) y su salida;
- los esquemas del estándar (`$defs` de `open-accounting.schema.json`) y los de la api (`api/esquemas/`) pasan a
  `components.schemas`, y cada `$ref` apunta dentro del documento;
- los rechazos se describen como «problem details» del RFC 9457.

No lleva `servers`: dónde se sirve lo decide quien lo despliega. Se versiona en `api/openconta.json` con una
serialización determinista; `herramientas/generar_openconta.py` lo reescribe y `tests/test_openconta.py` exige que
regenerarlo no cambie ni un byte.
"""
from __future__ import annotations

import json
from typing import Any

from .. import _datos
from .._version import OPEN_ACCOUNTING, __version__
from .tabla import BASE_ESQUEMAS, ESTANDAR, OPERACIONES

# Los esquemas de la api que entran en el contrato, en el orden en que aparecen.
ESQUEMAS = ("configuracion", "imputacion", "claves_previas", "documento_anotado", "comprobante_de_la_respuesta",
            "cuadre", "asiento", "exportacion", "diagnostico", "cuenta_pcge", "adaptacion_pcge", "drivers",
            "catalogos_sunat", "catalogos_del_estandar", "problema")
ESTANDAR_EN_COMPONENTES = "OpenAccounting"

_PROBLEMA = {"application/problem+json": {"schema": {"$ref": "#/components/schemas/problema"}}}
RESPUESTAS = {
    "MalFormado": {"description": "El cuerpo no es JSON, o no es un objeto.", "content": _PROBLEMA},
    "DemasiadoGrande": {"description": "El cuerpo pasa del tope por petición.", "content": _PROBLEMA},
    "HostNoPermitido": {"description": "El `Host` de la petición no es uno de los que el servidor declara: es la defensa "
                                       "contra el DNS rebinding.", "content": _PROBLEMA},
    "NoProcesable": {"description": "El motor no puede hacerlo con estos datos: el documento, la configuración o el mes "
                                    "no dan. `clave` dice por qué.", "content": _PROBLEMA},
    "ErrorInterno": {"description": "El motor falló. La respuesta no enseña el detalle.", "content": _PROBLEMA},
}


def _referencia(ref: str) -> str:
    """Un `$ref` del estándar o de la api → su componente dentro del contrato."""
    if ref == ESTANDAR:
        return f"#/components/schemas/{ESTANDAR_EN_COMPONENTES}"
    for prefijo in (f"{ESTANDAR}#/$defs/", "#/$defs/"):
        if ref.startswith(prefijo):
            return f"#/components/schemas/{ESTANDAR_EN_COMPONENTES}_{ref[len(prefijo):]}"
    if ref.startswith(BASE_ESQUEMAS) or ref.endswith(".schema.json"):
        return "#/components/schemas/" + ref.rsplit("/", 1)[-1].removesuffix(".schema.json")
    return ref


def _dentro(valor: Any) -> Any:
    """El esquema con cada `$ref` apuntando dentro del contrato y sin `$schema` ni `$id`, que son de un archivo suelto."""
    if isinstance(valor, dict):
        return {clave: _referencia(v) if clave == "$ref" and isinstance(v, str) else _dentro(v)
                for clave, v in valor.items() if clave not in ("$schema", "$id")}
    if isinstance(valor, list):
        return [_dentro(v) for v in valor]
    return valor


def _esquemas() -> dict[str, Any]:
    estandar = _datos.esquema_open_accounting()
    definiciones = estandar.pop("$defs", {})
    esquemas: dict[str, Any] = {ESTANDAR_EN_COMPONENTES: _dentro(estandar)}
    for nombre, definicion in definiciones.items():
        esquemas[f"{ESTANDAR_EN_COMPONENTES}_{nombre}"] = _dentro(definicion)
    for nombre in ESQUEMAS:
        esquemas[nombre] = _dentro(_datos.leer_esquema(nombre))
    for op in OPERACIONES:
        if op.metodo == "POST":
            esquemas[f"{op.nombre}_entrada"] = _dentro(op.entrada)
    return esquemas


def _operacion(op) -> dict[str, Any]:
    salida: dict[str, Any] = {"operationId": op.nombre, "summary": op.resumen, "description": op.descripcion}
    if op.metodo == "POST":
        salida["requestBody"] = {"required": True, "content": {"application/json": {
            "schema": {"$ref": f"#/components/schemas/{op.nombre}_entrada"}}}}
    else:
        entrada = op.entrada
        parametros = [{"name": nombre, "in": "query", "required": nombre in entrada["required"],
                       "schema": _dentro(esquema)} for nombre, esquema in entrada["properties"].items()]
        if parametros:
            salida["parameters"] = parametros
    respuestas: dict[str, Any] = {"200": {"description": op.resumen, "content": {"application/json": {
        "schema": _dentro(op.esquema_de_salida)}}}}
    if op.metodo == "POST":
        respuestas["400"] = {"$ref": "#/components/responses/MalFormado"}
        respuestas["413"] = {"$ref": "#/components/responses/DemasiadoGrande"}
        respuestas["422"] = {"$ref": "#/components/responses/NoProcesable"}
    respuestas["421"] = {"$ref": "#/components/responses/HostNoPermitido"}
    respuestas["500"] = {"$ref": "#/components/responses/ErrorInterno"}
    salida["responses"] = respuestas
    return salida


def _rutas_de_la_puerta() -> dict[str, Any]:
    """Las dos rutas de la puerta HTTP que no son operaciones de la api: `/salud` y el propio contrato."""
    salud = {"type": "object", "additionalProperties": False, "required": ["estado", "motor", "open_accounting"],
             "properties": {"estado": {"const": "ok"}, "motor": {"type": "string"}, "open_accounting": {"type": "string"}}}
    host = {"421": {"$ref": "#/components/responses/HostNoPermitido"}}
    return {
        "/salud": {"get": {"operationId": "salud", "summary": "Si el servidor está vivo, y con qué versión del motor.",
                           "responses": {"200": {"description": "Vivo.", "content": {"application/json": {
                               "schema": salud}}}, **host}}},
        "/openconta.json": {"get": {"operationId": "openconta", "summary": "Este contrato.",
                                    "responses": {"200": {"description": "El contrato OpenConta.", "content": {
                                        "application/json": {"schema": {"type": "object"}}}}, **host}}},
    }


def generar() -> dict[str, Any]:
    """El contrato OpenConta, armado desde la tabla de operaciones con el código de hoy."""
    return {
        "openapi": "3.1.0",
        "jsonSchemaDialect": "https://json-schema.org/draft/2020-12/schema",
        "info": {
            "title": "OpenConta",
            "version": __version__,
            "summary": "El contrato de la puerta HTTP de ContaPerú, el núcleo contable abierto del Perú.",
            "description": "Documento `open-accounting` entra, JSON sale. Sin estado: cada petición trae todo lo que "
                           "necesita y el servidor no guarda nada. Los importes viajan como texto exacto y los "
                           "archivos binarios, en base64. Los rechazos son «problem details» (RFC 9457) con una "
                           "`clave` estable.",
            "license": {"name": "MIT", "identifier": "MIT"},
            "x-open-accounting": OPEN_ACCOUNTING,
        },
        "paths": {**{op.ruta: {op.metodo.lower(): _operacion(op)} for op in OPERACIONES}, **_rutas_de_la_puerta()},
        "components": {"schemas": _esquemas(), "responses": RESPUESTAS},
    }


def texto() -> str:
    """El contrato serializado como se versiona: JSON con sangría de uno, sin escapar lo que no es ASCII, y un salto de
    línea al final. La misma tabla da siempre los mismos bytes."""
    return json.dumps(generar(), ensure_ascii=False, indent=1) + "\n"
