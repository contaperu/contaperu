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


FALTAS: tuple[Falta, ...] = (
    Falta("sin_sigla", "tipo_cp", SinSigla,
          "de un tipo sin sigla en el sistema de destino", SISTEMA, "Tipos sin sigla"),
    Falta("sin_codigo_de_moneda", "moneda", SinCodigoDeMoneda,
          "en una moneda que el sistema de destino no admite", SISTEMA, "Monedas sin código"),
    Falta("reparto_no_admitido", "cuenta_unica", RepartoNoAdmitido,
          "con la base repartida entre varias cuentas, que el sistema de destino no admite", CONTADOR,
          "Reparto que el destino no admite"),
    Falta("sin_cuenta", "cuenta_contable", SinCuenta, "sin cuenta contable", CONTADOR, "Sin cuenta contable"),
    Falta("reparto_que_no_cuadra", "cuenta_contable", RepartoNoCuadra,
          "con un reparto entre cuentas que no suma la base del asiento", CONTADOR, "Reparto que no suma la base"),
    Falta("sin_centro", "centro_costo", SinCentro,
          "sin centro de costo en una cuenta que lo lleva", CONTADOR, "Sin centro de costo"),
    # Estas dos no bloquean por un requisito: el correlativo que falta arranca en 1, y lo que no cabe en el formato lo
    # declara el driver, con su motivo y su excepción (`contrato.NoCabe`).
    Falta("sin_correlativo", "", SinCorrelativo, "sub-diarios sin correlativo", SISTEMA,
          "Sub-diarios sin correlativo (arrancan en 1)"),
    Falta("no_cabe", "", None, "que el formato del destino no puede llevar", CONTADOR, "No cabe en el formato"),
)
FALTA: dict[str, Falta] = {falta.clave: falta for falta in FALTAS}
