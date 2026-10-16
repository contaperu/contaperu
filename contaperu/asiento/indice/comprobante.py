"""La mitad del índice que es de un COMPROBANTE: la cabecera de sus hechos, su tramo de líneas y su identidad.

Los cuarenta y tantos campos de `Cabecera` están anclados campo a campo contra el `$defs/comprobante` del estándar
—`tests/test_cabecera.py` los compara con el esquema publicado—, y ésa es la razón por la que esto no se comparte
con un movimiento: lo que esa clase promete es que el estándar y ella dicen lo mismo.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Sequence

from ...modelo import Libro, clave_de, identidad_de
from ..lineas import LineaDiario

# Las seis claves de la detracción que declara el estándar (`$defs/detraccion`, `additionalProperties: false`).
# Por eso la cabecera FILTRA en vez de copiar el bloque (`asiento.comprobante._detraccion_del_estandar`): si no, el
# documento que produce un driver fallaría su propio esquema en cuanto el bloque llevara algo de más, y puede
# llevarlo porque un `Comprobante` no vigila las claves de ese dict. Lo que SÍ pasa el filtro, además de estas seis,
# son las anotaciones del motor con guion bajo —`_tasa_tabla`, la tasa del Catálogo 54 con la que se calculó el
# monto—: el bloque las admite desde la 4.0 (enmienda 0019), y hasta la 3.10 se llamaba `tasa_tabla` y se quedaba en
# esta frontera.
# `estado` era la séptima y salió en la 2.0: su propia descripción decía que quien lee el documento NO se fía de
# él, y el motor no lo escribía nunca. El estado se deduce de la constancia y de su fecha, que son los dos datos que
# no se pueden inventar (`tributos.detracciones.estado_de`).
DETRACCION_DEL_ESTANDAR = ("codigo", "porcentaje", "monto", "cuenta", "nro_constancia", "fecha_constancia")


@dataclass(frozen=True)
class Cabecera:
    """Los hechos de un comprobante que un driver necesita al escribir sus filas y que no son de ninguna línea.

    **La regla, desde la 1.4.0: aquí está TODO hecho contable o tributario del comprobante, y ningún dato del
    proceso que lo produjo.** Lo hace cumplir `tests/test_cabecera.py`, que la compara contra el esquema del
    estándar: si el estándar gana un campo, o entra aquí o entra en la lista de los que no son hechos.

    Nació con trece campos, los que CONCAR necesitaba, y eso bastó mientras el único driver de asientos escribía
    contabilidad pura. STARSOFT rompió el supuesto: su plantilla mezcla el asiento con el registro tributario en la
    misma fila, así que pide el destino del IGV, el valor no gravado y los datos de la DUA. Un driver de REGISTRO
    (SIRE, CONTASIS) siempre los tuvo, porque recibe el comprobante entero; uno de ASIENTOS no, y se caían aquí.

    Fuera quedan los siete del proceso —`origen`, `confianza`, `archivo_nombre`, `datos_originales`, `estado`,
    `excluida`, `observaciones`—: dicen de dónde salió el dato y qué opina la validación, no qué pasó. Un driver
    que mirara `confianza` estaría decidiendo contabilidad con la certeza de un modelo de lenguaje.

    Todo en texto, como en el estándar: un importe es su `Decimal` escrito, sin redondear nada.
    """

    # Identificación
    tipo_cp: str = ""
    serie: str = ""
    numero: str = ""
    numero_final: str = ""           # solo rangos: boletas consolidadas del día
    fecha_emision: str = ""
    fecha_vencimiento: str = ""
    condicion_pago: str = ""         # CUÁNDO se paga: contado | credito
    # Las cuotas de una factura al crédito, con su fecha y su importe, ya en texto (enmienda 0030). Están aquí
    # porque la cabecera lleva TODOS los hechos: sin ellas, el documento que escribe un driver del estándar no
    # podría volver a entrar al motor con lo que el papel declaraba, que es la lección de la 3.9.
    cuotas: list = field(default_factory=list)
    monto_pendiente: str = ""        # el monto neto pendiente; vacío = el documento no lo dice, y no es cero
    medio_pago: str = ""             # CON QUÉ se paga: el código de SUNAT (`catalogos.MEDIOS_PAGO`)
    id_externo: str = ""
    # Contraparte
    contraparte_tipo_doc: str = ""   # tipo de documento de identidad: 6 RUC, 1 DNI, 4 CE, 7 pasaporte
    contraparte_doc: str = ""
    contraparte_nombre: str = ""
    concepto: str = ""               # lo que dice el comprobante que se compró o se vendió, tal cual
    # Importes
    moneda: str = ""
    tipo_cambio: str = ""
    base_gravada: str = "0"
    igv: str = "0"
    dscto_base: str = "0"            # qué parte de la base informa el SIRE como descuento; no resta al total
    dscto_igv: str = "0"
    exonerado: str = "0"
    inafecto: str = "0"
    exportacion: str = "0"
    isc: str = "0"
    base_ivap: str = "0"
    ivap: str = "0"
    icbper: str = "0"
    otros: str = "0"
    dscto_otros: str = "0"           # la parte de `otros` que el registro informa en negativo (resta del total)
    total: str = "0"
    retencion: str = "0"             # la de renta de 4ta que MUESTRA el recibo por honorarios
    # Solo compras
    destino_igv: str = "DG"          # DG gravadas | DGNG mixtas | DNG no gravadas
    valor_no_gravado: str = "0"      # YA RESUELTO: si el comprobante no lo trae, exonerado + inafecto
    anio_dua: str = ""
    cod_dep_aduanera: str = ""
    clasif_bienes: str = ""
    id_contrato: str = ""
    # Solo notas: por qué se emitió (el Catálogo 09 si es de crédito y el 10 si es de débito). Está aquí y no en el
    # bloque `referencia` de la línea porque no describe el comprobante MODIFICADO, sino la nota misma.
    tipo_nota: str = ""
    # Y CUÁL modifica: el comprobante al que apunta la nota. Viaja también en el bloque `referencia` de cada línea;
    # aquí está porque es un hecho del comprobante y la cabecera lleva todos, y porque quien escribe el documento del
    # estándar lo necesita sin tener que recomponerlo de una línea (`referencia.serie_numero` va unido por el guion).
    ref_tipo_cp: str = ""
    ref_serie: str = ""
    ref_numero: str = ""
    ref_fecha: str = ""
    # La detracción del comprobante: las claves del estándar (`DETRACCION_DEL_ESTANDAR`) y las anotaciones `_` del
    # motor, que el bloque admite desde la 4.0. Incluye la `cuenta` del Banco de la Nación, que ninguna línea lleva.
    detraccion: dict = field(default_factory=dict)

    @property
    def glosa(self) -> str:
        """Lo que se escribe en la columna de descripción: el concepto del comprobante y, si viene vacío, el nombre
        de la contraparte, en mayúsculas y sin cortar (el corte es de cada driver).

        Es una PROPIEDAD y no un campo desde la 3.9, por dos razones. No es un hecho del comprobante —es un derivado
        del `concepto`, que sí lo es— y el estándar no la declara, así que mientras fue campo era lo único que
        impedía que `a_dict()` fuese un comprobante del estándar. Y siendo derivada no puede discrepar de su fuente,
        que es lo que pasaba al construir una cabecera a mano con una glosa cualquiera.

        La misma regla que `asiento.glosa_de`, sobre los datos que la cabecera ya tiene."""
        return ((self.concepto or "").strip() or (self.contraparte_nombre or "").strip()).upper()

    def a_dict(self) -> dict:
        """Todos los campos, más la `glosa` derivada, que es la que un driver escribe en su columna.

        Lleva lo vacío a propósito: `tests/test_driver_diario_json.py` fija que un driver reciba la lista completa de
        hechos aunque este comprobante no traiga alguno. Para escribir un comprobante del estándar, `como_comprobante`.
        """
        return {**asdict(self), "glosa": self.glosa}

    def como_entrada(self) -> dict:
        """Lo mismo que `como_comprobante`, por el nombre que no dice cuál de las dos cabeceras es (ver
        `CabeceraDeMovimiento.como_entrada`)."""
        return self.como_comprobante()

    def como_comprobante(self) -> dict:
        """Esta cabecera como un `comprobante` del estándar, listo para el bloque `comprobantes` de un documento.

        Dos diferencias con `a_dict()`, y las dos son lo que hace que el resultado valide: **fuera la `glosa`**, que
        el estándar no declara porque es un derivado del concepto, y **fuera lo vacío**, porque una cadena vacía no
        pasa el `pattern` de `moneda` ni el `enum` de `contraparte_tipo_doc` — el estándar distingue «no lo sé» de
        «es esto», y lo primero se dice omitiendo la clave.

        La lista vacía entra en lo vacío por lo mismo: un comprobante al contado no declara cuotas, y escribir
        `"cuotas": []` diría «no tiene ninguna» donde lo cierto es «el documento no habla de eso».

        `tests/test_cabecera.py` lo comprueba contra el esquema publicado, campo a campo."""
        return {k: v for k, v in asdict(self).items() if v not in ("", None, {}, [])}


    @property
    def clave(self) -> tuple[str, str, str, str]:
        """La misma identidad de duplicados que `Comprobante.clave`, calculada con la misma función.

        La tiene para que `modelo.identidad_de` —que solo lee `.clave`— sirva igual para un comprobante y para la
        cabecera de su tramo. Sin esto, quien tiene el índice y no los comprobantes —un driver— tendría que
        rehacer la normalización del número y del documento, que es de donde salen los duplicados."""
        return clave_de(self.tipo_cp, self.serie, self.numero, self.contraparte_doc)


@dataclass(frozen=True)
class ComprobanteDelAsiento:
    """Un comprobante dentro del asiento del libro: su posición entre los que salieron, su sub-diario y su correlativo,
    el tramo de líneas que le toca (`desde` incluido, `hasta` excluido) y su cabecera."""

    posicion: int
    sub_diario: str
    correlativo: str
    desde: int
    hasta: int
    cabecera: Cabecera

    def lineas(self, todas: Sequence[LineaDiario]) -> list[LineaDiario]:
        """Las líneas de este comprobante dentro de las del libro."""
        return list(todas[self.desde:self.hasta])

    def a_dict(self) -> dict:
        return {"posicion": self.posicion, "sub_diario": self.sub_diario, "correlativo": self.correlativo,
                "lineas": [self.desde, self.hasta], "cabecera": self.cabecera.a_dict()}

    def identidad(self, libro: Libro) -> dict:
        """Con qué se reconoce este tramo si el documento vuelve a aparecer.

        La pregunta la contesta la ENTRADA y no `exportacion_de`, que es lo que permite que la misma función sirva
        para un comprobante y para un movimiento: cada uno sabe cómo se nombra, y el de arriba no tiene que saberlo.
        """
        return identidad_de(libro, self.cabecera)
