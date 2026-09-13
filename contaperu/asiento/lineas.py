"""La línea de diario neutral: el asiento sin el vocabulario de ningún ERP.

Es el bloque `asiento` del estándar `open-accounting` y, desde la 0.7, la FUENTE del asiento: la arma
`motor.asiento_neutral()` y de ella salen todos los destinos — el Excel de CONCAR como una proyección
(`drivers/concar/proyeccion.py`), el CSV genérico, los drivers de terceros y los agentes de IA a
través del servidor MCP.

El camino inverso —de las columnas de CONCAR a la línea— vive con su driver (`drivers/concar/proyeccion.py`).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

@dataclass
class LineaDiario:
    """Una línea del asiento, en el vocabulario de `open-accounting`.

    `documento` y `referencia` llevan `tipo` (la sigla del ERP, por compatibilidad) y `tipo_cp` (el
    código SUNAT de la Tabla 10, que es el que manda). `glosa` va entera: el corte es del driver.
    `tasa_igv` es la del comprobante como texto (`"18"`, `"10.5"`), sin redondear a entero.
    """

    cuenta: str
    debe_haber: str            # 'D' | 'H'
    importe: str
    rol: str = ""              # ver `motor.ROLES`: principal, igv, retencion_4ta, tercero…
    sub_diario: str = ""
    correlativo: str = ""
    fecha: str = ""
    moneda: str = ""
    tipo_cambio: Any = ""
    glosa: str = ""
    contraparte_doc: str = ""
    centro_costo: str = ""
    anexo_auxiliar: str = ""
    documento: dict = field(default_factory=dict)
    referencia: dict = field(default_factory=dict)
    detraccion: dict = field(default_factory=dict)
    tasa_igv: Any = ""

    def a_dict(self) -> dict:
        """Sin las claves vacías: un documento `open-accounting` no lleva ruido."""
        d = asdict(self)
        return {k: v for k, v in d.items() if v not in ("", {}, None)}
