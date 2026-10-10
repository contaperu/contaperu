"""Comprueba contra la API real del SIRE que el mapa del motor es cierto, y guarda lo que SUNAT contestó.

Existe por lo mismo que `extraer_pcge2026.py`: **para que cualquiera pueda rehacerlo y auditarlo**, en vez de tener
que confiar en un JSON que apareció de la nada. El motor publica las once operaciones del SIRE —ruta, método,
parámetros— en `contaperu/datos/sunat/sire_api.json`, y desde la 8.1 las arma con `contaperu.sunat.peticion`. Sin
una herramienta como esta, ese mapa es una afirmación que nadie de fuera puede contrastar.

    pip install httpx
    python herramientas/comprobar_sire.py --token <PASE> --ruc <RUC> --registro compra
    python herramientas/comprobar_sire.py --token <PASE> --ruc <RUC> --registro compra --periodo 202609 --guardar

**El token lo trae quien lo tenga.** Esta herramienta no sabe pedirlo y no va a saber: cambiar una Clave SOL por un
pase necesita un almacén de credenciales, y eso es de la aplicación que integra el motor, no del motor. Aquí el
token es un argumento, igual que allí el PDF del PCGE es un argumento. Se pasa por `--token` o por la variable
`SIRE_TOKEN`, que es lo que evita que quede en el historial del shell.

## Solo lecturas, y no es una precaución: es la del catálogo

El SIRE **no tiene ambiente de pruebas** (`limites.ambiente_de_pruebas`: «NO EXISTE… toda prueba del SIRE es contra
producción con un RUC real»). Por eso cada operación declara su `grada`, y esta herramienta **se niega** a llamar
una que no sea de lectura. Las siete de lectura son idempotentes: no cambian nada en SUNAT. Las otras cuatro tocan
un mes o declaran, y no se prueban con un script: se hacen en un cierre de verdad, a mano y mirando.

## Lo que guarda es CRUDO

Con `--guardar`, la respuesta entera va a `privado/sire/`, que `.gitignore` bloquea. **Crudo quiere decir con el RUC
y los nombres de verdad dentro**: eso no entra a un repositorio público ni anonimizado a ojo. Quien lo anonimice,
que use una herramienta con tests —la aplicación tiene la suya— y mire el resultado antes de añadirlo. La regla 6
del motor es la única que no se puede deshacer.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from contaperu import sunat  # noqa: E402

PRIVADO = pathlib.Path(__file__).resolve().parents[1] / "privado" / "sire"
# Lo que se prueba sin tocar nada de nadie, en el orden en que tiene sentido: qué meses hay, y qué dice de un mes.
DE_LECTURA = ("periodos", "excluidos", "no_incluidos")


def comprobar(token: str, registro: str, periodo: str, operaciones: tuple[str, ...], guardar: bool) -> int:
    import httpx  # se importa aquí para que `--help` funcione sin tenerlo instalado

    fallos = 0
    with httpx.Client(timeout=60.0, headers={"Authorization": f"Bearer {token}"}) as cliente:
        for nombre in operaciones:
            if sunat.grada(nombre) != "lectura":
                print(f"  {nombre:16s} SALTADA — es de grada {sunat.grada(nombre)!r}, y eso no se prueba con un "
                      f"script: toca un mes o declara ante SUNAT.")
                continue
            try:
                p = sunat.peticion(nombre, registro=registro, periodo=periodo, **_extras(nombre))
            except Exception as e:  # noqa: BLE001 — una operación que no se puede armar se dice y se sigue
                print(f"  {nombre:16s} NO SE PUDO ARMAR — {type(e).__name__}: {e}")
                fallos += 1
                continue
            try:
                r = cliente.request(p["metodo"], p["url"], params=p["params"])
            except Exception as e:  # noqa: BLE001
                print(f"  {nombre:16s} SIN RESPUESTA — {type(e).__name__}: {e}")
                fallos += 1
                continue
            print(f"  {nombre:16s} {r.status_code}  {len(r.content)} bytes  {p['metodo']} {p['url'][40:]}")
            if r.status_code >= 400:
                fallos += 1
                _explicar(nombre, r)
            if guardar:
                _guardar(f"{nombre}-{registro}-{periodo or 'sin-periodo'}", r)
    return fallos


def _extras(operacion: str) -> dict:
    """Lo que cada lectura exige además del registro y el periodo, con el valor más inofensivo."""
    # `codTipoArchivo` 0 es el TXT (`libros.cod_tipo_archivo`). Es un 0 de verdad, no un «vacío».
    return {"codTipoArchivo": 0} if operacion in ("excluidos", "no_incluidos") else {}


def _explicar(operacion: str, respuesta) -> None:
    """Un rechazo, leído con el clasificador del motor — que es justo lo que esta herramienta viene a comprobar."""
    try:
        cuerpo = respuesta.json()
    except ValueError:
        print(f"{'':18s} cuerpo no JSON ({respuesta.headers.get('content-type', '?')}): un 5xx con HTML suele ser "
              "una ruta que no existe para ese libro, no una caída de SUNAT")
        return
    e = sunat.clasificar_error(cuerpo.get("cod"), mensaje=str(cuerpo.get("msg") or ""),
                               errores=list(cuerpo.get("errors") or []), operacion=operacion)
    marcas = [m for m, v in (("idempotente", e.idempotente), ("reintentable", e.reintentable)) if v]
    print(f"{'':18s} [{e.codigo}] {e.mensaje}{'  (' + ', '.join(marcas) + ')' if marcas else ''}")


def _guardar(nombre: str, respuesta) -> None:
    PRIVADO.mkdir(parents=True, exist_ok=True)
    destino = PRIVADO / f"{nombre}.json"
    try:
        contenido = json.dumps(respuesta.json(), ensure_ascii=False, indent=1) + "\n"
    except ValueError:
        destino = destino.with_suffix(".bin")
        destino.write_bytes(respuesta.content)
    else:
        destino.write_text(contenido, encoding="utf-8")
    print(f"{'':18s} guardado CRUDO en {destino.relative_to(PRIVADO.parents[1])} — lleva datos reales dentro")


def main() -> int:
    p = argparse.ArgumentParser(description="Comprueba el mapa del SIRE contra la API real. Solo lecturas.")
    p.add_argument("--token", default=os.environ.get("SIRE_TOKEN", ""),
                   help="el pase de SUNAT. Mejor por la variable SIRE_TOKEN, para que no quede en el historial")
    p.add_argument("--ruc", default="", help="solo para el nombre del archivo que se guarda; no viaja en la petición")
    p.add_argument("--registro", default="compra", choices=("compra", "venta"))
    p.add_argument("--periodo", default="", help="AAAAMM; lo exigen las operaciones que miran un mes")
    p.add_argument("--operacion", default="", help="una sola, en vez de las tres de lectura sin riesgo")
    p.add_argument("--guardar", action="store_true",
                   help="guarda la respuesta CRUDA en privado/sire/ (bloqueado por .gitignore)")
    args = p.parse_args()
    if not args.token:
        print("Falta el token: --token o la variable SIRE_TOKEN. Esta herramienta no sabe pedirlo, y no debe: "
              "cambiar una Clave SOL por un pase necesita un almacén de credenciales, que es de la aplicación.")
        return 2
    operaciones = (args.operacion,) if args.operacion else DE_LECTURA
    print(f"\nSIRE · {args.registro}{' · ' + args.periodo if args.periodo else ''} · "
          f"mapa de {len(sunat.OPERACIONES)} operaciones, actualizado al "
          f"{sunat.sire_api()['actualizado_al']}\n")
    fallos = comprobar(args.token, args.registro, args.periodo, operaciones, args.guardar)
    print(f"\n{'Todo respondió.' if not fallos else f'{fallos} no respondió como se esperaba.'}")
    print("Si una ruta cambió, el que manda es el catálogo: se corrige `contaperu/datos/sunat/sire_api.json` con "
          "la fuente del manual nuevo al lado.\n")
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
