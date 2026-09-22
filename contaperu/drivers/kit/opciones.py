"""Las opciones de un driver: las microdecisiones de su formato, fuera del código."""
from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class Opciones:
    fecha: str = "AAAAMMDD"       # 'AAAAMMDD' | 'DD/MM/AAAA'
    nueva_linea: str = "\n"       # LF (archivos de referencia) | CRLF
    palote_final: bool = True     # cada línea termina en '|' (el SIRE: ver `drivers/sire/txt.py`)
    tc_pen: str = "1.000"         # tipo de cambio cuando la moneda es PEN ('' = vacío)
    cero: str = "0.00"            # cómo se escribe un importe a cero ('' = vacío)
    signo_nc: bool = True         # notas de crédito con importes en negativo
    sin_ceros: bool = True        # el número sin ceros a la izquierda (regla de contabilidad: SIRE, CONCAR y CONTASIS)
    sanear: bool = True           # quitar tildes/Ñ/controles → ASCII puro
    extension: str = ".txt"
    # SIRE Anexo 3: los campos 34-40 los "completa la Administración" y el archivo REAL que
    # SUNAT aceptó (un RVIE real de 2026, 25-ago-2026) no los manda: 33 campos y palote.
    # Mandarlos vacíos era lo que hacía el generador antes y da 40 campos por fila.
    rvie_vacios: int = 0
    # SIRE Anexo 11 (compras): aquí la nota de SUNAT dice lo CONTRARIO que en ventas —
    # "los campos 38 al 41 deberán mostrarse vacíos"—, así que van (37 + 4). Comprobado
    # contra un RCE real presentado (julio de 2026, contrastado el 27-ago-2026): el archivo
    # generado salió idéntico, 41 campos y palote. Que en ventas la nota fuera "los completa
    # la Administración" y aun así hubiera que quitarlos es el motivo de que siga siendo una
    # opción y no un número escrito en el driver: si SUNAT cambia de idea, `rce_vacios=0`.
    rce_vacios: int = 4
    codificacion: str = "ascii"

    def con(self, **cambios) -> "Opciones":
        return replace(self, **cambios)


@dataclass(frozen=True)
class OpcionesArchivo:
    """Lo que un driver de archivo nuevo necesita de sus opciones y nada del TXT del SIRE: la extensión de su archivo,
    si el número del comprobante va sin ceros a la izquierda y si la nota de crédito va en negativo. Es lo que leen el
    pipeline y el núcleo de las opciones de un driver que lleva cuentas; lo demás es de su formato."""

    extension: str = ""
    sin_ceros: bool = True
    signo_nc: bool = True
    # Cómo escribe las fechas el sistema de destino. **Vacío = como vienen**, en ISO, que es como viajan en el
    # estándar: es lo que quiere un formato de intercambio (el CSV, el asiento neutral) y por eso es el defecto.
    # Un sistema contable pide las suyas —STARSOFT, `DD/MM/AAAA`—, y hasta la 2.3 no tenía dónde decirlo: sus
    # fechas salían en ISO. Los valores son los de `Opciones.fecha` y los traduce `kit.texto.formatear_fecha`.
    fecha: str = ""
    # El archivo viaja dentro de un ZIP con su mismo nombre base (`pipeline/salida.py`). Comprimir es del
    # FORMATO y no de la forma del driver: lo pide STARSOFT, que es `desde_lineas`, igual que el TXT del SIRE,
    # que es `linea`.
    comprimir: bool = False

    def con(self, **cambios) -> "OpcionesArchivo":
        return replace(self, **cambios)
