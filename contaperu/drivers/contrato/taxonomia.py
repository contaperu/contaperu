"""Qué existe: los canales, los grupos, las formas, los vocabularios y lo que un driver puede exigir.

Son las tablas contra las que el examen contrasta lo que declara un driver. Están en un fichero propio
porque se leen más de lo que se cambian: quien escribe un driver viene aquí a ver qué valores hay, y quien
añade uno nuevo lo añade aquí y en ningún otro sitio.
"""
from __future__ import annotations

from ...asiento.configuracion import CONFIGURACION_DEL_ASIENTO, MONEDAS_CODIGO
from ...configuracion import CONFIGURACION_GENERAL, PATRON_CUENTA, Campo

# A quién se entrega lo que sale. Un eje distinto de la familia (registro o asiento), que dice qué se entrega.
#
# Las tres palabras son las del destino, y desde la 8.0 son las únicas: hasta la 7.x el contrato decía `tributario` e
# `intercambio` y una segunda tabla los traducía a «SIRE» y «ERP» para quien integra. Eran dos vocabularios para lo
# mismo, y el de fuera además mentía: `tributario` son tres drivers —`sire`, `ple` y `ple_plan`— y a los tres se les
# presentaba como grupo `sire`, cuando el PLE es otro régimen de SUNAT, con otras resoluciones y otro formato (la RS
# 234-2006 y la RS 286-2009 frente a la RS 112-2021 y la RS 040-2022). `sunat` cubre los dos.
#
# Y las palabras viejas describían el OTRO eje: `tributario` el formato que se escribe e `intercambio` el vocabulario
# con que se reciben las líneas — que es `VOCABULARIO` y ya tiene su campo. El canal contesta a quién se entrega.
CANALES = {
    "legacy": "un sistema contable instalado que importa un archivo",
    "sunat": "un registro o libro que se presenta a SUNAT",
    "erp": "un ERP, por el formato neutral del estándar",
}
# Los nombres con que nacieron, para que el rechazo diga el nuevo en vez de «no existe». Mismo trato que
# `configuracion.CLAVES_RETIRADAS`. La 8.0 los retira sin aviso previo y es a propósito: `CANAL` lo declara un driver,
# y los nueve que existen son de este repositorio —los ocho de serie y el `diario_json` de la batería—, así que no
# había a quién avisar. Un aviso durante la 7.x habría puesto roja la batería por sus propios drivers.
CANALES_RENOMBRADOS = {"tributario": "sunat", "intercambio": "erp"}
# Lo que tiene nombre y todavía no existe: el contrato lo rechaza diciendo por qué.
CANALES_RESERVADOS = {
    "api_erp": "escribir el cuerpo de la API de un ERP moderno es el hito A5 de la hoja de ruta: un canal nuevo solo "
               "entra si hay un formato que `erp` no pueda llevar, y el cuerpo neutral de un ERP se envía tal cual",
}
# Declarar el canal es OBLIGATORIO desde la 4.0. Hasta entonces un driver que no lo declaraba se trataba como
# `legacy` con un aviso que prometía la 2.0 —y el paquete llegó a la 3.10 con la promesa sin cumplir—. Sin canal, el
# destino se adivinaba, y de él dependen las reglas que el contrato hace cumplir.
CANAL_OBLIGATORIO_DESDE = "4.0"

# Con qué vocabulario arma el núcleo las líneas de un driver de asientos (1.1): `legacy` —siglas, sub-diarios,
# correlativos y el documento comodín de la detracción, lo que importan CONCAR y los de su familia— o `neutral`, las
# líneas del estándar sin nada de eso, por `rol` y código SUNAT, para los ERP que vienen. La contabilidad es la misma.
VOCABULARIOS = ("legacy", "neutral")
VOCABULARIO_POR_DEFECTO = "legacy"
# Lo que el núcleo exige a un driver neutral: la cuenta de cada línea. La equivalencia del tipo no, porque no hay sigla
# ni sub-diario que sacar de ella.
EXIGE_NUCLEO_NEUTRAL = frozenset({"cuenta_contable"})
# El vocabulario legacy de la configuración del asiento: lo que un driver neutral no declara. Las dos de la detracción
# —la sigla de la T.G. 06 y el mapa de la T.G. 28— salieron de `CONFIGURACION_DEL_ASIENTO` a la sección de CONCAR en la
# 4.0, y siguen siendo vocabulario legacy: se nombran a mano para que un driver neutral tampoco pueda declararlas.
CLAVES_LEGACY = frozenset({c.clave for c in CONFIGURACION_DEL_ASIENTO}
                          | {MONEDAS_CODIGO, "detraccion_tipo_doc", "detraccion_codigos"})

# En orden de preferencia: si un driver expone dos, el núcleo usa la primera.
FORMAS = ("desde_lineas", "desde_comprobantes", "linea")
FAMILIA = {"linea": "registro", "desde_comprobantes": "registro", "desde_lineas": "asiento"}

# Lo que un driver de asientos PUEDE exigir (el núcleo sabe generar sin ello): el centro de costo en
# las cuentas que lo llevan, que la moneda tenga código en el destino, y `detraccion` (4.1): el código del Catálogo 54
# de las compras que SUNAT marcó con detracción en su propuesta del SIRE. Lo declara el destino que escribe la línea de
# la detracción —sin el código no la escribiría, y en silencio—; un destino que no la lleva no tiene por qué pararse.
# Lo que exige el núcleo a todos: la cuenta contable de cada línea y la equivalencia del tipo SUNAT (de ella sale el
# sub-diario).
EXIGE_POSIBLES_ASIENTO = frozenset({"centro_costo", "moneda", "detraccion", "denominacion"})
EXIGE_NUCLEO_ASIENTO = frozenset({"cuenta_contable", "tipo_cp"})
# Y a uno de registro que lleva cuentas (`desde_comprobantes`), el núcleo le exige la cuenta —la columna con la
# que el destino arma su asiento— y nada del sub-diario ni de su equivalencia, que son del asiento. Puede exigir
# el centro de costo, y `cuenta_unica`: que ningún documento reparta su base entre varias cuentas, porque el destino
# lleva una por fila y arma un asiento por fila (CONTASIS, John 12-sep-2026). La moneda no: su código
# (`monedas_codigo`) es el de la configuración del asiento; lo que un registro no puede escribir en su propio
# vocabulario lo dice su `no_caben`.
EXIGE_POSIBLES_REGISTRO = frozenset({"centro_costo", "cuenta_unica", "detraccion"})
EXIGE_NUCLEO_REGISTRO = frozenset({"cuenta_contable"})

# Los datos que un sistema contable elige en qué columnas de su archivo escribir (`COLUMNAS_ELEGIBLES`). Hoy, el centro
# de costo (John, 13-sep-2026): se guarda una vez y la sección de cada sistema elige dónde sale.
DATOS_CON_COLUMNAS = frozenset({"centro_costo"})
# Las líneas del comprobante que pueden llevar el centro en su anexo auxiliar (`asiento.lineas_del_comprobante`).
_LINEAS_CON_ANEXO = frozenset({"principal", "tercero"})
# Lo que ninguna sección puede declarar: lo general y lo que el núcleo reserva.
_CLAVES_QUE_NO_SON_DE_UNA_SECCION = frozenset({c.clave for c in CONFIGURACION_GENERAL} | {"columnas", "imputaciones"})
# Las cuentas de lo general, contra las que se valida lo que un driver declare en `CUENTAS_POR_DEFECTO`: sus claves
# son estas y ninguna más, y cada una cumple lo que ya cumplía (el patrón de una cuenta, o el objeto PEN/USD).
_CUENTAS_GENERALES: tuple[Campo, ...] = next((c.campos for c in CONFIGURACION_GENERAL if c.clave == "cuentas"), ())
# Las dos claves que NO son configuración y por eso no están en lo general: la cuenta con la que ese sistema registra
# una compra y la de una venta. Siembran el plan de cuentas de la empresa (`plan_base`) y no imputan nada. El `tipo`
# de la fila sale de la clave, y son los dos únicos que admite un plan: gasto e ingreso.
TIPO_DEL_PLAN: dict[str, str] = {"compras": "gasto", "ventas": "ingreso"}
CLAVES_DEL_PLAN: tuple[str, ...] = tuple(TIPO_DEL_PLAN)
_CUENTAS_DEL_PLAN: tuple[Campo, ...] = tuple(
    Campo(clave, "texto", "", titulo=titulo, grupo="cuentas", patron=PATRON_CUENTA)
    for clave, titulo in (("compras", "Cuenta de compras del sistema"), ("ventas", "Cuenta de ventas del sistema")))

