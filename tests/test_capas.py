"""Las capas del motor, comprobadas por dependencia y no por buena voluntad (1.0).

`test_frontera.py` vigila que el núcleo no salga a la red, no mire el reloj y no importe una puerta. Esto va más lejos:
cada módulo del paquete pertenece a una capa, y una capa solo importa de las que están debajo.

    base     _version, _obsoleto, _datos, errores: hojas sin dependencias del paquete
    nucleo   modelo, catálogos, configuración, IGV, detracciones, validación, partida doble, asiento, PCGE, lectores
    drivers  el contrato, el kit común y cada driver
    pipeline la preparación y la orquestación de un mes
    api      la fachada estable
    puertas  CLI, MCP y HTTP: solo hablan con la api

Además, aquí se hacen visibles dos cosas que la hoja de ruta pedía antes de mover código:

- **El núcleo y los drivers no abren archivos** (hito 0.5): lo que viaja con el paquete lo lee `_datos`.
- **El acoplamiento con lo peruano** (hito J0): qué módulos importan hoy uno peruano queda congelado en
  `fixtures/capas/acoplamiento_pe.json`, y un acoplamiento nuevo no entra sin verse. No mueve código.

    python -c "import sys; sys.path.insert(0, 'tests'); import test_capas as t; t.regenerar()"
"""
from __future__ import annotations

import ast
import json
import pathlib
import subprocess
import sys

import pytest

PAQUETE = pathlib.Path(__file__).resolve().parents[1] / "contaperu"
RAIZ = PAQUETE.parent
ACOPLAMIENTO = pathlib.Path(__file__).parent / "fixtures" / "capas" / "acoplamiento_pe.json"


def _nombre(archivo: pathlib.Path) -> str:
    partes = list(archivo.relative_to(RAIZ).with_suffix("").parts)
    if partes[-1] == "__init__":
        partes = partes[:-1]
    return ".".join(partes)


MODULOS: dict[str, pathlib.Path] = {_nombre(f): f for f in sorted(PAQUETE.rglob("*.py"))}

# Prefijo de módulo → capa. Gana el prefijo más largo.
CAPAS = {
    "contaperu": "paquete",
    "contaperu._version": "base", "contaperu._obsoleto": "base", "contaperu._datos": "base",
    "contaperu.errores": "base",
    "contaperu.modelo": "nucleo", "contaperu.catalogos": "nucleo", "contaperu.configuracion": "nucleo",
    # El vocabulario del estándar (roles, clases, tipos de libro), que lee su catálogo publicado por `_datos`.
    # Núcleo como su hermano `catalogos`, y no «peruano»: los cinco valores de `clase` son universales.
    "contaperu.vocabulario": "nucleo",
    "contaperu.asiento": "nucleo", "contaperu.pcge": "nucleo",
    # El comprobante de compra o de venta (12.11): qué dice el papel y qué cuatro datos lo distinguen de otro.
    # Es el espejo de `tesoreria` sobre el otro libro, y **núcleo y hoja** como él: lo que SALE de un comprobante
    # —el asiento— no está aquí, igual que el asiento de un movimiento no está en `tesoreria`. Y **no es
    # peruano**, aunque `Comprobante` lo sea por contenido: lo que lo hace peruano son los impuestos en campos
    # fijos, que están declarados abajo en `PERUANOS_POR_CONTENIDO` y se separan con J2-J4.
    "contaperu.comprobantes": "nucleo",
    # La contabilidad que no depende del país ni del régimen (6.4.0): la partida doble y cuánto suma un libro.
    # Núcleo, y NO peruano: «Debe igual a Haber» no la discute ninguna jurisdicción. Y **núcleo y no pipeline**
    # para el resumen, que es la decisión que sostiene todo lo demás: esta capa NO PUEDE importar un driver, así
    # que la garantía de que un resumen no mire el destino es la capa y no una promesa escrita en un docstring.
    "contaperu.contable": "nucleo",
    "contaperu.lectores": "nucleo",
    # La API del SIRE como funciones puras (8.1): armar la petición, el estado de un ticket, el rechazo de SUNAT.
    # **Núcleo y no una puerta**, y es la decisión que lo hace legítimo: aquí se SABE la URL y no se llama nunca. El
    # catálogo que lo sostiene viaja en `datos/sunat/`, y `test_frontera` sigue prohibiendo `httpx` y `socket`.
    "contaperu.sunat": "nucleo",
    # La tesorería (8.2): qué es una cuenta bancaria, un movimiento de extracto y una constancia de pago, y el
    # cuadre de la cadena de saldos. **Núcleo y hoja**, como `sunat`: no lo importa nadie de dentro y su público es
    # quien integra. Lo que lee bytes de un extracto vivirá fuera, igual que los conectores (D7).
    "contaperu.tesoreria": "nucleo",
    # El puente entre los tres libros (12.3): cuánto de un pago cancela un documento. **Núcleo y no pipeline** por
    # lo mismo que `contable`: lo que decide si una factura está pagada no puede mirar un destino, y la capa es lo
    # que lo garantiza. Importa de `tesoreria` las claves con que se nombra un comprobante, para no escribirlas dos
    # veces. Y **no es peruano**: «cuánto de esto cancela aquello» no lo discute ninguna jurisdicción.
    "contaperu.aplicaciones": "nucleo",
    # Los tributos del Perú agrupados (6.4.0): el IGV, las detracciones, la validación y el contraste con
    # lo que SUNAT tiene. Núcleo, y peruano: es casi toda la tupla `PERUANOS` de más abajo.
    "contaperu.tributos": "nucleo",
    "contaperu.drivers": "drivers",
    "contaperu.pipeline": "pipeline",
    "contaperu.api": "api",
    "contaperu.puertas": "puertas",
}
PUEDE = {
    "base": {"base"},
    "nucleo": {"base", "nucleo"},
    "drivers": {"base", "nucleo", "drivers"},
    "pipeline": {"base", "nucleo", "drivers", "pipeline"},
    "api": {"base", "nucleo", "drivers", "pipeline", "api"},
    "puertas": {"base", "api", "puertas"},
}

# Lo que todavía importa una capa que no le toca, con su motivo. Vacía desde que las puertas hablan solo con la api
# (etapa 3 de la 1.0): una excepción nueva entra aquí con su motivo, a la vista.
TOLERADAS: dict[tuple[str, str], str] = {}


def capa(modulo: str) -> str:
    partes = modulo.split(".")
    for largo in range(len(partes), 0, -1):
        prefijo = ".".join(partes[:largo])
        if prefijo in CAPAS:
            return CAPAS[prefijo]
    raise KeyError(f"{modulo} no tiene capa: añádelo a CAPAS")


def _recorrer(nodo: ast.AST, en_funcion: bool = False):
    for hijo in ast.iter_child_nodes(nodo):
        yield hijo, en_funcion
        yield from _recorrer(hijo, en_funcion or isinstance(hijo, (ast.FunctionDef, ast.AsyncFunctionDef)))


def importaciones(modulo: str) -> set[str]:
    """Los módulos del paquete que `modulo` importa, resolviendo los imports relativos y los submódulos que se importan
    por su nombre (`from . import concar`)."""
    archivo = MODULOS[modulo]
    paquete = modulo if archivo.name == "__init__.py" else modulo.rpartition(".")[0]
    salida: set[str] = set()
    for nodo, _ in _recorrer(ast.parse(archivo.read_text(encoding="utf-8"))):
        destinos: list[str] = []
        if isinstance(nodo, ast.Import):
            destinos = [alias.name for alias in nodo.names]
        elif isinstance(nodo, ast.ImportFrom):
            if nodo.level:
                partes = paquete.split(".")
                base = partes[:len(partes) - (nodo.level - 1)]
                origen = ".".join(base + ([nodo.module] if nodo.module else []))
            else:
                origen = nodo.module or ""
            destinos = [origen] + [f"{origen}.{alias.name}" for alias in nodo.names]
        for destino in destinos:
            if destino.split(".")[0] != "contaperu":
                continue
            while destino and destino not in MODULOS:
                destino = destino.rpartition(".")[0]
            # La raíz del paquete es perezosa y solo trae `_version`: pedirle un nombre no es depender de otra capa.
            if destino and destino not in (modulo, "contaperu"):
                salida.add(destino)
    return salida


def test_cada_modulo_tiene_capa():
    assert [m for m in MODULOS if not _tiene_capa(m)] == []


def _tiene_capa(modulo: str) -> bool:
    try:
        capa(modulo)
        return True
    except KeyError:
        return False


def test_cada_modulo_importa_solo_su_capa_o_las_de_abajo():
    culpables = {}
    for modulo in MODULOS:
        propia = capa(modulo)
        if propia == "paquete":
            continue
        malas = sorted(d for d in importaciones(modulo)
                       if capa(d) not in PUEDE[propia] and (modulo, d) not in TOLERADAS)
        if malas:
            culpables[modulo] = malas
    assert culpables == {}, f"importan una capa que no les toca: {culpables}"


def test_las_toleradas_siguen_existiendo():
    """Una excepción que ya no hace falta se quita de la lista, para que no tape una nueva."""
    sobran = [par for par in TOLERADAS if par[1] not in importaciones(par[0])]
    assert sobran == []


def test_las_puertas_hablan_solo_con_la_api():
    """Una puerta traduce un protocolo: si importara el núcleo o el pipeline, dejaría de haber una api entre ellas y el
    motor, y el mismo documento podría salir distinto según por dónde llega."""
    culpables = {m: sorted(d for d in importaciones(m) if capa(d) not in ("base", "api", "puertas"))
                 for m in MODULOS if capa(m) == "puertas"}
    assert {m: d for m, d in culpables.items() if d} == {}


def test_los_drivers_no_saben_por_que_puerta_llego_el_documento():
    culpables = {m: sorted(d for d in importaciones(m) if capa(d) in ("pipeline", "api", "puertas"))
                 for m in MODULOS if capa(m) == "drivers"}
    assert {m: d for m, d in culpables.items() if d} == {}


def test_importar_el_modelo_no_carga_los_drivers_ni_la_fachada():
    """El paquete es perezoso: quien solo necesita el modelo no paga los drivers, la fachada ni openpyxl."""
    codigo = ("import json, sys; import contaperu.modelo; "
              "print(json.dumps(sorted(m for m in sys.modules if m.startswith(('contaperu', 'openpyxl')))))")
    salida = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True, cwd=RAIZ, check=True)
    cargados = set(json.loads(salida.stdout))
    assert not cargados & {"contaperu.drivers", "contaperu.api", "contaperu.pipeline", "openpyxl"}, sorted(cargados)


def test_cada_submodulo_se_importa_el_primero_sin_ciclos():
    """Cada paquete de primer nivel importado **de primero**, con `sys.modules` limpio entre uno y otro.

    Un ciclo de imports no es una propiedad del código: es una propiedad del ORDEN en que se entra. La batería
    importa `contaperu.api` casi siempre antes que nada, así que un círculo entre dos paquetes de abajo puede
    estar verde aquí y reventar en la aplicación que importe el de dentro primero. Esto lo caza.

    Lo pide la 12.11, que sacó el comprobante a su paquete: `comprobantes/comprobante.py` necesita
    `modelo.coerciones`, y pedir un módulo hoja despierta a su paquete, de modo que si `modelo/__init__`
    volviera a importar `comprobantes` en su cabecera —en vez de perezosamente— `import contaperu.comprobantes`
    moriría con `ImportError` y `import contaperu.modelo` seguiría pasando.

    Un proceso y no uno por módulo: limpiar `contaperu*` de `sys.modules` deja el siguiente import empezando de
    cero, que es lo que se quiere probar, y evita pagar sesenta arranques de intérprete.
    """
    codigo = """
import importlib, json, sys
fallos = {}
for nombre in json.loads(sys.argv[1]):
    for cargado in [m for m in sys.modules if m == "contaperu" or m.startswith("contaperu.")]:
        del sys.modules[cargado]
    try:
        importlib.import_module(nombre)
    except Exception as e:
        fallos[nombre] = f"{type(e).__name__}: {e}"
print(json.dumps(fallos))
"""
    import contaperu
    nombres = sorted(f"contaperu.{s}" for s in contaperu._SUBMODULOS)
    salida = subprocess.run([sys.executable, "-c", codigo, json.dumps(nombres)],
                            capture_output=True, text=True, cwd=RAIZ, check=True)
    assert json.loads(salida.stdout) == {}, salida.stdout


# ── El `rol` es una etiqueta para los destinos, y el núcleo no manda por ella ─────────────────────────────────

def _compra_con_detraccion() -> dict:
    """Un documento que produce las cinco líneas con sus cinco roles distintos, que es lo que hace útil el test."""
    return {"open_accounting": "3.0",
            "libro": {"ruc": "20601234567", "razon_social": "EMPRESA DE PRUEBA SAC", "periodo": "202608",
                      "tipo": "compra"},
            "comprobantes": [{"tipo_cp": "01", "serie": "F001", "numero": "123", "fecha_emision": "2026-08-05",
                              "contraparte_doc": "20602222226", "contraparte_nombre": "PROVEEDOR SAC",
                              "moneda": "PEN", "base_gravada": "1000.00", "igv": "180.00", "total": "1180.00",
                              "detraccion": {"codigo": "037", "tasa": "12", "monto": "141.60"},
                              "id_externo": "x1"}],
            "imputaciones": {"x1": {"cuenta_contable": "6311100"}}}


def test_el_nucleo_no_decide_nada_por_el_rol():
    """Se **anota** cada línea con un papel y lo que el núcleo calcula no cambia.

    Es la versión de comportamiento de una regla de arquitectura, y desde la 10.0 mide una cosa distinta y más
    útil: el `rol` **ya no viaja en la línea**, así que el núcleo no puede leer uno que el motor escribió. Lo que
    sí puede llegarle es una línea que alguien anotó —la api lo hace para el pre-mayor, porque está por encima de
    `drivers` y puede derivarlo—, y eso no tiene derecho a mover nada: ni la huella, ni el cuadre, ni un importe.

    `asiento.huella.SIN` sigue excluyendo el `rol` justo por esto, y es lo único que impide que anotar una línea le
    cambie la huella. Si algún día hace falta que el núcleo decida por el rol, este test cae y hay que discutirlo,
    no descubrirlo."""
    from contaperu import api
    from contaperu.asiento import huella  # la función, que  reexporta
    from contaperu.contable import partida_doble
    from contaperu.drivers.kit.rol import rol_de

    lineas = api.generar_asiento(_compra_con_detraccion(), driver="asiento_contable", configuracion={})["asiento"]
    assert all("rol" not in ln for ln in lineas), "el motor dejó de emitir el `rol` en la 10.0"
    papeles = {rol_de(ln, "compra") for ln in lineas}
    assert len(papeles) == 5, f"el caso tiene que traer los cinco papeles o no prueba nada: {papeles}"

    antes = (huella(lineas), partida_doble.cuadra(lineas))
    # Las dos formas en que una línea puede llegar anotada: con su papel de verdad y con uno inventado. Ninguna
    # mueve nada, que es la afirmación entera.
    for anotar in (lambda ln: rol_de(ln, "compra"), lambda ln: "un_rol_que_no_existe"):
        anotadas = [{**ln, "rol": anotar(ln)} for ln in lineas]
        assert (huella(anotadas), partida_doble.cuadra(anotadas)) == antes, \
            "el núcleo cambió de respuesta al anotar el papel de cada línea"


def test_el_resumen_informa_los_roles_y_no_cuenta_con_ellos():
    """El único módulo del núcleo que lee el rol, y lo que hace con él es **informarlo**: anota qué papeles juega
    cada cuenta. Los importes no lo miran, y eso es lo que se comprueba aquí — reescribir los roles cambia lo que
    el resumen dice de ellos y **ni un céntimo** de lo que suma."""
    from contaperu import api
    from contaperu.contable import resumen

    lineas = api.generar_asiento(_compra_con_detraccion(), driver="asiento_contable", configuracion={})["asiento"]
    def sin_los_roles(r: dict) -> dict:
        return {k: v for k, v in r.items() if k != "cuentas"} | {
            "cuentas": [{k: v for k, v in c.items() if k != "roles"} for c in r.get("cuentas", [])]}

    original = resumen.por_cuenta(lineas)
    revuelto = resumen.por_cuenta([{**ln, "rol": "un_rol_que_no_existe"} for ln in lineas])
    assert sin_los_roles(original) == sin_los_roles(revuelto)


_ROL = "rol"


# Los dos módulos que pueden comparar un `rol`, con su motivo escrito. **Ninguno de los dos decide un asiento.**
# Que la lista sea corta y nombrada es el punto: el test de abajo falla también si una entrada deja de hacer falta,
# así que una excepción no se queda aquí por inercia.
# **Era una lista de dos y la 10.0 la dejó en uno**, y lo cazó este mismo test: `api.operaciones` avisaba de un
# rol fuera del catálogo, y ese aviso se fue con el campo —una línea con `rol` ya no se degrada, falla el esquema—.
COMPARAN_UN_ROL_A_PROPOSITO = {
    "contaperu.drivers.contrato.examen":
        "`Columna.rol` no es el rol de una línea: es la configuración de un driver, que declara qué línea llena "
        "cada columna. Son dos cosas con el mismo nombre, y esta se queda (la otra se va).",
}


def test_nadie_se_bifurca_por_el_rol_de_una_linea():
    """El hermano sintáctico del de arriba, y el que caza un `if linea.rol == "tercero"` **antes** de producción.

    Lo que prohíbe es COMPARAR el rol contra un valor, que es decidir por él. No prohíbe mirar si lo trae —
    `contable/resumen` hace `if campo(linea, "rol")` para saber si tiene algo que informar, y eso es correcto: es
    la presencia, no cuál. La diferencia es justo la línea que separa informar de decidir.

    **Desde la 9.2 vale para TODO el paquete y no solo para el núcleo** (John, 10-oct-2026). Hasta entonces los
    drivers quedaban fuera porque allí el rol sí mandaba: era la columna que su sistema pide. Lo que cambió es de
    dónde sale ese rol — `drivers.kit.rol.rol_de()` lo **deriva** de los datos que la línea trae, que es la lógica
    de SAF-T, así que un driver ya no necesita que el asiento le traiga la etiqueta.

    Importa porque es lo que convirtió el campo en pura salida: **no se puede retirar un campo que algo lee**, y la
    2.0 del estándar lo retiró. La excepción que queda va arriba, con su motivo."""
    culpables = []
    for modulo, archivo in MODULOS.items():
        if modulo in COMPARAN_UN_ROL_A_PROPOSITO or modulo == "contaperu.drivers.kit.rol":
            continue
        for nodo in ast.walk(ast.parse(archivo.read_text(encoding="utf-8"))):
            if not isinstance(nodo, ast.Compare):
                continue
            # Se mira TODO el subárbol de la comparación y no solo sus dos lados: el núcleo lee el campo con un
            # accesor genérico (`campo(linea, "rol")`), así que buscar solo `.rol` o `["rol"]` dejaba pasar el
            # caso real. Lo descubrió la mutación de este propio test, que es para lo que se mutan.
            for dentro in ast.walk(nodo):
                mira_el_rol = ((isinstance(dentro, ast.Attribute) and dentro.attr == _ROL)
                               or (isinstance(dentro, ast.Constant) and dentro.value == _ROL))
                if mira_el_rol:
                    culpables.append(f"{modulo}:{nodo.lineno}")
                    break
    assert not culpables, (
        f"se compara el rol contra un valor en: {sorted(set(culpables))}. El rol es una etiqueta de SALIDA: el "
        "motor lo produce y nadie decide por él. Lo que un driver necesita lo deriva con "
        "`drivers.kit.rol.rol_de()`; si hace falta decidir en el núcleo, el dato va en un bloque tipado de la "
        "línea —como `impuesto` o `detraccion`, que es lo que hacen SAF-T y EN 16931— y no en el rol.")

    # Y la otra mitad: una excepción que ya no se usa se quita. Si no, la lista crece y deja de decir nada.
    sobran = [m for m in COMPARAN_UN_ROL_A_PROPOSITO
              if not any(isinstance(d, (ast.Attribute, ast.Constant))
                         and (getattr(d, "attr", None) == _ROL or getattr(d, "value", None) == _ROL)
                         for n in ast.walk(ast.parse(MODULOS[m].read_text(encoding="utf-8")))
                         if isinstance(n, ast.Compare) for d in ast.walk(n))]
    assert not sobran, (f"estos módulos ya no comparan ningún rol, así que su excepción sobra: {sobran}. "
                        "Quítala de COMPARAN_UN_ROL_A_PROPOSITO.")


_LECTURAS = {"read_text", "read_bytes", "write_text", "write_bytes"}


def test_el_nucleo_y_los_drivers_no_abren_archivos():
    """Hito 0.5: lo que el núcleo necesita le llega en bytes o diccionarios, y lo que viaja con el paquete lo lee
    `_datos`. Un `open()` o un `Path.read_*` en el núcleo o en un driver haría depender una regla del disco."""
    culpables = []
    for modulo, archivo in MODULOS.items():
        if capa(modulo) not in ("nucleo", "drivers"):
            continue
        for nodo, _ in _recorrer(ast.parse(archivo.read_text(encoding="utf-8"))):
            if not isinstance(nodo, ast.Call):
                continue
            if isinstance(nodo.func, ast.Name) and nodo.func.id == "open":
                culpables.append(f"{modulo}:{nodo.lineno} open()")
            elif isinstance(nodo.func, ast.Attribute) and nodo.func.attr in _LECTURAS:
                culpables.append(f"{modulo}:{nodo.lineno} .{nodo.func.attr}()")
    assert culpables == []


# ── J0: el acoplamiento con lo peruano, a la vista ────────────────────────────────────────────────────────────────

# Los módulos que son contabilidad peruana por lo que IMPORTAN a otros: catálogos de SUNAT, IGV, detracciones,
# validación de SUNAT, PCGE, los lectores del UBL de SUNAT y de la propuesta del SIRE, y el driver del SIRE.
PERUANOS = ("contaperu.catalogos", "contaperu.pcge", "contaperu.tributos", "contaperu.sunat",
            "contaperu.lectores.xml_ubl", "contaperu.lectores.sire_txt", "contaperu.drivers.sire")
# Y los que lo son por lo que CONTIENEN, aunque no importen nada peruano. Separarlos es J2-J4, con un cliente real.
PERUANOS_POR_CONTENIDO = {
    # Las once operaciones de la API del SIRE, cada una con el manual del que sale. No importa nada peruano —lee su
    # catálogo por `_datos`— y es peruano de arriba abajo: separarlo es J2-J4, con un cliente real de fuera.
    "contaperu.sunat:OPERACIONES": "las once operaciones de la API del SIRE, con la ruta y el manual de cada una",
    "contaperu.modelo:Libro": "exige un RUC de 11 dígitos y un periodo AAAAMM de venta o compra",
    "contaperu.comprobantes:Comprobante": "los impuestos del Perú en campos fijos (base gravada, IGV, ISC, IVAP, ICBPER)",
    # El mismo de la línea de arriba, pedido por su ruta vieja: desde la 12.11 `Comprobante` vive en
    # `comprobantes/` y `modelo` lo resuelve perezosamente. Que esta entrada siga verde es lo que prueba que la
    # fachada no perdió el nombre, así que no se quita aunque parezca repetida.
    "contaperu.modelo:Comprobante": "los impuestos del Perú en campos fijos (base gravada, IGV, ISC, IVAP, ICBPER)",
    "contaperu.configuracion:CONFIGURACION_GENERAL": "las cuentas del PCGE y las tasas de detracción",
    # El CCI es peruano de arriba abajo, y la constancia nombra el Catálogo 05 de SUNAT en sus referencias. No
    # importa nada peruano —solo las coerciones del modelo—, así que es de los que se detectan por contenido.
    "contaperu.tesoreria:LARGO_CCI": "el Código de Cuenta Interbancario del Perú: 20 dígitos, 3+3+12+2",
    "contaperu.asiento.configuracion:CONFIGURACION_DEL_ASIENTO": "la Tabla 10, los sub-diarios y la detracción",
}


def _peruano(modulo: str) -> bool:
    return any(modulo == p or modulo.startswith(p + ".") for p in PERUANOS)


def acoplamiento() -> dict[str, list[str]]:
    salida = {}
    for modulo in MODULOS:
        peruanos = sorted(d for d in importaciones(modulo) if _peruano(d) and not _peruano(modulo))
        if peruanos:
            salida[modulo] = peruanos
    return salida


def regenerar() -> None:
    """Reescribe el acoplamiento congelado. Solo cuando se añade o se quita un acoplamiento A PROPÓSITO."""
    ACOPLAMIENTO.parent.mkdir(parents=True, exist_ok=True)
    ACOPLAMIENTO.write_bytes((json.dumps(acoplamiento(), ensure_ascii=False, indent=1) + "\n").encode("utf-8"))


def test_el_acoplamiento_con_lo_peruano_no_crece_sin_verse():
    congelado = json.loads(ACOPLAMIENTO.read_text(encoding="utf-8"))
    hoy = acoplamiento()
    nuevos = {m: sorted(set(p) - set(congelado.get(m, []))) for m, p in hoy.items()}
    assert {m: p for m, p in nuevos.items() if p} == {}, (
        "un módulo que no es peruano empezó a importar uno que sí: si es a propósito, regenera el acoplamiento")
    assert hoy == congelado, "un acoplamiento desapareció: regenera el archivo para que la lista siga siendo la de hoy"


@pytest.mark.parametrize("ruta", sorted(PERUANOS_POR_CONTENIDO))
def test_lo_peruano_por_contenido_sigue_donde_se_dice(ruta):
    import importlib
    modulo, _, nombre = ruta.partition(":")
    assert hasattr(importlib.import_module(modulo), nombre)


# Tres submódulos se llaman igual que algo que su paquete exporta, y en los tres el atributo del paquete tiene que ser
# la función: hay código que la llama así —`api/documento.py` hace `preparacion.documento(...)`—. Gana la función
# porque `from .x import x` la enlaza después de que el sistema de imports ponga el módulo, y sigue ganando aunque
# alguien importe el submódulo a mano o añada `from . import x`: lo segundo prefiere el atributo que ya existe.
#
# Lo que SÍ lo rompe es que la fachada deje de exportar el nombre; entonces el atributo es el módulo y la llamada
# muere con «'module' object is not callable». Eso ya revienta ochenta y tres tests, pero ninguno lo dice: este lo
# dice en una línea, y por eso vive aquí y no al lado de ninguno de ellos.
TAPADOS = ("contaperu.asiento:huella", "contaperu.pcge:adaptar", "contaperu.pipeline.preparacion:documento")


@pytest.mark.parametrize("ruta", TAPADOS)
def test_donde_un_submodulo_se_llama_como_una_funcion_gana_la_funcion(ruta):
    import importlib
    paquete, _, nombre = ruta.partition(":")
    importlib.import_module(f"{paquete}.{nombre}")   # importarlo explícitamente no cambia el atributo
    assert callable(getattr(importlib.import_module(paquete), nombre))


def test_no_hay_assert_en_el_paquete():
    """Un `assert` desaparece con `python -O`: lo que protege un archivo no puede depender de cómo se arranca Python. Lo
    que no se cumple se dice con una excepción del motor."""
    culpables = [f"{modulo}:{nodo.lineno}" for modulo, archivo in MODULOS.items()
                 for nodo, _ in _recorrer(ast.parse(archivo.read_text(encoding="utf-8"))) if isinstance(nodo, ast.Assert)]
    assert culpables == []
