"""Lo que puede impedir exportar un mes a un destino, en UNA tabla: su clave en `faltantes`, el requisito del
contrato de driver que la hace bloquear, la excepción con que el núcleo se niega, el texto que lee una persona, a quién
pedírsela y el título con que la lista la CLI.

Hasta el 12-sep-2026 esto vivía en cinco sitios —`REQUISITO_DE`, `TEXTO_FALTANTE`, las claves de faltas de `PEDIR_A`,
la tupla de `por_que_no` y los títulos de la CLI—, cada uno con su orden. Ahora hay uno, el de la comprobación: primero
lo que impide clasificar (el tipo, la moneda) y después lo de cada documento.

Las reglas no están aquí: las comprueba `resolucion.faltantes_para`. Esto dice cómo se llaman y a quién se le piden.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..errores import ErrorContaperu
from ..modelo import Comprobante

# A quién se le pide. **contador**: se decide mirando el documento o el plan de cuentas. **sistema**: la configuración
# del destino o un dato público que no está en el papel. **proveedor** queda reservado (ver `operaciones.PEDIR_A`).
CONTADOR, SISTEMA, PROVEEDOR = "contador", "sistema", "proveedor"


class NoExportable(ErrorContaperu):
    """La base de todo lo que impide exportar a un destino. Quien llama atrapa esta y lee `clave` (la de su fila de
    `FALTAS`, o la propia de un driver) y `comprobantes`, vacía cuando lo que falta es un código: un tipo, una moneda,
    un sub-diario."""

    clave = ""

    def __init__(self, mensaje: str, comprobantes: list[Comprobante] | None = None):
        super().__init__(mensaje)
        self.comprobantes = list(comprobantes or [])


class SinSigla(NoExportable):
    """Comprobantes de un tipo SUNAT sin sigla configurada (`tipos.NN.sigla`): no se inventa una."""

    clave = "sin_sigla"

    def __init__(self, tipos: list[str]):
        super().__init__("Tipos SUNAT sin sigla configurada: " + ", ".join(tipos))
        self.tipos = tipos


class SinCodigoDeMoneda(NoExportable):
    """Comprobantes en una moneda sin código en el sistema de destino (`monedas_codigo`)."""

    clave = "sin_codigo_de_moneda"

    def __init__(self, monedas: list[str]):
        super().__init__("Monedas sin código en el sistema de destino: " + ", ".join(monedas))
        self.monedas = monedas


class SinDenominacion(NoExportable):
    """Cuentas del asiento que la empresa no ha dicho cómo se llaman (`denominacion_cuentas`): no se inventa un
    nombre, igual que no se inventa una sigla.

    El nombre del PCGE no sirve de reemplazo: su catálogo llega hasta cinco dígitos, así que de `101101` solo sabe
    decir «Caja» donde la empresa escribe «CAJA CHICA M.N.». Lo exige el detalle del plan contable del PLE."""

    clave = "sin_denominacion"

    def __init__(self, cuentas: list[str]):
        super().__init__("Cuentas sin denominación en el plan de la empresa: " + ", ".join(cuentas))
        self.cuentas = cuentas


class RepartoNoAdmitido(NoExportable):
    """Comprobantes con la base repartida entre varias cuentas (un `reparto` en su imputación) para un destino que
    lleva UNA cuenta por documento: CONTASIS arma un asiento por fila (John, 12-sep-2026)."""

    clave = "reparto_no_admitido"

    def __init__(self, comprobantes: list[Comprobante]):
        super().__init__(f"{len(comprobantes)} comprobante(s) con la base repartida entre varias cuentas, y el sistema "
                         "de destino lleva una sola por documento", comprobantes)


class SinCuenta(NoExportable):
    """Comprobantes incluidos sin cuenta contable (ni en su imputación ni por defecto en la configuración)."""

    clave = "sin_cuenta"

    def __init__(self, comprobantes: list[Comprobante]):
        super().__init__(f"{len(comprobantes)} comprobante(s) sin cuenta contable", comprobantes)


class SinCodigoDetraccion(NoExportable):
    """Compras que **SUNAT marcó** como sujetas al SPOT en su propuesta del SIRE (campo 38 del Anexo 8 de la RS
    040-2022) y que no traen el código del Catálogo 54 con el que se arma la detracción.

    Detiene la exportación, y no es una cortesía: **el hecho lo afirma SUNAT en su propio registro**, no lo infiere el
    motor. Un contador que acepta esa propuesta está aceptando que esos comprobantes tienen detracción, así que
    exportarlos sin ella contradice el archivo que acaba de aceptar — y lo haría en silencio, porque sin código no hay
    tasa, sin tasa el monto es 0 y la línea no nace (`motor.lineas_del_comprobante`). El asiento saldría con la cuenta
    por pagar al proveedor inflada y nadie se enteraría.

    El código no se inventa (la misma regla que `SinSigla`): de él salen la tasa de la tabla y el monto, así que
    inventarlo escribiría una tasa falsa en el asiento y un código interno falso en CONCAR. Lo pone el contador, por
    la imputación (`detraccion_codigo`), igual que pone la cuenta contable."""

    clave = "sin_codigo_detraccion"

    def __init__(self, comprobantes: list[Comprobante]):
        super().__init__(f"{len(comprobantes)} comprobante(s) que SUNAT marcó con detracción y no traen su código "
                         "del Catálogo 54", comprobantes)


class RepartoNoCuadra(NoExportable):
    """Comprobantes cuyo reparto (el de su imputación) no suma la base del asiento. Hasta el 12-sep-2026 heredaba de
    `SinCuenta` para que quien atrapaba la falta de cuenta la atrapara sin cambiar nada; ahora eso lo da `NoExportable`,
    y un reparto que no cuadra deja de pasar por una cuenta que falta."""

    clave = "reparto_que_no_cuadra"

    def __init__(self, comprobantes: list[Comprobante]):
        super().__init__(f"{len(comprobantes)} comprobante(s) con un reparto entre cuentas que no suma la base del "
                         "asiento", comprobantes)


class SinCentro(NoExportable):
    """Comprobantes sin centro de costo en una cuenta que SÍ lo lleva (columna M de CONCAR).

    La regla es del contador (06-sep-2026: obligatorio donde de verdad se escribe) y hasta el
    11-sep-2026 la aplicaba solo el portal antes de exportar; el driver de CONCAR la hace cumplir
    desde entonces (decisión de John), como la de la cuenta.
    """

    clave = "sin_centro"

    def __init__(self, comprobantes: list[Comprobante]):
        super().__init__(f"{len(comprobantes)} comprobante(s) sin centro de costo en una cuenta que lo lleva",
                         comprobantes)


class SinClase(NoExportable):
    """Comprobantes imputados a una cuenta cuyo elemento del PCGE no tiene clase contable: el 8 (saldos
    intermediarios de gestión) y el 0 (cuentas de orden). Son de cierre y de control, no de compras ni de ventas, así
    que una imputación a ellas es casi seguro un error: se dice en vez de inventarle una clase a la línea."""

    clave = "sin_clase"

    def __init__(self, comprobantes: list[Comprobante]):
        super().__init__(f"{len(comprobantes)} comprobante(s) con una cuenta de un elemento sin clase contable "
                         "(el 8 y el 0 del PCGE no la tienen)", comprobantes)


class SinCorrelativo(NoExportable):
    """Sub-diarios presentes sin correlativo de partida: el asiento no se puede numerar."""

    clave = "sin_correlativo"

    def __init__(self, sub_diarios: list[str]):
        super().__init__("Falta el correlativo de los sub-diarios " + ", ".join(sub_diarios))
        self.sub_diarios = sub_diarios


@dataclass(frozen=True)
class Falta:
    clave: str
    requisito: str                          # el de `contrato.exige` que la hace bloquear; '' = no bloquea por requisito
    excepcion: type[NoExportable] | None    # con la que se niega el núcleo; None = la declara otro (el driver)
    texto: str                              # detrás de un número: «3 sin cuenta contable»
    pedir_a: str
    titulo: str                             # el de la CLI


class AnuladaConDeposito(NoExportable):
    """Facturas marcadas como anuladas por una nota de crédito cuya detracción **ya tiene constancia de depósito**.

    Los dos hechos se contradicen y el motor no elige. Marcar la factura como anulada hace que no provisione su
    detracción, y eso es correcto cuando el depósito nunca se hizo —que es el caso normal: se anula antes de pagar—.
    Pero con una constancia de verdad el dinero SÍ salió al Banco de la Nación: suprimir esas dos líneas esconderría
    un pago real, y el asiento diría que nunca hubo obligación.

    Anular una factura cuya detracción ya se depositó es contabilidad distinta —hay que recuperar el depósito— y no
    una línea de menos. Así que se para y se dice cuál es el comprobante, en vez de elegir por el contador. El estado
    se deduce de la constancia y de su fecha, no de lo que el bloque declare (`detracciones.estado_de`)."""

    clave = "anulada_con_deposito"

    def __init__(self, comprobantes: list):
        super().__init__(f"{len(comprobantes)} factura(s) marcadas como anuladas con su detracción ya depositada")
        self.comprobantes = list(comprobantes)


FALTAS: tuple[Falta, ...] = (
    Falta("sin_sigla", "tipo_cp", SinSigla,
          "de un tipo sin sigla en el sistema de destino", SISTEMA, "Tipos sin sigla"),
    Falta("sin_codigo_de_moneda", "moneda", SinCodigoDeMoneda,
          "en una moneda que el sistema de destino no admite", SISTEMA, "Monedas sin código"),
    Falta("reparto_no_admitido", "cuenta_unica", RepartoNoAdmitido,
          "con la base repartida entre varias cuentas, que el sistema de destino no admite", CONTADOR,
          "Reparto que el destino no admite"),
    Falta("sin_cuenta", "cuenta_contable", SinCuenta, "sin cuenta contable", CONTADOR, "Sin cuenta contable"),
    Falta("sin_clase", "cuenta_contable", SinClase,
          "con una cuenta de un elemento del PCGE que no tiene clase contable (el 8 y el 0)", CONTADOR,
          "Cuenta sin clase contable"),
    Falta("reparto_que_no_cuadra", "cuenta_contable", RepartoNoCuadra,
          "con un reparto entre cuentas que no suma la base del asiento", CONTADOR, "Reparto que no suma la base"),
    Falta("sin_centro", "centro_costo", SinCentro,
          "sin centro de costo en una cuenta que lo lleva", CONTADOR, "Sin centro de costo"),
    Falta("sin_denominacion", "denominacion", SinDenominacion,
          "cuentas sin denominación en el plan de la empresa", CONTADOR, "Cuentas sin denominación"),
    Falta("sin_codigo_detraccion", "detraccion", SinCodigoDetraccion,
          "con detracción marcada por SUNAT y sin su código del Catálogo 54", CONTADOR,
          "Sin código de detracción"),
    # Esta no bloquea por un requisito que falte, sino porque dos hechos del documento se contradicen.
    Falta("anulada_con_deposito", "", AnuladaConDeposito,
          "marcadas como anuladas por una nota de crédito con su detracción ya depositada", CONTADOR,
          "Anuladas con su detracción depositada"),
    # Estas dos no bloquean por un requisito: el correlativo que falta arranca en 1, y lo que no cabe en el formato lo
    # declara el driver, con su motivo y su excepción (`contrato.NoCabe`).
    Falta("sin_correlativo", "", SinCorrelativo, "sub-diarios sin correlativo", SISTEMA,
          "Sub-diarios sin correlativo (arrancan en 1)"),
    Falta("no_cabe", "", None, "que el formato del destino no puede llevar", CONTADOR, "No cabe en el formato"),
)
FALTA: dict[str, Falta] = {falta.clave: falta for falta in FALTAS}
