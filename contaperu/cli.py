"""CLI del motor: generar el TXT del SIRE desde XML locales, sin API ni portal.

    contaperu generar --tipo venta --ruc 20601234567 --razon "MI EMPRESA SAC" \
        --periodo 202512 --driver todas --salida ./salida  comprobantes/*.xml  lote.zip

    contaperu desde-json tests/fixtures/golden/ventas_202512.json --driver sire

Herramienta de diagnóstico: genera el TXT del SIRE fuera dla aplicación que lo use (la fase de
la prueba real en SUNAT se cerró el 25-ago-2026) y compara propuestas con
`comparar`. "todas" = los drivers de TXT, que hoy es solo el SIRE.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import comparar_sire
from . import __version__, asiento as asi, drivers, generar as gen, operaciones, validar
from .lectores import archivos
from .modelo import Libro

# Esta puerta pasa por `operaciones` para todo lo que la fachada sabe hacer —leer un documento y
# escribirlo— y baja al núcleo solo donde la fachada no aplica: `gen.generar` devuelve los BYTES del
# archivo, que es lo que aquí hay que escribir en disco, mientras `operaciones.exportar` los
# devuelve en base64 porque su contrato es JSON. Codificar para decodificar sería peor.


def _tabla(comprobantes: list[Comprobante]) -> str:
    filas = ["  #  TIPO  SERIE-NUMERO        FECHA       CONTRAPARTE                          TOTAL        ESTADO"]
    for i, c in enumerate(comprobantes, 1):
        serie_numero = f"{c.serie}-{c.numero}" if c.serie else c.numero
        fecha = c.fecha_emision.strftime("%d/%m/%Y") if c.fecha_emision else "--/--/----"
        nombre = (c.contraparte_nombre or "")[:36]
        marca = "EXCL" if c.excluida else c.estado.upper()
        filas.append(f"{i:3d}  {c.tipo_cp:<4}  {serie_numero:<18}  {fecha}  {nombre:<36} "
                     f"{c.moneda} {c.total:>11}  {marca}")
        for observacion in c.observaciones:
            nivel = "!!" if observacion.nivel == "error" else " ·"
            filas.append(f"        {nivel} [{observacion.codigo}] {observacion.texto}")
    return "\n".join(filas)


def _leer_json(ruta: str) -> dict:
    """Un JSON que escribió una persona en Windows —el Bloc de notas, `Out-File` de PowerShell— suele
    llevar BOM, y `json.loads` lo rechaza. `utf-8-sig` lo quita si está y no cambia nada si no está."""
    return json.loads(Path(ruta).read_text(encoding="utf-8-sig"))


def _escribir(exp: gen.Exportado, salida: Path) -> None:
    salida.mkdir(parents=True, exist_ok=True)
    if exp.texto:
        # Un registro en texto: el TXT y el ZIP con el que se sube a SUNAT.
        (salida / exp.nombre).write_bytes(exp.texto)
        (salida / exp.nombre_comprimido).write_bytes(exp.comprimido)
        destino = salida / exp.nombre_comprimido
    else:
        # Un archivo (el Excel de CONCAR, el CSV, el registro de un sistema contable, el de un driver de
        # terceros): tal cual.
        destino = salida / exp.archivo
        destino.write_bytes(exp.contenido)
    print(f"  {exp.driver:<5} {exp.formato:<9} {exp.comprobantes:>3} comprobantes  → {destino}")


def _generar_todas(libro: Libro, comprobantes: list[Comprobante], driver: str, salida: Path,
                   incluir_errores: bool, config: dict | None = None) -> int:
    # "todas" = los drivers de TXT. Los que llevan cuentas (CONCAR, el CSV, el registro de un sistema contable,
    # los de terceros) se piden por su nombre: necesitan la configuración contable del contribuyente —la de
    # --config, con la imputación de --imputacion dentro—, y los de asientos, además sus correlativos, que
    # arrancan en 1: los mismos valores de partida que usa `operaciones.exportar`.
    nombres = ([nombre for nombre, registrado in drivers.DRIVERS.items()
                if drivers.contrato.forma(registrado) == "linea"]
               if driver == "todas" else [driver])
    config = operaciones.configuracion() if config is None else config
    codigo = 0
    for nombre_driver in nombres:
        modulo = drivers.obtener(nombre_driver)
        if libro.tipo not in modulo.FORMATOS:
            print(f"  {nombre_driver:<5} no genera libros de {libro.tipo}", file=sys.stderr)
            continue
        correlativos = None
        if drivers.contrato.arma_asientos(modulo):
            incluidos = gen.seleccionar(comprobantes)
            presentes = asi.sub_diarios_presentes(incluidos, config, libro.es_venta)
            correlativos = {sub_diario: 1 for sub_diario in presentes}
        try:
            _escribir(gen.generar(libro, comprobantes, nombre_driver, incluir_errores=incluir_errores,
                                  config=config if drivers.contrato.lleva_cuentas(modulo) else None,
                                  correlativos=correlativos), salida)
        except gen.ErroresBloqueantes as error:
            print(f"  {nombre_driver:<5} NO generado: {error}. Corrige o usa --incluir-errores", file=sys.stderr)
            codigo = 1
        except (asi.SinCuenta, asi.SinCentro, asi.TipoSinMapa, asi.MonedaSinCodigo, drivers.concar.CorrelativoDesborda,
                drivers.contrato.NoCabe) as error:
            # Lo que le falta al mes para ese destino. `contaperu diagnosticar` lo lista por serie-número.
            print(f"  {nombre_driver:<5} NO generado: {error}. Revísalo con `contaperu diagnosticar`", file=sys.stderr)
            codigo = 1
    return codigo


def cmd_generar(args: argparse.Namespace) -> int:
    libro = Libro(ruc=args.ruc, razon_social=args.razon, periodo=args.periodo, tipo=args.tipo)
    lote = archivos.Lote()
    for ruta in args.archivos:
        archivo = Path(ruta)
        if not archivo.is_file():
            lote.error(ruta, "No existe")
            continue
        archivos.expandir(archivo.name, archivo.read_bytes(), lote=lote)
    lectura = archivos.convertir_xml(lote, libro)
    comprobantes = archivos.ordenar(lectura.comprobantes)
    validar.revisar(comprobantes, libro)

    print(f"Libro: {libro.tipo.upper()} {libro.periodo} · RUC {libro.ruc} · {libro.razon_social}")
    print(f"Archivos: {len(lote.entradas)} leídos · {len(lectura.ignorados)} ignorados (CDR, hojas de estilo) · "
          f"{len(lectura.pendientes_ia)} PDF/imagen (pendientes de IA) · {len(lectura.errores)} con error")
    for error in lectura.errores:
        print(f"  !! {error['archivo']}: {error['motivo']}")
    print()
    print(_tabla(comprobantes))
    print()
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        # `operaciones.documento` y no un dict a mano: era la fuente de un desajuste real — este
        # comando emitía un JSON SIN la clave `open_accounting`, y el golden de los tests tenía que
        # añadírsela para poder validar contra el esquema del estándar.
        Path(args.json).write_text(
            json.dumps(operaciones.documento(libro, comprobantes), ensure_ascii=False, indent=1),
            encoding="utf-8")
        print(f"Datos estructurados → {args.json}")
    if not comprobantes:
        print("No hay comprobantes que exportar.", file=sys.stderr)
        return 1
    return _generar_todas(libro, comprobantes, args.driver, Path(args.salida), args.incluir_errores)


def cmd_desde_json(args: argparse.Namespace) -> int:
    datos = _leer_json(args.json)
    # Por la fachada: así este comando gana lo que antes se saltaba al construir los objetos a mano
    # —el motivo legible cuando falta el bloque `libro`, y el tope de 5.000 comprobantes— y lee el
    # documento con las MISMAS reglas que el servidor MCP.
    try:
        libro = operaciones.libro_de(datos)
        comprobantes = operaciones.comprobantes_de(datos)
    except operaciones.DocumentoInvalido as error:
        print(f"El archivo no es un documento open-accounting válido: {error}", file=sys.stderr)
        return 2
    if args.revisar:
        validar.revisar(comprobantes, libro)
        print(_tabla(comprobantes))
    config = _leer_json(args.config) if args.config else None
    imputacion = _leer_json(args.imputacion) if args.imputacion else None
    try:
        config = operaciones.con_imputacion(operaciones.configuracion(config), imputacion, comprobantes)
    except operaciones.DocumentoInvalido as error:
        print(f"La imputación no se puede usar con este documento: {error}", file=sys.stderr)
        return 2
    return _generar_todas(libro, comprobantes, args.driver, Path(args.salida), args.incluir_errores, config)


def _lista(titulo: str, elementos: list, vacio: str = "ninguno") -> None:
    print(f"{titulo}: {', '.join(str(elemento) for elemento in elementos) if elementos else vacio}")


def cmd_diagnosticar(args: argparse.Namespace) -> int:
    """Qué bloquea, qué falta y qué saldría, antes de generar nada."""
    datos = _leer_json(args.json)
    config = _leer_json(args.config) if args.config else None
    imputacion = _leer_json(args.imputacion) if args.imputacion else None
    try:
        diagnostico = operaciones.diagnosticar(datos, config, driver=args.driver, imputacion=imputacion)
    except operaciones.DocumentoInvalido as error:
        # El documento que no se puede leer, o una imputación que no es de él: el motivo va en `e`.
        print(f"No se puede diagnosticar: {error}", file=sys.stderr)
        return 2
    libro, totales = diagnostico["libro"], diagnostico["totales"]
    print(f"Libro: {libro['tipo'].upper()} {libro['periodo']} · RUC {libro['ruc']} · destino {diagnostico['driver']}")
    print(f"Comprobantes: {totales['comprobantes']} · saldrían {totales['saldrian']} · "
          f"excluidos {totales['excluidos']} · fuera del registro {totales['fuera_del_registro']} · "
          f"con error {totales['con_error']} · con aviso {totales['con_aviso']}")
    print()
    for bloque, marca in (("bloqueantes", "!!"), ("avisos", " ·")):
        for entrada in diagnostico[bloque]:
            for observacion in entrada["observaciones"]:
                print(f"  {marca} {entrada['serie_numero']:<18} [{observacion['codigo']}] {observacion['texto']}")
    for clave, titulo in (("reparto_no_admitido", "Reparto que el destino no admite"),
                          ("sin_cuenta", "Sin cuenta contable"), ("reparto_no_cuadra", "Reparto que no suma la base"),
                          ("sin_centro_de_costo", "Sin centro de costo"),
                          ("tipos_sin_equivalencia", "Tipos sin equivalencia"),
                          ("monedas_sin_codigo", "Monedas sin código"),
                          ("sub_diarios_sin_correlativo", "Sub-diarios sin correlativo (arrancan en 1)")):
        if diagnostico["faltantes"].get(clave):
            _lista(titulo, diagnostico["faltantes"][clave])
    for motivo, cuales in diagnostico["faltantes"].get("no_caben", {}).items():
        _lista(f"No cabe en el formato ({motivo})", cuales)
    if diagnostico["detracciones_pendientes"]:
        _lista("Detracciones pendientes de constancia",
               [pendiente["serie_numero"] for pendiente in diagnostico["detracciones_pendientes"]])
    if diagnostico.get("que_falta"):
        quien = {"contador": "Pedir al contador", "sistema": "Ajustar en el sistema", "proveedor": "Pedir al proveedor"}
        for falta in diagnostico["que_falta"]:
            destinatario = quien.get(falta["pedir_a"], falta["pedir_a"])
            print(f"  -> {destinatario}: {falta['texto']} ({', '.join(falta['comprobantes'])})")
    for sub_diario, rango in diagnostico["sub_diarios"].items():
        print(f"  Sub-diario {sub_diario} ({rango['etiqueta']}): {rango['comprobantes']} comprobantes "
              f"desde el {rango['empieza_en']}")
    print()
    if diagnostico["listo_para_exportar"]:
        print(f"LISTO para exportar: {len(diagnostico['saldrian'])} comprobantes.")
        return 0
    print("NO está listo: " + "; ".join(diagnostico["por_que_no"]) + ".")
    return 1


def cmd_comparar(args: argparse.Namespace) -> int:
    """Nuestro archivo del SIRE contra la exportación del detalle que da SUNAT."""
    try:
        registro = comparar_sire.registro_de([args.nuestro, args.sunat], args.registro)
    except ValueError as error:
        print(error)
        return 2
    comparacion = comparar_sire.comparar(comparar_sire.leer(args.nuestro), comparar_sire.leer(args.sunat), registro)
    print(comparar_sire.informe(comparacion))
    return 1 if (comparacion["diferencias"] or comparacion["solo_en_sunat"] or comparacion["solo_nuestros"]) else 0


def _consola_utf8() -> None:
    """La consola de Windows usa cp1252 por defecto y revienta con una flecha o una tilde.
    Un contador peruano trabaja en Windows: que la herramienta se caiga al IMPRIMIR, con los
    archivos ya generados, es de las cosas mas absurdas que pueden pasar."""
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):     # ya redirigido, o no es una consola
            pass


# La imputación de cada documento llega aparte del documento, igual que por la fachada (`operaciones.con_imputacion`).
AYUDA_IMPUTACION = ("JSON con la imputación de cada documento, por su id_externo: "
                    "{id: {cuenta_contable, centro_costo, cuenta_tercero, reparto}}")


def main(argv: list[str] | None = None) -> int:
    _consola_utf8()
    analizador = argparse.ArgumentParser(prog="contaperu", description=__doc__,
                                         formatter_class=argparse.RawDescriptionHelpFormatter)
    analizador.add_argument("--version", action="version", version=f"contaperu {__version__}")
    subcomandos = analizador.add_subparsers(dest="cmd", required=True)

    sub_generar = subcomandos.add_parser("generar", help="XML/ZIP locales → TXT + ZIP para el SIRE")
    sub_generar.add_argument("--tipo", required=True, choices=["venta", "compra"])
    sub_generar.add_argument("--ruc", required=True)
    sub_generar.add_argument("--razon", required=True, help="razón social del generador (va en la driver sire)")
    sub_generar.add_argument("--periodo", required=True, help="AAAAMM")
    sub_generar.add_argument("--driver", default="todas", choices=["todas", *drivers.DRIVERS])
    sub_generar.add_argument("--salida", default="salida")
    sub_generar.add_argument("--incluir-errores", action="store_true",
                             help="generar aunque haya observaciones de error")
    sub_generar.add_argument("--json", help="volcar los comprobantes leídos a este JSON (para fixtures)")
    sub_generar.add_argument("archivos", nargs="+")
    sub_generar.set_defaults(fn=cmd_generar)

    sub_desde_json = subcomandos.add_parser("desde-json",
                                            help="JSON de comprobantes (formato de los golden) → TXT + ZIP")
    sub_desde_json.add_argument("json")
    sub_desde_json.add_argument("--driver", default="todas", choices=["todas", *drivers.DRIVERS])
    sub_desde_json.add_argument("--salida", default="salida")
    sub_desde_json.add_argument("--revisar", action="store_true", help="aplicar las validaciones antes de generar")
    sub_desde_json.add_argument("--incluir-errores", action="store_true")
    sub_desde_json.add_argument("--config", help="JSON con la configuración contable (la piden los drivers que "
                                                 "llevan cuentas: concar, csv…)")
    sub_desde_json.add_argument("--imputacion", help=AYUDA_IMPUTACION)
    sub_desde_json.set_defaults(fn=cmd_desde_json)

    sub_diagnosticar = subcomandos.add_parser("diagnosticar",
                                              help="qué bloquea, qué falta y qué saldría, antes de generar nada")
    sub_diagnosticar.add_argument("json", help="documento open-accounting")
    sub_diagnosticar.add_argument("--driver", default="concar", choices=list(drivers.DRIVERS))
    sub_diagnosticar.add_argument("--config", help="JSON con la configuración contable del contribuyente")
    sub_diagnosticar.add_argument("--imputacion", help=AYUDA_IMPUTACION)
    sub_diagnosticar.set_defaults(fn=cmd_diagnosticar)

    sub_comparar = subcomandos.add_parser("comparar",
                                          help="nuestro TXT del SIRE vs la exportación del detalle de SUNAT")
    sub_comparar.add_argument("--nuestro", required=True,
                              help="TXT o ZIP que genera la aplicación que lo use (reemplazar propuesta)")
    sub_comparar.add_argument("--sunat", required=True,
                              help="TXT o ZIP de la exportación del detalle (menú Exportar → ticket)")
    sub_comparar.add_argument("--registro", default="", choices=["", "venta", "compra"],
                              help="normalmente se deduce del nombre (1404 ventas / 0804 compras); fuérzalo si no")
    sub_comparar.set_defaults(fn=cmd_comparar)

    args = analizador.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
