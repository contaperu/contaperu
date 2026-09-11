"""Modelo canónico del motor: un `Comprobante` = una fila del registro de compras o ventas.

Aquí está TODO lo que necesitan las cuatro salidas (PLE 14.1 / 8.1 y SIRE
Anexo 3 / 11); las plantillas solo ordenan y formatean. Reglas:

- Importes en `Decimal` con 2 decimales y SIEMPRE positivos: el signo de las
  notas de crédito lo pone la plantilla, no el dato (así la celda editable del
  portal no obliga a escribir negativos).
- Fechas como `date`; las plantillas las escriben en el formato que toque.
- Los campos de revisión (`estado`, `observaciones`, `excluida`) los rellenan
  `validar.py` y el usuario; el motor nunca los inventa.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, fields
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

CERO = Decimal("0.00")
_DOS = Decimal("0.01")
_TRES = Decimal("0.001")

TIPOS_LIBRO = ("venta", "compra")
ORIGENES = ("xml", "pdf_texto", "vision", "manual", "sire")  # sire = importado de la propuesta de SUNAT


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
    return abs(d).quantize(_DOS, rounding=ROUND_HALF_UP)


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
    # Contraparte: el cliente en ventas, el proveedor en compras
    contraparte_tipo_doc: str = "6"  # Tabla 1: 6 RUC, 1 DNI, 4 CE, 7 pasaporte, 0 otros
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
    # Contable (CONCAR)
    concepto: str = ""
    cuenta_contable: str = ""
    centro_costo: str = ""
    # Procedencia
    origen: str = "xml"
    confianza: Decimal = Decimal("1.00")
    archivo_nombre: str = ""
    datos_raw: dict = field(default_factory=dict)
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
        self.confianza = Decimal(str(self.confianza)).quantize(_DOS)
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


_CAMPOS_MONTO = (
    "base_gravada", "igv", "dscto_base", "dscto_igv", "exonerado", "inafecto", "exportacion",
    "isc", "base_ivap", "ivap", "icbper", "otros", "total", "retencion",
)
_CAMPOS_FECHA = ("fecha_emision", "fecha_vencimiento", "ref_fecha")
_CAMPOS_TEXTO = (
    "tipo_cp", "serie", "numero", "numero_final", "contraparte_tipo_doc", "contraparte_doc",
    "contraparte_nombre", "moneda", "destino_igv", "anio_dua", "cod_dep_aduanera",
    "clasif_bienes", "ref_tipo_cp", "ref_serie", "ref_numero", "id_contrato",
    "concepto", "cuenta_contable", "centro_costo", "archivo_nombre",
)
