"""El contrato de un driver de salida: lo que tiene que exponer para que el núcleo lo use.

El mismo documento sale de dos maneras —como registro o como asiento (`estandar/LEEME.md`, «Dos familias de
salida, un solo documento»)—, y hay cuatro formas de driver. Un driver implementa una:

**Familia registro** — una fila por comprobante, sin asiento:

- **`linea(c, libro, idx, opciones) -> str`** — un archivo de texto, una línea por comprobante. Es el TXT
  del SIRE: un registro para SUNAT, que se escribe desde el comprobante y no lleva cuentas.
- **`desde_comprobantes(libro, comprobantes, config, opciones) -> (bytes, resumen)`** — el archivo de un sistema
  contable que importa su registro de compras o de ventas y arma el asiento él mismo (CONTASIS). Recibe los comprobantes y la configuración, con la imputación de cada documento dentro, y
  **no decide ninguna cuenta**: las lee de `asiento.partes_de` (la de la base, o sus partes si hay reparto) y
  de `asiento.cuenta_tercero` (la del total), que las resuelven igual que para el asiento de CONCAR. No numera:
  el correlativo es del asiento, y el asiento lo arma el destino. El núcleo exige la cuenta ANTES de llamarlo.

**Familia asiento** — las líneas de la partida doble:

- **`desde_lineas(libro, lineas, config, opciones, *, indice=()) -> (bytes, resumen)`** — un archivo de asientos
  armado a partir de las LÍNEAS NEUTRALES de `open-accounting` (`asiento.LineaDiario`), ya numeradas y cuadradas.
  **Es la forma de todo driver de asientos**, CONCAR incluido desde la 1.0: el driver solo traduce vocabulario, y la
  contabilidad —cuentas, sentidos, detracción, numeración— la pone el núcleo una sola vez para todos. El núcleo exige
  el cuadre ANTES de llamarlo. Si la firma acepta `indice`, recibe además qué tramo de líneas es de qué comprobante,
  con la cabecera de sus hechos (`asiento.indice`): lo que un formato escribe en cada fila y la línea no guarda.
La forma **`construir`** —un archivo entero armado a partir de los comprobantes, con sus correlativos— se RETIRÓ en
la 4.0. Era la del Excel de CONCAR hasta la 0.10, avisaba desde la 1.0 y contradecía lo de arriba: recibiendo los
comprobantes, el driver tenía que hacer la contabilidad él mismo. Un driver que la exponga ya no carga, y el error
dice que pase a `desde_lineas`.

**El canal** — a QUIÉN se entrega lo que sale (la familia dice QUÉ se entrega). Cada driver declara su `CANAL`:

- **`legacy`** — un sistema contable instalado que importa un archivo (CONCAR, CONTASIS; STARSOFT y SISCONT cuando
  entren). Lleva cuentas y declara `EXIGE`, lo que su sistema no puede importar sin (vacío si nada).
- **`sunat`** — un registro o libro que se presenta a SUNAT, por **cualquiera de sus dos regímenes**: el SIRE (el
  RVIE y el RCE, RS 112-2021 y RS 040-2022) y el PLE (el Libro Diario y los demás, RS 234-2006 y RS 286-2009). Dos
  formas, según de qué sea su FILA: `linea` cuando es un comprobante (el SIRE, sin cuentas ni configuración) y
  `desde_lineas` cuando es una línea del asiento (el Libro Diario del PLE, que sí lleva cuentas y numera su CUO con
  el sub-diario y el correlativo). Lo que el canal fija es que escribe **texto para SUNAT**, no un Excel ni un JSON.
- **`erp`** — un ERP, por el formato neutral del estándar (el CSV, `asiento_contable`). Forma `desde_lineas`:
  proyecta la línea.

**Una palabra por destino, y es el canal.** Hasta la 7.x había una segunda tabla, `GRUPOS`, que lo traducía a «SIRE»,
«Legacy» y «ERP» para quien integra, y `drivers_disponibles` devolvía las dos. La 8.0 la retiró: eran dos vocabularios
para lo mismo, y el de fuera mentía — `tributario` son tres drivers y a los tres se les presentaba como `sire`, cuando
el PLE no es el SIRE.

**El vocabulario** — con qué palabras recibe sus líneas un driver de asientos (`VOCABULARIO`, 1.1). `legacy`, el de
siempre: siglas, sub-diarios, correlativos y el documento comodín de la detracción. `neutral`: las líneas del estándar
sin nada de eso, por `rol` y código SUNAT, para un ERP (el driver `asiento_contable`). Un driver neutral es de canal
`erp`, no declara claves legacy en su configuración y el núcleo solo le exige la cuenta.

`api_erp`, escribir el cuerpo de la API de un ERP moderno, queda reservado (hito A5): el contrato lo rechaza, y el
criterio para admitirlo es que haya un formato que `erp` no pueda llevar. Ojo a la pareja: `erp` se admite y `api_erp`
no, a una letra de distancia. **Un driver de terceros sin `CANAL` no se registra** desde la 4.0: el contrato lo cuenta
como incumplimiento y `drivers.de_terceros` lo deja fuera con su `AvisoDriver`.

Todas exponen además `NOMBRE`, `FORMATOS` ({'venta'|'compra': identificador de la salida}),
`OPCIONES` (una `kit.Opciones`, o una `kit.OpcionesArchivo` en un driver de archivo) y `nombre(libro, opciones) -> str`; las tres de archivo, su
`CONTENT_TYPE`. Opcional: `EXCLUYE_TIPOS`, los tipos SUNAT que ese destino no lleva; y, en un driver que
lleva cuentas, `EXIGE`: lo que ese sistema no puede importar sin y que el núcleo, si no se lo dicen, deja
pasar (`EXIGE_POSIBLES_ASIENTO`; en uno de registro, `EXIGE_POSIBLES_REGISTRO`). Lo que el núcleo exige se declare o
no (`EXIGE_NUCLEO_ASIENTO`, `EXIGE_NUCLEO_REGISTRO`) es aquello sin lo que no hay nada que escribir: la cuenta
contable, y en un asiento además la equivalencia del tipo, de la que sale el sub-diario. `exige(modulo)` devuelve
la unión, y es lo que `diagnosticar` lee para decidir si un mes está listo **para ese destino** — la idea
viene de Codat `options` y Merge `/meta` (ver `REFERENCIAS.md`): el destino declara qué exige antes de
que nadie escriba un byte.

Y opcional en cualquier forma, `no_caben(libro, comprobantes, config) -> {motivo: [comprobantes]}`: lo que su
formato no puede llevar aunque la contabilidad esté completa —una moneda que no tiene, un código más largo que su
columna—. `diagnosticar` lo lista antes de exportar y el núcleo se niega con `NoCabe` antes de escribir un byte, en
toda forma que lleva cuentas: un código no se corta ni una moneda se inventa.

Y opcional en un driver `desde_lineas` de columnas simples, `COLUMNAS_DE_LINEA` (1.1): el formato declarado como tabla
de `kit.columnas.ColumnaDeLinea` —cabecera, campo de la línea que la llena y su fuente—, que escribe `kit.columnas`. El
contrato exige que cada columna diga su fuente y lea un campo que existe.

Y en un driver que lleva cuentas, lo que se configura en su sección (`CONFIGURACION`, una tupla de
`configuracion.Campo`) y en qué columnas de su archivo puede ir un dato (`COLUMNAS_ELEGIBLES`, de
`configuracion.Columna`). Un driver de asientos declara al menos las claves del asiento
(`asiento.CONFIGURACION_DEL_ASIENTO`), que el núcleo lee al armar sus líneas. De lo declarado salen los valores por
defecto de su sección, su validación y la descripción con la que una aplicación pinta su pantalla
(`seccion_por_defecto`, `describir`): cada aplicación construida con el motor configura cada sistema según lo que
necesita cada empresa, sin copiar nada.

Y opcional en un driver que lleva cuentas, `CUENTAS_POR_DEFECTO` (2.5): **con qué cuentas nace una empresa que lleva
SU sistema**. Es un solo sitio (John, 23-sep-2026) con **dos oficios**, y el reparto lo decide la clave:

- **Las de la contrapartida** —`cxp`, `cxp_detraccion`, `honorarios`, `retencion_4ta`, `igv`, `clientes`— son
  CONFIGURACIÓN: `config_aplicada` las pone debajo de lo que la empresa haya guardado, y de ahí salen las líneas del
  asiento que no son la del comprobante. Las de fábrica son las del PCGE a seis dígitos —`421201`, `401111`,
  `121201`—, que es como numeran CONCAR y CONTASIS; un sistema que numera de otra forma declara las suyas.
- **`compras` y `ventas`** (`CLAVES_DEL_PLAN`, 3.0) NO son configuración: son la cuenta con la que ese sistema
  registra habitualmente una compra y una venta, y **siembran el plan de cuentas** de la empresa que lo abre, para
  que las elija (`plan_base`). **No imputan solas**: la cuenta de un comprobante viene siempre en su imputación, y
  hasta la 3.0 una cuenta por defecto la suplía y el mes salía «listo» imputado a un comodín que nadie eligió.

**No son las cuentas de nadie**: son de dónde parte quien abre ese sistema por primera vez, y en cuanto el contador
escriba la suya, manda la suya.

**Se declara el bloque ENTERO y visible** (John, 23-sep-2026), aunque repita lo de fábrica: un driver se lee de un
vistazo y no obliga a ir a buscar qué hereda. Hasta la 3.0 aquí convivían dos respuestas —CONCAR declaraba una sola
cuenta «porque las demás ya son las suyas»— y esa se retiró. Repetir un dato en dos sitios **exige un test que los
compare**, o el driver se queda atrás en silencio: están en `tests/test_cuentas_del_sistema.py`.

Los `Protocol` de abajo son la documentación tipada; lo que el registro comprueba de verdad al cargar
un driver de terceros es `incumplimientos()`, y `tests/test_contrato_drivers.py` es el examen que pasa
cualquier driver registrado.
Este manual vive en el `__init__` del paquete, que es donde lo busca quien va a escribir un driver. El
contrato era un módulo de 587 líneas con cuatro capas dentro —la taxonomía de lo que existe, los protocolos
tipados, los accesores que leen un driver y el examen que lo aprueba—, y desde la 6.2.0 cada una tiene su
fichero. **Lo que se importa no cambió**: aquí se reexportan los mismos nombres.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from ...asiento.configuracion import CONFIGURACION_DEL_ASIENTO, MONEDAS_CODIGO
from ...asiento.faltas import NoExportable
from ...asiento.motor import CENTRO_EN_ANEXO
from ...configuracion import CONFIGURACION_GENERAL, PATRON_CUENTA, Campo, Columna
from ...modelo import TIPOS_LIBRO, Comprobante, Libro
from ..kit import Opciones, OpcionesArchivo
from .accesores import (NoCabe, acepta_indice, arma_asientos, canal, centro_en_anexo, columnas_elegibles,
                        columnas_elegidas, configuracion, cuentas_por_defecto, declara_canal, describir,
                        excluye_tipos, exige, familia, forma, lleva_cuentas, no_caben, plan_base,
                        seccion_por_defecto, vocabulario)
from .examen import incumplimientos
from .protocolos import Driver, DriverAsientoLineas, DriverRegistroArchivo, DriverRegistroTexto
from .taxonomia import (CANAL_OBLIGATORIO_DESDE, CANALES, CANALES_RENOMBRADOS, CANALES_RESERVADOS, CLAVES_DEL_PLAN,
                        CLAVES_LEGACY, DATOS_CON_COLUMNAS, EXIGE_NUCLEO_ASIENTO, EXIGE_NUCLEO_NEUTRAL,
                        EXIGE_NUCLEO_REGISTRO, EXIGE_POSIBLES_ASIENTO, EXIGE_POSIBLES_REGISTRO, FAMILIA,
                        FORMAS, TIPO_DEL_PLAN, VOCABULARIO_POR_DEFECTO, VOCABULARIOS)

# Los nombres que este módulo tenía al alcance —los suyos y los que importaba—, escritos a mano porque
# están en la superficie pública congelada: un driver de terceros puede estar importando cualquiera de
# ellos de aquí, y retirarlo sin avisar rompería la promesa de la mayor anterior.
__all__ = [
    "CANALES", "CANALES_RENOMBRADOS", "CANALES_RESERVADOS", "CANAL_OBLIGATORIO_DESDE", "CENTRO_EN_ANEXO",
    "CLAVES_DEL_PLAN",
    "CLAVES_LEGACY", "CONFIGURACION_DEL_ASIENTO", "CONFIGURACION_GENERAL", "Campo", "Columna", "Comprobante",
    "DATOS_CON_COLUMNAS", "Driver", "DriverAsientoLineas", "DriverRegistroArchivo", "DriverRegistroTexto",
    "EXIGE_NUCLEO_ASIENTO", "EXIGE_NUCLEO_NEUTRAL", "EXIGE_NUCLEO_REGISTRO", "EXIGE_POSIBLES_ASIENTO",
    "EXIGE_POSIBLES_REGISTRO", "FAMILIA", "FORMAS", "Libro", "MONEDAS_CODIGO", "NoCabe", "NoExportable",
    "Opciones", "OpcionesArchivo", "PATRON_CUENTA", "TIPOS_LIBRO", "TIPO_DEL_PLAN", "TYPE_CHECKING", "VOCABULARIOS",
    "VOCABULARIO_POR_DEFECTO", "acepta_indice", "arma_asientos", "canal", "centro_en_anexo", "columnas_elegibles",
    "columnas_elegidas", "configuracion", "cuentas_por_defecto", "declara_canal", "describir", "excluye_tipos",
    "exige", "familia", "forma", "incumplimientos", "lleva_cuentas", "no_caben", "plan_base",
    "seccion_por_defecto", "vocabulario",
]
