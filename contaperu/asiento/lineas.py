"""La línea de diario neutral: el asiento sin el vocabulario de ningún ERP.

Es el bloque `asiento` del estándar `open-accounting` y, desde la 0.7, la FUENTE del asiento: la arma
`motor.lineas_del_comprobante()` y de ella salen todos los destinos — el Excel de CONCAR como una proyección
(`drivers/concar/proyeccion.py`), el CSV genérico, los drivers de terceros y los agentes de IA a
través del servidor MCP.

El camino inverso —de las columnas de CONCAR a la línea— vive con su driver (`drivers/concar/proyeccion.py`).
"""
from __future__ import annotations

import copy
from dataclasses import asdict, dataclass, field, fields
from typing import Any

@dataclass
class LineaDiario:
    """Una línea del asiento, en el vocabulario de `open-accounting`.

    `documento` y `referencia` llevan `tipo` (la sigla del ERP, por compatibilidad) y `tipo_cp` (el
    código SUNAT de la Tabla 10, que es el que manda). `glosa` va entera: el corte es del driver.
    `tasa_igv` es la del comprobante como texto (`"18"`, `"10.5"`), sin redondear a entero. El `tipo_cambio` y la `tasa`
    de la detracción también van como texto exacto (`"3.550"`, `"4"`, desde la 1.0): `float` solo al escribir una celda.
    """

    cuenta: str
    debe_haber: str            # 'D' | 'H'
    importe: str
    rol: str = ""              # ver `motor.ROLES`: principal, igv, retencion_4ta, tercero…
    # Qué es la cuenta de esta línea: activo, pasivo, patrimonio, ingreso o gasto. Obligatoria desde la 1.0, y
    # derivada del primer dígito de la cuenta (`pcge.clase_de`), no del rol: en una compra de mercadería el rol es
    # `principal` y la línea es un ACTIVO. Es lo único que un ERP de fuera entiende sin conocer el PCGE.
    clase: str = ""
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

    @classmethod
    def de_dict(cls, d: dict) -> "LineaDiario":
        """Una línea del bloque `asiento` de un documento → `LineaDiario`. Rechaza (`ValueError`) una clave que no es de
        la línea, una línea sin cuenta, sin sentido o sin importe, y un sentido que no es D ni H: una línea que llega
        por JSON no se completa adivinando."""
        if not isinstance(d, dict):
            raise ValueError("Una línea del asiento tiene que ser un objeto")
        desconocidas = sorted(set(d) - {f.name for f in fields(cls)})
        if desconocidas:
            raise ValueError(f"Claves que no son de una línea del asiento: {', '.join(desconocidas)}")
        faltan = [clave for clave in ("cuenta", "debe_haber", "importe") if not str(d.get(clave) or "").strip()]
        if faltan:
            raise ValueError(f"A la línea del asiento le falta: {', '.join(faltan)}")
        if d["debe_haber"] not in ("D", "H"):
            raise ValueError(f"debe_haber tiene que ser D o H, no {d['debe_haber']!r}")
        return cls(**copy.deepcopy(d))
