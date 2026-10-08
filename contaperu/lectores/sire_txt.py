"""Leer la PROPUESTA del SIRE: el TXT que SUNAT entrega al exportar un periodo.

Por qué existe: el archivo que un estudio contable siempre tiene a mano no son los
XML de su cliente —esos los tiene el cliente— sino lo que SUNAT ya registró. Se baja
del SIRE (Exportar → ticket → ZIP con un TXT) y con eso se puede trabajar el mes
entero, sin un solo XML, hasta el Excel para el sistema contable.

Entran los dos formatos, porque comparten el orden de los campos informados:

- **La exportación**: fila de cabecera, 40 columnas en ventas, el CAR lleno y las
  que completa la Administración al final. De esas se leen dos, el motivo de la nota
  y el estado del comprobante, y se ignoran las demás (FOB, gratuitas, tipo de
  operación, DAM, CLU): son referenciales y nunca vuelven a SUNAT, así que del estado
  y del motivo lo que se hace es transportarlos, no decidir con ellos.
- **El de "reemplazar propuesta"**: 33 campos en ventas (37 en compras) y palote
  final, sin cabecera. Es el que genera este mismo portal, así que un archivo puede
  salir y volver a entrar.

Lo que la propuesta NO trae, y por eso no se inventa aquí: el concepto del
comprobante, la cuenta contable, el centro de costo y el detalle de la detracción. Son
datos del comprobante, no del registro; `validar.py` lo avisa con `SIRE_SIN_DETALLE`.

De la detracción conviene precisar qué calla SUNAT y qué no, porque no es lo mismo: el RCE **sí marca si una
fila está sujeta al SPOT** —el campo 38 del Anexo 8, con una `D`; en un RCE real de un mes, 221 filas de 3018—,
pero **no dice cuál**: ni código del Catálogo 54, ni tasa, ni monto, ni cuenta, ni constancia. Desde la 4.1 esa
marca **se lee** y entra como anotación (`detraccion._marca_sire`), sin código, y el motor se niega a exportar
esos comprobantes hasta que quien integra mande el `detraccion_codigo` en su imputación (enmienda 0020). Antes
salían sin su línea de detracción y en silencio. Para quien integra, el circuito está en `INTEGRAR.md` §«El SIRE,
de punta a punta», punto 9.
El **concepto se queda VACÍO a propósito** (regla de contabilidad): copiarle el nombre de
la contraparte repetía en la columna un dato que ya está en la suya, y no ganaba nada
—`asiento.glosa_de` ya cae al nombre de la contraparte cuando el concepto está vacío, así
que el Excel sale idéntico— mientras que la celda llena aparentaba un dato que el
archivo no da y estorbaba para escribir el de verdad.
"""
from __future__ import annotations

import io
import zipfile
from decimal import Decimal

from . import _zip
from ..tributos import detracciones as _detracciones
from ..errores import ErrorContaperu
from ..modelo import Comprobante, Libro

ORIGEN = "sire"


class SireInvalido(ErrorContaperu, ValueError):
    """El archivo no es una propuesta del SIRE, o no es la de este proceso."""


# Orden de los campos informados. El mismo en la exportación y en el reemplazo: se
# comprobó columna a columna contra la exportación real de agosto (26-ago-2026).
# Ventas = Anexo 3 (RS 112-2021); compras = Anexo 11 (RS 040-2022).
#
# Los índices son 0-based, o sea el número de campo del anexo menos uno. **Los dos últimos de cada mapa son los que
# completa la Administración**, y se leen desde la 3.5.0: el motivo de la nota y lo que SUNAT dice del comprobante.
# Sus números NO son los mismos en los dos registros, y de ahí que cada mapa los tenga por separado — ventas los pone
# en los campos 34 y 35 (Anexo N.° 2 de la RS 112-2021) y compras en el 39 y el 40 (Anexo 8 de la RS 040-2022, §8.4,
# donde el 38 es la marca de detracción y el 41 las inconsistencias). Los anexos ni siquiera les dan el mismo formato:
# el estado es «longitud 2, alfanumérico» en ventas y «longitud 1, numérico» en compras, así que ninguno de los dos
# campos se normaliza al leerlo.
#
# El formato de «reemplazar propuesta» no las trae —33 campos y palote en ventas, 37 en compras—: ahí quedan vacías
# y el comprobante entra igual, que es lo que hace segura la ida y vuelta.
POS_VENTA = {
    "fecha_emision": 4, "fecha_vencimiento": 5, "tipo_cp": 6, "serie": 7, "numero": 8, "numero_final": 9,
    "contraparte_tipo_doc": 10, "contraparte_doc": 11, "contraparte_nombre": 12,
    "exportacion": 13, "base_gravada": 14, "dscto_base": 15, "igv": 16, "dscto_igv": 17,
    "exonerado": 18, "inafecto": 19, "isc": 20, "base_ivap": 21, "ivap": 22, "icbper": 23,
    "otros": 24, "total": 25, "moneda": 26, "tipo_cambio": 27,
    "ref_fecha": 28, "ref_tipo_cp": 29, "ref_serie": 30, "ref_numero": 31, "id_contrato": 32,
    "tipo_nota": 33, "estado_sunat": 34,
}
POS_COMPRA = {
    "fecha_emision": 4, "fecha_vencimiento": 5, "tipo_cp": 6, "serie": 7, "anio_dua": 8,
    "numero": 9, "numero_final": 10, "contraparte_tipo_doc": 11, "contraparte_doc": 12,
    "contraparte_nombre": 13,
    # 14-19: las tres parejas base/IGV según el destino de la adquisición
    "isc": 21, "icbper": 22, "otros": 23, "total": 24, "moneda": 25, "tipo_cambio": 26,
    "ref_fecha": 27, "ref_tipo_cp": 28, "ref_serie": 29, "cod_dep_aduanera": 30, "ref_numero": 31,
    "clasif_bienes": 32, "id_contrato": 33,
    # 34-36: % de participación, IMB y el CAR del CP a modificar; 37: la marca de detracción, que no se lee.
    # Estos índices y los de arriba, con el nombre de SUNAT de cada columna y el motivo de cada hueco, están
    # publicados en `datos/sunat/sire_campos.json`, y `tests/test_sire_campos.py` no los deja separarse.
    "tipo_nota": 38, "estado_sunat": 39,
}
IGV_COMPRAS = {"DG": (14, 15), "DGNG": (16, 17), "DNG": (18, 19)}
VALOR_NO_GRAVADO = 20
# La columna «Detracción» del RCE: campo 38 del Anexo 8 de la RS 040-2022 (§8.4). SUNAT escribe una `D` en las filas
# sujetas al SPOT y la deja vacía en las demás — en un RCE real de un mes, 221 de 3018 (set-2026). **Es lo único que
# la propuesta dice del SPOT**: afirma QUE hay detracción y no dice CUÁL, porque el código del Catálogo 54, la tasa y
# el monto son del comprobante y no del registro. El RVIE no tiene esta columna: solo compras.
MARCA_DETRACCION = 37
# Lo que SUNAT escribe en esa columna cuando la operación está sujeta. Se guarda el valor literal, no un booleano: es
# el dato del archivo, y si algún día el anexo admite otra letra, aquí se verá en vez de perderse en un `True`.
MARCA_DETRACCION_SI = "D"
MONTOS = {"exportacion", "base_gravada", "dscto_base", "igv", "dscto_igv", "exonerado", "inafecto",
          "isc", "base_ivap", "ivap", "icbper", "otros", "dscto_otros", "total"}
FECHAS = {"fecha_emision", "fecha_vencimiento", "ref_fecha"}
MINIMO_CAMPOS = 30


def _texto(datos: bytes) -> str:
    return datos.decode("utf-8-sig", errors="replace")


def leer_lineas(datos: bytes) -> list[list[str]]:
    """Filas del TXT (o del TXT que va dentro del ZIP), sin la cabecera si la trae."""
    if zipfile.is_zipfile(io.BytesIO(datos)):
        with zipfile.ZipFile(io.BytesIO(datos)) as z:
            nombres = [n for n in z.namelist() if n.lower().endswith(".txt")]
            if not nombres:
                raise SireInvalido("El ZIP no trae ningún TXT dentro")
            try:
                datos = _zip.leer(z, z.getinfo(nombres[0]))
            except _zip.Desmedido as e:
                raise SireInvalido(str(e)) from None
    filas = [l.split("|") for l in _texto(datos).splitlines() if l.strip()]
    if filas and filas[0][0].strip().lower() == "ruc":
        filas = filas[1:]          # la exportación trae cabecera; el reemplazo no
    return filas


def es_sire(datos: bytes) -> bool:
    """¿Esto es una propuesta del SIRE? Se mira el contenido, no el nombre.

    Acepta el TXT suelto y el ZIP tal cual lo entrega SUNAT (dentro de la aplicación que lo use los
    ZIP ya vienen abiertos, pero desde la CLI o los tests entra el ZIP entero).
    """
    try:
        if zipfile.is_zipfile(io.BytesIO(datos)):
            with zipfile.ZipFile(io.BytesIO(datos)) as z:
                dentro = [n for n in z.namelist() if n.lower().endswith(".txt")]
                if not dentro:
                    return False
                datos = _zip.leer(z, z.getinfo(dentro[0]))
        texto = _texto(datos[:4096])
    except Exception:  # noqa: BLE001
        return False
    for linea in texto.splitlines():
        if not linea.strip():
            continue
        campos = linea.split("|")
        if campos[0].strip().lower() == "ruc" and len(campos) >= MINIMO_CAMPOS:
            return True            # la cabecera de la exportación
        # Una fila: RUC de 11 dígitos, periodo AAAAMM y bastantes columnas.
        return (len(campos) >= MINIMO_CAMPOS and campos[0].strip().isdigit()
                and len(campos[0].strip()) == 11 and campos[2].strip().isdigit() and len(campos[2].strip()) == 6)
    return False


def _valor(campos: list[str], i: int) -> str:
    return campos[i].strip() if i < len(campos) else ""


def _con_signo(v: str) -> Decimal:
    return Decimal((v or "0").replace(",", ""))


def _una(campos: list[str], libro: Libro, archivo_nombre: str) -> Comprobante:
    pos = POS_VENTA if libro.es_venta else POS_COMPRA
    datos = {k: _valor(campos, i) for k, i in pos.items()}
    # «Otros conceptos, tributos y cargos» (RCE campo 24, RVIE campo 25) es un NETO CON SIGNO, y un negativo
    # ahí es un descuento global: caso real, una factura de grifo con 96.00 no gravado y −13.40, total 82.60.
    # `monto()` devuelve el valor absoluto —el signo no es parte del dato— así que sin esto el total salía
    # 109.40 y el comprobante avisaba «no cuadra» por algo que estaba bien.
    #
    # Se mira el signo CONTRARIO AL DEL TOTAL, no el signo a secas: en una nota de crédito TODOS los campos
    # vienen negativos porque lo es la operación entera, y ese signo ya lo pone el driver al escribir
    # (`negativo(c)`). Tomarlo por descuento invertiría la nota. Comprobado en un RCE real de 1116 filas: las
    # dos notas de crédito traen este campo en 0.00 y las seis facturas con descuento lo traen contrario.
    bruto_otros = _con_signo(datos.get("otros") or "0")
    if bruto_otros < 0 and _con_signo(datos.get("total") or "0") >= 0:
        datos["otros"], datos["dscto_otros"] = "0", str(-bruto_otros)
    for k in MONTOS:
        if k in datos:
            datos[k] = datos[k] or "0"
    for k in FECHAS:
        datos[k] = datos.get(k) or None
    # SUNAT exporta `1.000` cuando la moneda es PEN, pero el registro solo pide el
    # T.C. si la moneda NO es soles — y así lo escribe el driver (`tc_pen=""`).
    # Guardar ese 1.000 sería un dato que el comprobante no tiene y que se
    # contradice con el archivo que este mismo motor genera (regla de contabilidad).
    if datos.get("moneda", "").strip().upper() in ("", "PEN"):
        datos["tipo_cambio"] = ""
    if not libro.es_venta:
        # Las seis columnas de base/IGV dicen el destino de la adquisición: se toma
        # la pareja que trae importe, y si no hay ninguna se queda en DG.
        for destino, (i_base, i_igv) in IGV_COMPRAS.items():
            base, igv = _valor(campos, i_base), _valor(campos, i_igv)
            if (base and base.strip("0.-")) or (igv and igv.strip("0.-")):
                datos.update(destino_igv=destino, base_gravada=base or "0", igv=igv or "0")
                break
        else:
            datos.update(destino_igv="DG", base_gravada="0", igv="0")
        # El campo 21 solo se DECLARA cuando trae importe, y el `strip("0.-")` no es adorno: la columna
        # llega como "0" o "0.00" en las compras gravadas, y la cadena "0" es verdadera. Declararlo en cero
        # significa «lo no gravado de este comprobante es cero», y eso **gana** sobre `exonerado + inafecto`
        # en `adquisiciones_no_gravadas`. Mientras el lector fuera el unico que escribia el campo daba igual
        # —en el RCE esos dos siempre son 0—, pero desde que `validar` usa la propiedad (3.5.1) un cero
        # declarado se llevaria por delante el desglose que alguien escriba luego en la pantalla. Es el mismo
        # idioma con el que arriba se decide si una pareja base/IGV trae algo.
        no_gravado = _valor(campos, VALOR_NO_GRAVADO)
        if no_gravado and no_gravado.strip("0.-"):
            datos["valor_no_gravado"] = no_gravado
        # La marca de detracción, lo único que la propuesta dice del SPOT. Entra como ANOTACIÓN en un bloque de
        # detracción que, a propósito, **no lleva código**: la propuesta no lo trae y no se inventa (si se inventara,
        # CONCAR recibiría un código interno falso y el asiento una tasa falsa). Lo que hace esta marca es que el
        # motor sepa a QUIÉN le falta: `validar` se niega a exportar esos comprobantes hasta que el contador ponga el
        # código, en vez de exportarlos sin su línea de detracción y en silencio, que es lo que pasaba hasta la 4.0.
        if _valor(campos, MARCA_DETRACCION).strip().upper() == MARCA_DETRACCION_SI:
            datos["detraccion"] = {_detracciones.MARCA_SIRE: MARCA_DETRACCION_SI}
    if libro.es_venta:
        # Base e IGV netos, descuentos aparte (estandar/LEEME.md). SUNAT escribe cada campo con su signo y el
        # total es la suma de todos: en las diez filas de la exportación real de agosto, el campo 26 es
        # exactamente la suma con signo de los campos 14 a 25 (11-sep-2026). Por eso la base neta es 15 + 16 y
        # el IGV neto 17 + 18 —una NC de descuento (15 = 0, 16 = −9985.36) tiene base 9985.36—, y hay que
        # leerlos CON signo: `Comprobante` los guarda en positivo y se perdería de qué lado estaba cada uno.
        b15, d16, i17, d18 = (_con_signo(datos[k]) for k in ("base_gravada", "dscto_base", "igv", "dscto_igv"))
        if d16 > 0 or d18 > 0:
            raise ValueError("los descuentos (campos 16 y 18) vienen en positivo y SUNAT los escribe en negativo")
        datos.update(base_gravada=str(abs(b15 + d16)), dscto_base=str(abs(d16)),
                     igv=str(abs(i17 + d18)), dscto_igv=str(abs(d18)))
    return Comprobante(
        **datos,
        # `concepto` se queda vacío: la propuesta no lo trae y el Excel de CONCAR ya
        # cae al nombre de la contraparte por su cuenta (`asiento.glosa_de`).
        origen=ORIGEN,
        confianza=Decimal("1.00"),      # es el dato de SUNAT, no la lectura de una IA
        archivo_nombre=archivo_nombre,
        datos_originales={"sire": campos},     # la fila cruda, para rastrear de dónde salió cada valor
    )


def parsear(datos: bytes, libro: Libro, archivo_nombre: str = "") -> list[Comprobante]:
    """TXT (o ZIP) de la propuesta → comprobantes del libro que se está trabajando.

    Falla con un motivo concreto —RUC, periodo o tipo de registro— en vez de cargar
    comprobantes que no son de este proceso.
    """
    filas = leer_lineas(datos)
    if not filas:
        raise SireInvalido("El archivo del SIRE no tiene ninguna fila")

    rucs = {f[0].strip() for f in filas if f and f[0].strip()}
    if rucs and libro.ruc not in rucs:
        raise SireInvalido(f"El archivo es del RUC {sorted(rucs)[0]} y este cliente es {libro.ruc}")
    periodos = {f[2].strip() for f in filas if len(f) > 2 and f[2].strip()}
    if periodos and libro.periodo not in periodos:
        raise SireInvalido(f"El archivo es del periodo {sorted(periodos)[0]} y este proceso es de {libro.periodo}")

    comprobantes = []
    for i, campos in enumerate(filas, 1):
        if len(campos) < MINIMO_CAMPOS:
            raise SireInvalido(f"La fila {i} tiene {len(campos)} campos: no parece un archivo del SIRE")
        try:
            c = _una(campos, libro, archivo_nombre)
        except ValueError as e:
            raise SireInvalido(f"La fila {i} no se pudo leer ({e}). "
                               f"¿Es el registro de {'ventas' if libro.es_venta else 'compras'}?") from e
        if not c.fecha_emision or not c.tipo_cp.strip():
            raise SireInvalido(f"La fila {i} no trae fecha de emisión o tipo de comprobante: "
                               f"¿es el registro de {'ventas' if libro.es_venta else 'compras'}?")
        comprobantes.append(c)
    return comprobantes
