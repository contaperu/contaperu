"""Armar la petición de cada operación del SIRE: el método, la URL y los parámetros. Sin enviarla.

Lo que se devuelve es un diccionario: quien tenga el socket lo convierte en una llamada con su cliente, su token y
sus reintentos. Así el motor describe la petición y nunca la hace, que es la línea de la regla 4.
"""
from __future__ import annotations

import re
from typing import Any

from .catalogo import CatalogoDelSireInvalido, _CATALOGO, _operacion, cod_libro_de

# Los huecos de una ruta, que el catálogo escribe como `{nombre}`: `{cod_libro}`, `{periodo}`, `{indEliminar}`.
_HUECO = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _vacio(valor: Any) -> bool:
    """Si un parámetro no llegó. **Un `0` SÍ llegó**, y no es un detalle: `codTipoArchivo` vale 0 para el TXT
    (`libros.cod_tipo_archivo`), así que un `if not valor` lo trataría como ausente y pediría un dato que ya está.
    Pasó al escribir esto."""
    return valor is None or (isinstance(valor, str) and not valor.strip())


def grada(operacion: str) -> str:
    """Con qué cuidado se llama: `lectura`, `escritura` o `declarativa`.

    Es lo que decide si quien envía puede llamarla sola. Una **lectura** no cambia nada en SUNAT y es idempotente;
    una **escritura** toca un mes; una **declarativa** declara de verdad ante SUNAT. Y hace falta porque el SIRE **no
    tiene ambiente de pruebas** (`sire_api.json`, `limites.ambiente_de_pruebas`): toda prueba es contra producción con
    un RUC real."""
    return str(_operacion(operacion)["grada"])


def peticion(operacion: str, *, registro: str = "", periodo: str = "", **params: Any) -> dict:
    """La petición de una operación del SIRE, lista para que otro la envíe.

    Devuelve `{operacion, metodo, url, params, grada, devuelve, cod_proceso}`. `registro` es `compra` o `venta` del
    estándar —se traduce al `cod_libro` de la API, 080000 o 140000—, `periodo` va en `AAAAMM`, y lo demás son los
    parámetros de la API tal como los nombra SUNAT (`codTipoArchivo`, `numTicket`…), para que quien lea su manual
    reconozca lo que escribe.

    **Qué se rellena solo, y por qué:** el `cod_libro` de la ruta y del parámetro `codLibro`, porque sale de
    `registro`; `codOrigenEnvio`, que vale `2` («servicio API») desde la v22 del manual —el `1` de los manuales
    anteriores da 422—, y `codOrigen`, que es ese mismo dato con el nombre que le da la descarga de lo declarado; y
    `codProceso` **solo cuando la operación lo exige y declara el suyo** (`registro_pedir`, el 70 medido): el
    catálogo lo respalda, y quien llama no tiene por qué saber que el manual dice otra cosa; y `perTributario`, cuando
    la operación lo exige y la ruta no lleva el periodo dentro (lo declarado de ventas): es el `periodo` que llegó, el
    mismo dato con el nombre de SUNAT. Nada más: un valor que el catálogo no respalde lo pone quien llama — el
    `codMoneda` y el `lisPeriodos` de lo declarado en compras, por ejemplo.

    **Y por libro, cuando el catálogo lo dice** (15.2.0): una operación puede pedir parámetros distintos y producir un
    código de proceso distinto en cada libro (`params_obligatorios_por_libro`, `cod_proceso_por_libro`). Es lo que
    pasa con lo declarado, que en compras y en ventas son dos servicios con la misma pregunta.

    **Lo que NO hace:** enviar, firmar, reintentar ni mirar el reloj. Y no toca el token: la credencial viaja con
    quien envía, nunca por aquí.
    """
    op = _operacion(operacion)
    cod_libro = str(params.pop("cod_libro", "") or "")
    if registro and not cod_libro:
        cod_libro = cod_libro_de(registro)

    ruta = str(op.get("ruta") or "")
    if not ruta:
        por_libro = op["ruta_por_libro"]
        if not cod_libro:
            raise CatalogoDelSireInvalido(
                f"La operación {operacion!r} tiene una ruta por libro: dile de qué registro es (`registro=\"compra\"` "
                f"o `\"venta\"`), o pásale su `cod_libro` ({', '.join(sorted(por_libro))}).")
        if cod_libro not in por_libro:
            raise CatalogoDelSireInvalido(
                f"La operación {operacion!r} no tiene ruta para el libro {cod_libro!r}; "
                f"la tiene para {', '.join(sorted(por_libro))}.")
        ruta = str(por_libro[cod_libro])

    # Los huecos de la ruta se llenan con lo que se sabe. `periodo` y `cod_libro` van aparte porque los nombra el
    # estándar; el resto —`indEliminar`— son de la API y llegan por `params`.
    disponibles: dict[str, Any] = {"cod_libro": cod_libro, "periodo": periodo, **params}
    huecos_de_esta = _HUECO.findall(ruta)
    for hueco in huecos_de_esta:
        if _vacio(disponibles.get(hueco)):
            raise CatalogoDelSireInvalido(
                f"La ruta de {operacion!r} necesita {hueco!r} y no llegó: {ruta}")
    ruta = _HUECO.sub(lambda m: str(disponibles[m.group(1)]), ruta)
    # Lo que se fue a la ruta no se repite en la cadena de consulta.
    usados = set(_HUECO.findall(str(op.get("ruta") or "") + "".join(op.get("ruta_por_libro", {}).values())))
    consulta = {k: v for k, v in params.items() if k not in usados}

    obligatorios = list(_del_libro(op, "params_obligatorios", cod_libro) or [])
    cod_proceso = str(_del_libro(op, "cod_proceso", cod_libro) or "")
    if "codLibro" in obligatorios and "codLibro" not in consulta and cod_libro:
        consulta["codLibro"] = cod_libro
    for nombre in ("codOrigenEnvio", "codOrigen"):      # el mismo dato: la 5.51 lo llama `codOrigen`
        if nombre in obligatorios and nombre not in consulta:
            consulta[nombre] = str(_CATALOGO["cod_origen_envio"]["valor"])
    # El periodo, con el nombre de SUNAT, donde la ruta no lo lleva dentro y la operación lo exige (lo declarado de
    # ventas). Si la ruta lo lleva, ya está en ella, y `ticket_archivo` lo recibe de quien recuerda el ticket.
    if "perTributario" in obligatorios and "perTributario" not in consulta and periodo and "periodo" not in huecos_de_esta:
        consulta["perTributario"] = periodo
    # El código de proceso va como PARÁMETRO solo donde la operación lo exige y declara el suyo. En `ticket_archivo`
    # también es obligatorio, pero ahí es el de OTRA operación —la que pidió el ticket— y lo pone quien lo recuerda.
    if "codProceso" in obligatorios and "codProceso" not in consulta and cod_proceso:
        consulta["codProceso"] = cod_proceso
    faltan = [p for p in obligatorios if _vacio(consulta.get(p))]
    if faltan:
        raise CatalogoDelSireInvalido(
            f"La operación {operacion!r} exige {', '.join(faltan)} y no llegó. Los obligatorios son "
            f"{', '.join(obligatorios)} ({op['fuente']}).")

    return {"operacion": operacion,
            "metodo": str(op["metodo"]),
            "url": f"{_CATALOGO['hosts']['sire']}/{ruta}",
            "params": consulta,
            "grada": str(op["grada"]),
            "devuelve": str(op.get("devuelve") or ""),
            # El código de proceso que ESTA operación produce, con el que luego se pide el archivo de su ticket.
            # Se inyecta como parámetro solo donde la propia operación lo exige (arriba); en `ticket_archivo` lo pone
            # quien recuerda de qué operación venía el ticket.
            "cod_proceso": cod_proceso}


def verificado(operacion: str, *, registro: str = "", cod_libro: str = "") -> str:
    """La fecha en que esa operación se MIDIÓ contra producción para ese libro, o `""` si no se ha medido.

    Es la pregunta que tiene que hacerse quien automatiza: el SIRE no tiene ambiente de pruebas y sus manuales se
    contradicen, así que «el catálogo la describe» no es lo mismo que «se la vio responder». Lo declarado (15.2.0) es el
    caso que lo pide: en compras se midió y en ventas solo está escrita del manual. Una operación medida entera
    (`verificado`) vale para sus dos libros; una medida por libro (`verificado_por_libro`), solo para los que nombra.
    """
    op = _operacion(operacion)
    if registro and not cod_libro:
        cod_libro = cod_libro_de(registro)
    return str(_del_libro(op, "verificado", cod_libro) or "")


def _del_libro(op: dict, campo: str, cod_libro: str) -> Any:
    """El valor de `campo` para ese libro: el de `<campo>_por_libro` si la operación lo declara así, y si no, el de la
    operación entera. Lo que falta en el de por libro NO cae al general: dos libros que no piden lo mismo no comparten
    lo que a uno le falta."""
    por_libro = op.get(f"{campo}_por_libro")
    if isinstance(por_libro, dict):
        return por_libro.get(cod_libro)
    return op.get(campo)
