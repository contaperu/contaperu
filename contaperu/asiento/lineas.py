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

from ..pcge import clase_de

@dataclass
class LineaDiario:
    """Una línea del asiento, en el vocabulario de `open-accounting`.

    `documento` y `referencia` llevan `tipo_cp`, el código SUNAT de la Tabla 10 — **y solo eso** desde la 4.0: la
    sigla con la que cada sistema legacy llama a ese tipo la escribe su driver (`asiento.sigla_de_tipo`), que es quien
    conoce su tabla. `glosa` va entera: el corte es del driver.
    `tasa_igv` es la del comprobante como texto (`"18"`, `"10.5"`), sin redondear a entero. El `tipo_cambio` y la `tasa`
    de la detracción también van como texto exacto (`"3.550"`, `"4"`, desde la 1.0): `float` solo al escribir una celda.
    """

    cuenta: str
    debe_haber: str            # 'D' | 'H'
    importe: str
    rol: str = ""              # ver `motor.ROLES`: principal, impuesto, retencion, tercero…
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
    # QUÉ TRIBUTO es la línea de rol `impuesto`, y qué se le retiene a un tercero en la de rol `retencion`. Son los
    # dos bloques que la 5.0 trae con los renombrados, y sin ellos los nombres nuevos habrían perdido información: con
    # `igv` el tributo iba en el nombre del rol, y un rol `impuesto` a secas no sabría decir que una línea es del ISC o
    # del ICBPER.
    #
    # - `impuesto`: `{"codigo"}`, del Catálogo 05 (`catalogos.TRIBUTOS`). El motor escribe el `1000`, el IGV.
    # - `retencion`: `{"codigo", "categoria"}` — el tributo, que es el `3000`, Impuesto a la Renta, y la categoría de
    #   la Ley del Impuesto a la Renta. El motor escribe la `4`, y la sabe con certeza porque solo emite esa línea en un
    #   recibo por honorarios.
    #
    # **Ninguno lleva `tasa`, y es una decisión.** En el repositorio conviven dos convenciones —`detraccion.porcentaje`
    # es porcentaje («4, 10, 12») y `catalogos.TASA_IGV` es fracción («0.18»)—, así que un `tasa` aquí contradiría a una
    # de las dos en la misma línea que ya lleva `tasa_igv`. Y para el ICBPER no existe tasa: es un importe por bolsa.
    # En la retención el motor tampoco la conoce: el importe le llega dado en `comprobante.retencion`, y derivarla
    # sería adivinar. Si hace falta, entra con su caso real y su convención decidida.
    #
    # **Los dos SÍ entran en la huella**, al contrario que `medio_pago`: una línea de IGV y una de ISC con la misma
    # cuenta y el mismo importe son hechos distintos, así que dejarlos fuera podría darles la misma huella.
    impuesto: dict = field(default_factory=dict)
    retencion: dict = field(default_factory=dict)
    tasa_igv: Any = ""
    # CON QUÉ se movió el dinero en ESTA línea: un código de `catalogos.MEDIOS_PAGO` (Tabla 1 del Anexo 3 de la
    # RS 169-2015). Completa el bloque que abrió la enmienda 0004, que lo dejó en el comprobante y en la `Cabecera`:
    # el catálogo decía con qué se paga, pero la línea que mueve el dinero no lo llevaba. Es de la línea de rol
    # `tesoreria`, y el motor **no la emite todavía** — este campo es para quien produce ese asiento.
    #
    # **Fuera de la huella** (`huella.SIN`), y por el mismo motivo que la 0004 escribió al entrar: el medio de pago no
    # cambia ningún asiento ni ningún importe. Hasta hoy eso era cierto solo porque vivía en la `Cabecera`, que no se
    # hashea; en la línea hay que decirlo a propósito.
    medio_pago: str = ""

    def a_dict(self) -> dict:
        """Sin las claves vacías: un documento `open-accounting` no lleva ruido."""
        d = asdict(self)
        return {k: v for k, v in d.items() if v not in ("", {}, None)}

    @classmethod
    def de_dict(cls, d: dict) -> "LineaDiario":
        """Una línea del bloque `asiento` de un documento → `LineaDiario`. Rechaza (`ValueError`) una clave que no es de
        la línea, una línea sin cuenta, sin sentido, sin importe o **sin clase**, un sentido que no es D ni H, y una
        `clase` que contradice su cuenta: una línea que llega por JSON no se completa adivinando.

        **La clase se exige desde la 1.0**, que es cuando el estándar la puso en `required`: aceptar una línea sin ella
        dejaba al lector más laxo que el esquema que publica. Y se comprueba contra la cuenta porque de eso depende
        que la clase pueda quedar FUERA de la huella (`huella.SIN`): si una línea pudiera decir una clase que su
        cuenta contradice, dos asientos distintos compartirían huella."""
        if not isinstance(d, dict):
            raise ValueError("Una línea del asiento tiene que ser un objeto")
        desconocidas = sorted(set(d) - {f.name for f in fields(cls)})
        if desconocidas:
            raise ValueError(f"Claves que no son de una línea del asiento: {', '.join(desconocidas)}")
        faltan = [clave for clave in ("cuenta", "debe_haber", "importe", "clase")
                  if not str(d.get(clave) or "").strip()]
        if faltan:
            raise ValueError(f"A la línea del asiento le falta: {', '.join(faltan)}")
        if d["debe_haber"] not in ("D", "H"):
            raise ValueError(f"debe_haber tiene que ser D o H, no {d['debe_haber']!r}")
        esperada = clase_de(str(d["cuenta"]))
        if str(d["clase"]).strip() != esperada:
            raise ValueError(
                f"La cuenta {d['cuenta']} es de clase {esperada!r} y la línea dice {str(d['clase']).strip()!r}: "
                "la clase se deriva del primer dígito de la cuenta, que es el elemento del PCGE"
                if esperada else
                f"La cuenta {d['cuenta']} es de un elemento del PCGE sin clase contable (el 8 y el 0), "
                "así que ninguna clase le corresponde")
        return cls(**copy.deepcopy(d))
