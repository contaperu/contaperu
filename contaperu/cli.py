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
from . import __version__, drivers, generar as gen, operaciones, validar
from .lectores import archivos
from .modelo import Libro

# Esta puerta pasa por `operaciones` para todo lo que la fachada sabe hacer —leer un documento y
# escribirlo— y baja al núcleo solo donde la fachada no aplica: `gen.generar` devuelve los BYTES del
# archivo, que es lo que aquí hay que escribir en disco, mientras `operaciones.exportar` los
# devuelve en base64 porque su contrato es JSON. Codificar para decodificar sería peor.


def _tabla(comprobantes: list[Comprobante]) -> str:
    filas = ["  #  TIPO  SERIE-NUMERO        FECHA       CONTRAPARTE                          TOTAL        ESTADO"]
    for i, c in enumerate(comprobantes, 1):
        sn = f"{c.serie}-{c.numero}" if c.serie else c.numero
        f = c.fecha_emision.strftime("%d/%m/%Y") if c.fecha_emision else "--/--/----"
        nombre = (c.contraparte_nombre or "")[:36]
        marca = "EXCL" if c.excluida else c.estado.upper()
        filas.append(f"{i:3d}  {c.tipo_cp:<4}  {sn:<18}  {f}  {nombre:<36} {c.moneda} {c.total:>11}  {marca}")
        for o in c.observaciones:
            filas.append(f"        {'!!' if o.nivel == 'error' else ' ·'} [{o.codigo}] {o.texto}")
    return "\n".join(filas)


def _escribir(exp: gen.Exportado, salida: Path) -> None:
    salida.mkdir(parents=True, exist_ok=True)
    (salida / exp.nombre).write_bytes(exp.txt)
    (salida / exp.nombre_zip).write_bytes(exp.zip)
    print(f"  {exp.driver:<5} {exp.formato:<9} {exp.n_filas:>3} filas  → {salida / exp.nombre_zip}")


def _generar_todas(libro: Libro, comprobantes: list[Comprobante], driver: str, salida: Path,
                   incluir_errores: bool) -> int:
    # "todas" = los drivers de TXT (el Excel de CONCAR necesita correlativos y cuentas: va por la aplicación que lo use)
    nombres = [n for n, m in drivers.DRIVERS.items() if not hasattr(m, "construir")] if driver == "todas" else [driver]
    codigo = 0
    for p in nombres:
        if libro.tipo not in drivers.obtener(p).FORMATOS:
            print(f"  {p:<5} no genera libros de {libro.tipo}", file=sys.stderr)
            continue
        try:
            _escribir(gen.generar(libro, comprobantes, p, incluir_errores=incluir_errores), salida)
        except gen.ErroresBloqueantes as e:
            print(f"  {p:<5} NO generado: {e}. Corrige o usa --incluir-errores", file=sys.stderr)
            codigo = 1
    return codigo


def cmd_generar(args: argparse.Namespace) -> int:
    libro = Libro(ruc=args.ruc, razon_social=args.razon, periodo=args.periodo, tipo=args.tipo)
    lote = archivos.Lote()
    for ruta in args.archivos:
        p = Path(ruta)
        if not p.is_file():
            lote.error(ruta, "No existe")
            continue
        archivos.expandir(p.name, p.read_bytes(), lote=lote)
    res = archivos.convertir_xml(lote, libro)
    comprobantes = archivos.ordenar(res.comprobantes)
    validar.revisar(comprobantes, libro)

    print(f"Libro: {libro.tipo.upper()} {libro.periodo} · RUC {libro.ruc} · {libro.razon_social}")
    print(f"Archivos: {len(lote.entradas)} leídos · {len(res.ignorados)} ignorados (CDR, hojas de estilo) · "
          f"{len(res.pendientes_ia)} PDF/imagen (pendientes de IA) · {len(res.errores)} con error")
    for e in res.errores:
        print(f"  !! {e['archivo']}: {e['motivo']}")
    print()
    print(_tabla(comprobantes))
    print()
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        # `operaciones.documento` y no un dict a mano: era la fuente de un desajuste real — este
        # comando emitía un JSON SIN la clave `pe_ledger`, y el golden de los tests tenía que
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
    datos = json.loads(Path(args.json).read_text(encoding="utf-8"))
    # Por la fachada: así este comando gana lo que antes se saltaba al construir los objetos a mano
    # —el motivo legible cuando falta el bloque `libro`, y el tope de 5.000 comprobantes— y lee el
    # documento con las MISMAS reglas que el servidor MCP.
    try:
        libro = operaciones.libro_de(datos)
        comprobantes = operaciones.comprobantes_de(datos)
    except operaciones.DocumentoInvalido as e:
        print(f"El archivo no es un documento pe-ledger válido: {e}", file=sys.stderr)
        return 2
    if args.revisar:
        validar.revisar(comprobantes, libro)
        print(_tabla(comprobantes))
    return _generar_todas(libro, comprobantes, args.driver, Path(args.salida), args.incluir_errores)


def cmd_comparar(args: argparse.Namespace) -> int:
    """Nuestro archivo del SIRE contra la exportación del detalle que da SUNAT."""
    try:
        reg = comparar_sire.registro_de([args.nuestro, args.sunat], args.registro)
    except ValueError as e:
        print(e)
        return 2
    r = comparar_sire.comparar(comparar_sire.leer(args.nuestro), comparar_sire.leer(args.sunat), reg)
    print(comparar_sire.informe(r))
    return 1 if (r["diferencias"] or r["solo_en_sunat"] or r["solo_nuestros"]) else 0


def _consola_utf8() -> None:
    """La consola de Windows usa cp1252 por defecto y revienta con una flecha o una tilde.
    Un contador peruano trabaja en Windows: que la herramienta se caiga al IMPRIMIR, con los
    archivos ya generados, es de las cosas mas absurdas que pueden pasar."""
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):     # ya redirigido, o no es una consola
            pass


def main(argv: list[str] | None = None) -> int:
    _consola_utf8()
    ap = argparse.ArgumentParser(prog="contaperu", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version", version=f"contaperu {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generar", help="XML/ZIP locales → TXT + ZIP para el SIRE")
    g.add_argument("--tipo", required=True, choices=["venta", "compra"])
    g.add_argument("--ruc", required=True)
    g.add_argument("--razon", required=True, help="razón social del generador (va en la driver sire)")
    g.add_argument("--periodo", required=True, help="AAAAMM")
    g.add_argument("--driver", default="todas", choices=["todas", *drivers.DRIVERS])
    g.add_argument("--salida", default="salida")
    g.add_argument("--incluir-errores", action="store_true", help="generar aunque haya observaciones de error")
    g.add_argument("--json", help="volcar los comprobantes leídos a este JSON (para fixtures)")
    g.add_argument("archivos", nargs="+")
    g.set_defaults(fn=cmd_generar)

    d = sub.add_parser("desde-json", help="JSON de comprobantes (formato de los golden) → TXT + ZIP")
    d.add_argument("json")
    d.add_argument("--driver", default="todas", choices=["todas", *drivers.DRIVERS])
    d.add_argument("--salida", default="salida")
    d.add_argument("--revisar", action="store_true", help="aplicar las validaciones antes de generar")
    d.add_argument("--incluir-errores", action="store_true")
    d.set_defaults(fn=cmd_desde_json)

    c = sub.add_parser("comparar", help="nuestro TXT del SIRE vs la exportación del detalle de SUNAT")
    c.add_argument("--nuestro", required=True, help="TXT o ZIP que genera la aplicación que lo use (reemplazar propuesta)")
    c.add_argument("--sunat", required=True, help="TXT o ZIP de la exportación del detalle (menú Exportar → ticket)")
    c.add_argument("--registro", default="", choices=["", "venta", "compra"],
                   help="normalmente se deduce del nombre (1404 ventas / 0804 compras); fuérzalo si no")
    c.set_defaults(fn=cmd_comparar)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
