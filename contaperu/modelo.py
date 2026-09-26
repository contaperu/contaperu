"""Modelo canónico del motor: un `Comprobante` = una fila del registro de compras o ventas.

Aquí está TODO lo que necesitan las salidas —el SIRE (Anexos 3 y 11) y los sistemas contables—; los drivers
solo ordenan y formatean. Reglas:

- Importes en `Decimal` con 2 decimales y SIEMPRE positivos: el signo de las
  notas de crédito lo pone el driver, no el dato (así la celda editable del
  portal no obliga a escribir negativos).
- Fechas como `date`; los drivers las escriben en el formato que toque.
- Los campos de revisión (`estado`, `observaciones`, `excluida`) los rellenan
  `validar.py` y el usuario; el motor nunca los inventa.
"""
from __future__ import annotations

from . import vocabulario

import re
from dataclasses import dataclass, field, fields
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

CERO = Decimal("0.00")
CENTIMO = Decimal("0.01")     # el cuántum de todo importe: una sola fuente para el motor
_TRES = Decimal("0.001")

# Del catálogo del estándar (`vocabulario.TIPOS_LIBRO`), que es la única fuente desde la 1.0: estaba aquí y otra
# vez como enum del esquema, sin nada que comparara las dos copias.
TIPOS_LIBRO = vocabulario.TIPOS_LIBRO
ORIGENES = ("xml", "pdf_texto", "vision", "manual", "sire")  # sire = importado de la propuesta de SUNAT
# Lo que declara el documento sobre su pago. En la factura electrónica es obligatorio desde 2021 (UBL
# `PaymentTerms FormaPago`: «Contado», o «Credito» con sus cuotas). Vacío = el documento no lo dice.
CONDICIONES_PAGO = ("contado", "credito")


def a_decimal(v: Any) -> Decimal:
    """Un número cualquiera (una tasa, un porcentaje) a `Decimal`, sin redondear y sin quitarle el signo; vacío o
    ilegible, 0. Para importes está `monto`, que además los deja en 2 decimales y en positivo."""
    try:
        return Decimal(str(v if v not in (None, "") else 0))
    except Exception:
        return Decimal(0)


def texto_tasa(tasa: Decimal) -> str:
    """Una tasa como se escribe: a 2 decimales y sin ceros de más (18 → «18», 10.5 → «10.5», 4.50 → «4.5»)."""
    return format(tasa.quantize(CENTIMO, rounding=ROUND_HALF_UP).normalize(), "f")


def serie_y_numero(serie: str, numero: str) -> str:
    """«F001-123», o solo la parte que haya: un documento sin serie (un DUA, un recibo de servicios) se nombra por su
    número, y sin número por su serie."""
    return f"{serie}-{numero}" if serie and numero else (serie or numero)


def monto(v: Any) -> Decimal:
    """Normaliza a Decimal de 2 decimales. Acepta str ('1,234.50'), int, float,
    Decimal o vacío/None (→ 0.00). Devuelve el valor absoluto: el signo no es
    parte del dato (ver docstring del módulo)."""
    if v is None or v == "":
        return CERO
    if isinstance(v, Decimal):
        d = v
    else:
        s = str(v).strip().replace(",", "")
        if s == "":
            return CERO
        try:
            d = Decimal(s)
        except InvalidOperation as e:
            raise ValueError(f"Importe inválido: {v!r}") from e
    return abs(d).quantize(CENTIMO, rounding=ROUND_HALF_UP)


def tipo_cambio(v: Any) -> Decimal | None:
    """Tipo de cambio con 3 decimales (formato `#.###` de SUNAT); vacío → None."""
    if v is None or v == "":
        return None
    try:
        d = Decimal(str(v).strip().replace(",", ""))
    except InvalidOperation as e:
        raise ValueError(f"Tipo de cambio inválido: {v!r}") from e
    if d <= 0:
        return None
    return d.quantize(_TRES, rounding=ROUND_HALF_UP)


_FORMATOS_FECHA = ("%Y-%m-%d", "%Y%m%d", "%d/%m/%Y", "%d-%m-%Y")


def fecha(v: Any) -> date | None:
    """Acepta date/datetime, 'AAAA-MM-DD', 'AAAAMMDD', 'DD/MM/AAAA', 'DD-MM-AAAA';
    vacío → None. Cualquier otra cosa es un error (mejor fallar que inventar)."""
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v).strip()[:10]
    for f in _FORMATOS_FECHA:
        try:
            return datetime.strptime(s, f).date()
        except ValueError:
            continue
    raise ValueError(f"Fecha inválida: {v!r}")


def solo_digitos(v: Any) -> str:
    return re.sub(r"\D", "", str(v or ""))


def numero_sin_ceros(numero: str) -> str:
    """El número de un comprobante sin ceros a la izquierda (`00028806` → `28806`, `0000` → `0`): SUNAT identifica el
    comprobante por su número y los ceros son cosmética del emisor. Un número con letras queda tal cual."""
    n = (numero or "").strip()
    return (n.lstrip("0") or "0") if n.isdigit() else n


@dataclass
class Libro:
    """El registro que se genera: un RUC, un mes, ventas o compras."""

    ruc: str
    razon_social: str
    periodo: str  # 'AAAAMM'
    tipo: str     # 'venta' | 'compra'

    def __post_init__(self) -> None:
        self.ruc = solo_digitos(self.ruc)
        self.periodo = solo_digitos(self.periodo)[:6]
        self.razon_social = " ".join(str(self.razon_social or "").split())
        self.tipo = str(self.tipo or "").strip().lower()
        if len(self.ruc) != 11:
            raise ValueError(f"RUC inválido: {self.ruc!r} (11 dígitos)")
        if not re.fullmatch(r"20[0-9]{2}(0[1-9]|1[0-2])", self.periodo):
            raise ValueError(f"Periodo inválido: {self.periodo!r} (AAAAMM)")
        if self.tipo not in TIPOS_LIBRO:
            raise ValueError(f"Tipo de libro inválido: {self.tipo!r} (venta|compra)")

    @property
    def anio(self) -> int:
        return int(self.periodo[:4])

    @property
    def mes(self) -> int:
        return int(self.periodo[4:6])

    @property
    def es_venta(self) -> bool:
        return self.tipo == "venta"

    def a_dict(self) -> dict[str, str]:
        return {"ruc": self.ruc, "razon_social": self.razon_social, "periodo": self.periodo, "tipo": self.tipo}

    @classmethod
    def de_dict(cls, d: dict) -> "Libro":
        """Lo desconocido se ignora; lo que falta llega vacío y lo rechaza la validación del libro (`ValueError`)."""
        if not isinstance(d, dict):
            raise ValueError("El libro tiene que ser un objeto con ruc, razon_social, periodo y tipo")
        return cls(**{f.name: d.get(f.name, "") for f in fields(cls)})


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
        return self.tipo_cp in ("07", "87")

    @property
    def es_nota(self) -> bool:
        return self.tipo_cp in ("07", "08", "87", "88")

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
        """Lo desconocido se ignora; lo que salió del comprobante en open-accounting 0.3, no: un documento que todavía
        trae la cuenta o el centro se rechaza, porque ignorarlos lo dejaría sin cuenta y sin aviso."""
        retirados = [k for k in RETIRADOS_EN_0_3 if str(d.get(k) or "").strip()]
        if retirados:
            raise ValueError(f"{', '.join(retirados)} ya no va en el comprobante (open-accounting 0.3): la cuenta y "
                             "el centro de cada documento llegan en la imputación, por id_externo")
        conocidos = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in conocidos})


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
    "isc", "base_ivap", "ivap", "icbper", "otros", "total", "retencion",
)
_CAMPOS_FECHA = ("fecha_emision", "fecha_vencimiento", "ref_fecha")
# Los campos que salieron del comprobante en open-accounting 0.3: llegan en la imputación.
RETIRADOS_EN_0_3 = ("cuenta_contable", "centro_costo")

_CAMPOS_TEXTO = (
    "tipo_cp", "serie", "numero", "numero_final", "contraparte_tipo_doc", "contraparte_doc",
    "contraparte_nombre", "moneda", "destino_igv", "anio_dua", "cod_dep_aduanera",
    "clasif_bienes", "ref_tipo_cp", "ref_serie", "ref_numero", "id_contrato",
    "concepto", "archivo_nombre", "condicion_pago", "id_externo",
)
