"""El comprobante: una fila del registro de compras o de ventas, con lo que dice el papel y nada más.

Va junto con su **identidad** —`clave_de` e `identidad_de`— porque son lo mismo visto de otra forma: qué
cuatro datos distinguen un comprobante de otro, que es la pregunta que decide un duplicado.

`Comprobante` se queda entero, con sus cuarenta campos y su lector estricto: partir una dataclass por tamaño
dejaría la mitad de los campos lejos de la regla que los valida.
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields
from datetime import date
from decimal import Decimal
from typing import Any

from .coerciones import CENTIMO, CERO, fecha, monto, solo_digitos, tipo_cambio
from .libro import Libro

ORIGENES = ("xml", "pdf_texto", "vision", "manual", "sire")  # sire = importado de la propuesta de SUNAT
# Lo que declara el documento sobre su pago. En la factura electrónica es obligatorio desde 2021 (UBL
# `PaymentTerms FormaPago`: «Contado», o «Credito» con sus cuotas). Vacío = el documento no lo dice.
CONDICIONES_PAGO = ("contado", "credito")

# Qué tipos de la Tabla 10 son una nota, y cuáles de ellas restan. **Con nombre desde la 3.4.0**, que no
# es cosmética: estaba dentro de las dos propiedades de abajo, así que quien resumía un libro fuera del
# motor no tenía nada que citar y lo escribía a mano. La primera aplicación que lo hizo se quedó con el
# `07` y se dejó el `87` —la nota de crédito de no domiciliado—, así que esa **sumaba en vez de restar**:
# el importe entraba con el signo contrario y el total cuadraba consigo mismo. Un nombre público es lo
# que permite que la próxima lo pregunte en vez de deducirlo.
NOTAS_CREDITO = ("07", "87")             # 07 domiciliado · 87 no domiciliado
NOTAS_DEBITO = ("08", "88")              # las hermanas que suman
NOTAS = NOTAS_CREDITO + NOTAS_DEBITO

# ── Quién escribe cada campo (3.4.0) ────────────────────────────────────────────────────────────
#
# El esquema del estándar ya lo dice en prosa, campo por campo; lo que faltaba era poder **preguntarlo**.
# Sirve para una cosa concreta y frecuente: cualquier ERP que abra una puerta de entrada —una API, un
# formulario, un agente al que se le dicta una factura— tiene que decidir qué acepta de quien escribe, y
# hasta la 3.4 lo escribía a mano. La primera aplicación que lo hizo se dejó cinco campos que su propia
# base ya guardaba (los descuentos, el ICBPER, el valor no gravado y el destino del IGV): se perdían sin
# error y sin aviso, porque una lista escrita a mano no se queja de lo que le falta.
#
# Tres tramos que no se solapan y cubren el comprobante entero. Lo comprueba `tests/test_campos.py`, y eso
# es el valor: un campo nuevo en el modelo que nadie reparta deja el test rojo.
CAMPOS_DEL_DOCUMENTO = (
    "tipo_cp", "serie", "numero", "numero_final", "fecha_emision", "fecha_vencimiento",
    "condicion_pago", "medio_pago", "contraparte_tipo_doc", "contraparte_doc", "contraparte_nombre",
    "moneda", "tipo_cambio", "base_gravada", "igv", "dscto_base", "dscto_igv", "exonerado", "inafecto",
    "exportacion", "isc", "base_ivap", "ivap", "icbper", "otros", "dscto_otros", "total", "retencion", "destino_igv",
    "valor_no_gravado", "anio_dua", "cod_dep_aduanera", "clasif_bienes",
    "tipo_nota", "ref_fecha", "ref_tipo_cp", "ref_serie", "ref_numero", "detraccion", "id_contrato", "concepto",
)
# Lo que pone el sistema que lo produce: de dónde salió el dato y cómo se le llama desde fuera. Nada de
# esto lo dice el papel, así que una puerta de entrada no lo acepta de quien dicta. Y lo que diga del comprobante la
# fuente de la que salió, cuando esa fuente es la Administración: `estado_sunat` no está en ninguna factura impresa,
# solo en el registro de SUNAT, y que no se pueda dictar es justo lo que se quiere de una API de registro.
CAMPOS_DEL_SISTEMA = ("origen", "confianza", "archivo_nombre", "estado_sunat", "id_externo", "datos_originales")
# Y lo que decide quien revisa: el veredicto de la validación y la marca de apartarlo. Se separa del
# sistema porque son de dos momentos distintos —uno al leer, otro al revisar— y porque un ERP que deposite
# comprobantes para que un contador los apruebe necesita saber cuál es cuál.
CAMPOS_DE_LA_REVISION = ("estado", "excluida", "observaciones")


@dataclass
class Observacion:
    codigo: str
    nivel: str   # 'error' (bloquea la exportación) | 'aviso' (se exporta igual)
    texto: str

    def a_dict(self) -> dict:
        return {"codigo": self.codigo, "nivel": self.nivel, "texto": self.texto}


@dataclass
class Comprobante:
    # Identificación
    tipo_cp: str = "01"             # código SUNAT de 2 dígitos (01 factura, 03 boleta, 07 NC, 08 ND, 14 servicios…)
    serie: str = ""
    numero: str = ""
    numero_final: str = ""          # solo rangos (boletas consolidadas del día)
    fecha_emision: date | None = None
    fecha_vencimiento: date | None = None
    condicion_pago: str = ""        # contado | credito (CONDICIONES_PAGO); vacío = el documento no lo dice
    # CON QUÉ se paga, que es otra pregunta que `condicion_pago`: el código de tres dígitos del catálogo de medios
    # de pago de SUNAT (`catalogos.MEDIOS_PAGO`). Vacío = el documento no lo dice, y quien exporta usa el que tenga
    # configurado el contribuyente. **No se valida contra el catálogo al construir**, a diferencia de
    # `condicion_pago`: un código desconocido es un aviso (`MEDIO_PAGO_DESCONOCIDO`) y no impide registrar nada,
    # porque no cambia ningún asiento y SUNAT puede añadir códigos.
    medio_pago: str = ""
    # Contraparte: el cliente en ventas, el proveedor en compras
    contraparte_tipo_doc: str = "6"  # tipo de documento de identidad: 6 RUC, 1 DNI, 4 CE, 7 pasaporte, 0 otros
    contraparte_doc: str = ""
    contraparte_nombre: str = ""
    # Importes (positivos)
    moneda: str = "PEN"
    tipo_cambio: Decimal | None = None
    base_gravada: Decimal = CERO
    igv: Decimal = CERO
    # base_gravada e igv son SIEMPRE el importe neto de la operación. Los dos descuentos no suman ni restan
    # al total: dicen qué parte de esa base y ese IGV informa el SIRE en sus columnas de descuento (una NC de
    # descuento global va entera ahí, así la registra SUNAT). Semántica completa en estandar/LEEME.md.
    dscto_base: Decimal = CERO      # SIRE ventas, Anexo 3 campo 16 («Dscto BI»)
    dscto_igv: Decimal = CERO       # SIRE ventas, Anexo 3 campo 18 («Dscto IGV / IPM»)
    exonerado: Decimal = CERO
    inafecto: Decimal = CERO
    exportacion: Decimal = CERO
    isc: Decimal = CERO
    base_ivap: Decimal = CERO
    ivap: Decimal = CERO
    icbper: Decimal = CERO
    otros: Decimal = CERO
    # La parte de «otros conceptos» que el registro informa en NEGATIVO: un descuento global que no forma
    # base. Va en positivo, como todo importe, y **resta del total** — ahí se separa de `dscto_base` y
    # `dscto_igv`, que solo dicen qué parte de la base viaja en la columna de descuento y no mueven el total.
    # El RCE lo trae en su campo 24 y el RVIE en el 25, los dos como un NETO con signo: si viene negativo es
    # esto. Caso real: una factura de grifo con 96.00 no gravado y −13.40 aquí, total 82.60.
    dscto_otros: Decimal = CERO
    total: Decimal = CERO
    # Retención de renta de 4ta que MUESTRA el recibo por honorarios (tipo 02).
    # 0 = sin retención; nunca se calcula el 8 % solo (con suspensión no la hay y
    # lo que la documenta es el comprobante). NO confundir con el régimen de
    # retenciones del IGV de las facturas, que no entra en ningún asiento.
    retencion: Decimal = CERO
    # Solo compras
    destino_igv: str = "DG"         # DG gravadas | DGNG mixtas | DNG no gravadas (decide las columnas 14-19 / 15-20)
    valor_no_gravado: Decimal | None = None  # campo 20 / 21; None → exonerado + inafecto
    anio_dua: str = ""
    cod_dep_aduanera: str = ""
    clasif_bienes: str = ""
    # Documento modificado (NC/ND)
    # Por qué se emitió la nota: el Catálogo 09 si es de crédito y el 10 si es de débito
    # (`catalogos.motivos_de_nota`). Lo dice el documento —el `cbc:ResponseCode` del XML— y el SIRE lo trae en su
    # campo 34 de ventas y 39 de compras. Un código desconocido se avisa y se respeta, y vacío = el documento no lo
    # dice, que es lo normal: el propio TXT que este motor genera manda esa columna vacía porque la norma dice que no
    # se considera. OJO: el «01» del Catálogo 09 significa que la nota ANULA EL COMPROBANTE QUE REFERENCIA, no que la
    # nota esté anulada.
    tipo_nota: str = ""
    ref_fecha: date | None = None
    ref_tipo_cp: str = ""
    ref_serie: str = ""
    ref_numero: str = ""
    detraccion: dict | None = None  # {codigo, porcentaje, monto, cuenta, fecha_constancia, nro_constancia}
    id_contrato: str = ""
    # La glosa del documento. La cuenta y el centro no están aquí: no son hechos del documento sino decisiones de cada
    # entorno, y llegan aparte, en la imputación (`asiento.Imputacion`, por `id_externo`). Salieron del comprobante en
    # open-accounting 0.3 (John, 12-sep-2026: las cuentas viven en la aplicación, no en el documento).
    concepto: str = ""
    # Procedencia
    origen: str = "xml"
    confianza: Decimal = Decimal("1.00")
    archivo_nombre: str = ""
    # Lo que SUNAT dice del comprobante en su propio registro: el campo 35 del Anexo N.° 2 (ventas) y el 40 del
    # Anexo 8 de la RS 040-2022 (compras), «Est. Comp». Está aquí y no entre los hechos del documento porque **no lo
    # dice el papel**: una factura impresa no lleva «Est. Comp»; solo lo lleva el registro de la Administración. Y por
    # eso una puerta de entrada no lo acepta de quien dicta un comprobante.
    #
    # **Se transporta tal cual y NO condiciona ninguna regla**, y eso es a propósito: la norma dice de él solo dos
    # cosas —«en la propuesta se muestra datos a título referencial» y «este campo no es considerado para la
    # construcción del archivo de texto»— y **no publica su tabla de valores**. Así que el motor lo enseña y no lo
    # traduce: sin `zfill` y sin `upper()`, porque poner en mayúsculas un código cuyo alfabeto no conocemos ya sería
    # decidir algo sin fuente. Lo que aparta un comprobante del asiento es su importe en cero, que sí se puede
    # comprobar, no este campo.
    #
    # Y no es el `estado` de más abajo, que es el veredicto de la validación de aquí (ok / observada / duplicada).
    estado_sunat: str = ""
    # El id con el que la aplicación que produce el documento conoce este comprobante (su fila). Es la llave con
    # la que le llega aparte su imputación: la cuenta, el centro y el reparto de ESTE documento.
    id_externo: str = ""
    datos_originales: dict = field(default_factory=dict)
    # Revisión (las rellena validar.py / el usuario)
    estado: str = "ok"
    excluida: bool = False
    observaciones: list[Observacion] = field(default_factory=list)

    def __post_init__(self) -> None:
        for f in _CAMPOS_MONTO:
            setattr(self, f, monto(getattr(self, f)))
        self.valor_no_gravado = None if self.valor_no_gravado in (None, "") else monto(self.valor_no_gravado)
        self.tipo_cambio = tipo_cambio(self.tipo_cambio)
        for f in _CAMPOS_FECHA:
            setattr(self, f, fecha(getattr(self, f)))
        for f in _CAMPOS_TEXTO:
            setattr(self, f, " ".join(str(getattr(self, f) or "").split()))
        self.tipo_cp = self.tipo_cp.zfill(2) if self.tipo_cp.isdigit() else self.tipo_cp.upper()
        # Los dos catálogos de motivo son de dos dígitos, así que quien manda "9" quiere decir "09". Solo si es
        # dígito: la columna del RCE lo declara «alfanumérico» y no se le puede imponer un formato que la norma no
        # pide. `estado_sunat` NO pasa por aquí a propósito: se transporta verbatim.
        self.tipo_nota = self.tipo_nota.zfill(2) if self.tipo_nota.isdigit() else self.tipo_nota
        self.serie = self.serie.upper()
        self.moneda = (self.moneda or "PEN").upper()
        self.contraparte_tipo_doc = self.contraparte_tipo_doc or "6"
        self.destino_igv = (self.destino_igv or "DG").upper()
        self.condicion_pago = self.condicion_pago.lower().replace("é", "e")
        if self.condicion_pago and self.condicion_pago not in CONDICIONES_PAGO:
            raise ValueError(f"condicion_pago inválida: {self.condicion_pago!r} (contado | credito)")
        self.confianza = Decimal(str(self.confianza)).quantize(CENTIMO)
        self.observaciones = [
            o if isinstance(o, Observacion) else Observacion(**o) for o in (self.observaciones or [])
        ]
        if self.origen not in ORIGENES:
            raise ValueError(f"origen inválido: {self.origen!r}")

    # --- Derivados -------------------------------------------------------
    @property
    def es_nota_credito(self) -> bool:
        return self.tipo_cp in NOTAS_CREDITO

    @property
    def es_nota(self) -> bool:
        return self.tipo_cp in NOTAS

    @property
    def otros_neto(self) -> Decimal:
        """«Otros conceptos, tributos y cargos» como lo lleva el registro: UNA columna con signo.

        Los importes del estándar van siempre en positivo, así que un descuento global vive aparte en
        `dscto_otros` y aquí se vuelven a juntar. Quien escriba ese campo —el TXT del SIRE, el registro de
        CONTASIS— usa esto, y quien calcule una base a partir del total también: si no, el descuento se
        contaría como un cargo y la base saldría de más.
        """
        return self.otros - self.dscto_otros

    @property
    def adquisiciones_no_gravadas(self) -> Decimal:
        if self.valor_no_gravado is not None:
            return self.valor_no_gravado
        return self.exonerado + self.inafecto

    @property
    def clave(self) -> tuple[str, str, str, str]:
        """Identidad de un comprobante para detectar duplicados: mismo tipo,
        serie, número (sin ceros a la izquierda) y documento de la contraparte."""
        return clave_de(self.tipo_cp, self.serie, self.numero, self.contraparte_doc)

    @property
    def tiene_errores(self) -> bool:
        return any(o.nivel == "error" for o in self.observaciones)

    def observar(self, codigo: str, nivel: str, texto: str) -> None:
        if not any(o.codigo == codigo for o in self.observaciones):
            self.observaciones.append(Observacion(codigo, nivel, texto))

    # --- Serialización (fixtures JSON y almacenamiento externo) -----------
    def a_dict(self) -> dict:
        d: dict[str, Any] = {}
        for f in fields(self):
            v = getattr(self, f.name)
            if isinstance(v, Decimal):
                v = str(v)
            elif isinstance(v, date):
                v = v.isoformat()
            elif f.name == "observaciones":
                v = [o.a_dict() for o in v]
            d[f.name] = v
        return d

    @classmethod
    def de_dict(cls, d: dict) -> "Comprobante":
        """Rechaza (`ValueError`) una clave que no es un campo del comprobante, y con su propio mensaje las dos que
        salieron de aquí en open-accounting 0.3.

        **Lo desconocido NO se ignora** (4.0). Hasta la 3.10 se filtraba en silencio, y eso es lo que `INTEGRAR.md`
        promete que no pasa: «un dato que se cuela sin error es un dato que se pierde sin aviso». Pasaba de verdad —un
        `retencion_4ta` donde el campo es `retencion` exportaba el mes entero sin la línea de retención, y solo se veía
        leyendo las celdas—. Desde la 5.0 el rol se llama `retencion`, igual que el campo, lo que **no** vuelve a abrir el agujero: son objetos distintos —uno es un importe del comprobante y el otro el papel de una línea— y lo que protege ya no es la diferencia de nombre sino que el comprobante rechace lo que no es suyo. Además dejaba al lector **más laxo que el esquema publicado**, que ya rechaza por su
        `additionalProperties: false`; es el mismo error que `LineaDiario.de_dict` corrigió en su día, y de ahí sale la
        forma de este rechazo: nombrar TODAS las sobrantes, no reventar en la primera.

        Las claves `_` tampoco pasan aquí, y no es un olvido: el estándar las admite en la raíz del documento y dentro
        de la detracción, **no en un comprobante** (`estandar/LEEME.md`, «Anotaciones que produce el motor»).

        El orden es el que importa: primero las retiradas en 0.3, que tienen un mensaje que dice adónde se movieron, y
        después las desconocidas. Al revés, un documento viejo recibiría «clave desconocida» en vez de su migración.
        """
        if not isinstance(d, dict):
            raise ValueError("Un comprobante tiene que ser un objeto")
        retirados = [k for k in RETIRADOS_EN_0_3 if k in d]
        if retirados:
            raise ValueError(f"{', '.join(retirados)} ya no va en el comprobante (open-accounting 0.3): la cuenta y "
                             "el centro de cada documento llegan en la imputación, por id_externo")
        desconocidas = sorted(set(d) - {f.name for f in fields(cls)})
        if desconocidas:
            raise ValueError(f"Claves que no son de un comprobante: {', '.join(desconocidas)}. Un hecho que el "
                             "estándar no declara va en `datos_originales`, que se transporta sin interpretar")
        return cls(**d)


def clave_de(tipo_cp: str, serie: str, numero: str, contraparte_doc: str) -> tuple[str, str, str, str]:
    """La misma clave de duplicados, calculable desde una fila de la base sin
    construir un Comprobante entero."""
    return (
        str(tipo_cp or "").strip(),
        str(serie or "").strip().upper(),
        str(numero or "").strip().lstrip("0") or "0",
        solo_digitos(contraparte_doc),
    )


def identidad_de(libro: Libro, c: Comprobante) -> dict[str, str]:
    """La identidad estable de un comprobante (hito 0.0 de la hoja de ruta): el RUC y el tipo del libro, más el tipo,
    la serie y el número sin ceros del comprobante; en compras, también el documento del proveedor.

    No lleva el periodo: un comprobante se anota una sola vez por RUC (el error 452 de SUNAT), así que la misma
    identidad sirve para reconocerlo entre periodos. En ventas no lleva el documento del cliente (decisión de John,
    14-sep-2026): la serie-número del emisor ya es única, y un RUC de cliente mal escrito partiría la identidad en dos,
    que es la misma razón por la que `comparar_sire` lo deja fuera de su clave."""
    tipo_cp, serie, numero, contraparte = c.clave
    identidad = {"ruc": libro.ruc, "libro": libro.tipo, "tipo_cp": tipo_cp, "serie": serie, "numero": numero}
    if not libro.es_venta:
        identidad["contraparte_doc"] = contraparte
    return identidad


_CAMPOS_MONTO = (
    "base_gravada", "igv", "dscto_base", "dscto_igv", "exonerado", "inafecto", "exportacion",
    "isc", "base_ivap", "ivap", "icbper", "otros", "dscto_otros", "total", "retencion",
)
_CAMPOS_FECHA = ("fecha_emision", "fecha_vencimiento", "ref_fecha")
# Los campos que salieron del comprobante en open-accounting 0.3: llegan en la imputación.
RETIRADOS_EN_0_3 = ("cuenta_contable", "centro_costo")

_CAMPOS_TEXTO = (
    "tipo_cp", "serie", "numero", "numero_final", "contraparte_tipo_doc", "contraparte_doc",
    "contraparte_nombre", "moneda", "destino_igv", "anio_dua", "cod_dep_aduanera",
    "clasif_bienes", "tipo_nota", "ref_tipo_cp", "ref_serie", "ref_numero", "id_contrato",
    "concepto", "archivo_nombre", "condicion_pago", "medio_pago", "id_externo", "estado_sunat",
)
