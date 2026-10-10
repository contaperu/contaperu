"""La regla 6, que hasta la 9.0.1 no vigilaba nadie: **nunca datos reales en el repositorio**.

Es la primera de las siete que no se negocian y la única que no tenía test. Lo que pasó es exactamente lo que pasa
cuando una regla depende de que nos acordemos: la 8.2 escribió la forma de la tesorería con un extracto real
delante y se trajo el **CCI, el número de cuenta y el saldo** de una cuenta de verdad, más dos movimientos con sus
importes y la razón social de la empresa. Estuvo publicado en un repositorio público y en el sdist de PyPI, y lo
encontró una persona buscando un ejemplo, no la batería.

**Lo que se puede comprobar a máquina son las dos coordenadas que identifican a alguien**, y por eso este fichero
vigila dos cosas y no «datos reales» en abstracto:

- **El CCI**, y es el más grave: un Código de Cuenta Interbancario con su número de cuenta es la coordenada para
  mandarle dinero a alguien. Tolerancia cero — cualquier cadena de 20 dígitos que no sea una de las declaradas
  seguras cae, y también la forma con espacios o guiones con la que cada banco lo imprime.
- **El RUC**, con una regla más fina, porque un RUC de contraparte **el motor lo valida** y por tanto la batería
  necesita unos con el dígito verificador correcto. La convención que ya usaba todo el resto es que un RUC
  inventado se delata a la vista con una corrida de dígitos repetidos (`20655555553`, `20633333336`). Así que un
  RUC con dígito válido tiene que ser uno de los cuatro declarados o llevar su corrida. De los diecinueve que
  había, diecisiete la llevaban y **dos no**: se reemplazaron en la 9.0.1 sin averiguar de quién eran, porque la
  regla no admite el beneficio de la duda.

Lo que este test **no** puede hacer, dicho para que nadie lo suponga: no sabe si un importe o una glosa son reales.
Eso solo lo sabe quien escribe el test, y para eso está la regla escrita. Lo que sí hace es cerrar la puerta por la
que se colaron los datos que se colaron.
"""
from __future__ import annotations

import pathlib
import re

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[1]

# Los cuatro de `CLAUDE.md` §«Lo que no se negocia», regla 6. `20601234567` es seguro justamente por tener el
# dígito verificador mal a propósito: no puede ser de ninguna empresa. Los otros tres sí lo tienen bien, porque el
# motor valida la contraparte y un RUC inválido daría `RUC_INVALIDO` en vez de probar lo que el test quiere probar.
RUCS_SEGUROS = ("20131312955", "20601234567", "20602222226", "20607777773")

# Los de `tests/test_tesoreria.py`: código de entidad real —norma publicada— y el resto inventado.
CCIS_SEGUROS = ("01199900000000000100", "00999900000000000200")

# Donde se busca. Solo texto, y nunca `privado/` —que es donde un archivo real SÍ puede vivir, de lectura y en
# local— ni el entorno virtual.
EXTENSIONES = ("*.py", "*.md", "*.json", "*.txt", "*.csv", "*.toml", "*.yml", "*.yaml")
FUERA = ("privado", ".venv", ".git", "__pycache__", "node_modules")

# Un RUC: 11 dígitos con uno de los cuatro prefijos que SUNAT asigna (10 y 15 persona natural, 17, 20 jurídica).
RUC = re.compile(r"(?<!\d)(?:10|15|17|20)\d{9}(?!\d)")
# Un CCI: 20 dígitos seguidos, o los cuatro grupos 3+3+12+2 como los imprime un banco.
CCI_SEGUIDO = re.compile(r"(?<!\d)\d{20}(?!\d)")
CCI_EN_GRUPOS = re.compile(r"(?<!\d)\d{3}[ -]\d{3}[ -]\d{12}[ -]\d{2}(?!\d)")
# La marca de que un número se inventó: cinco dígitos iguales seguidos.
CORRIDA = re.compile(r"(\d)\1{4,}")

PESOS = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)


def digito_verificador(ruc: str) -> int:
    """El dígito que le toca a los diez primeros, por el algoritmo de SUNAT.

    Está aquí y no en el paquete a propósito: el motor **no valida el RUC del contribuyente** —el del libro—, y
    para la contraparte usa su propia comprobación. Una segunda copia en el núcleo sería una regla duplicada."""
    resto = 11 - (sum(int(d) * p for d, p in zip(ruc[:10], PESOS)) % 11)
    return {10: 0, 11: 1}.get(resto, resto)


def es_ruc_posible(ruc: str) -> bool:
    """¿Este número podría ser el RUC de alguien? Lo es si su dígito verificador cuadra."""
    return int(ruc[10]) == digito_verificador(ruc)


def ficheros_de_texto() -> list[pathlib.Path]:
    """Todo el texto del repositorio menos `privado/` y lo que no es nuestro."""
    hallados = []
    for patron in EXTENSIONES:
        for f in RAIZ.rglob(patron):
            if not set(f.relative_to(RAIZ).parts) & set(FUERA):
                hallados.append(f)
    return sorted(set(hallados))


@pytest.fixture(scope="module")
def textos() -> list[tuple[str, str]]:
    return [(str(f.relative_to(RAIZ)).replace("\\", "/"), f.read_text("utf-8", errors="replace"))
            for f in ficheros_de_texto()]


def test_ningun_cci_que_no_sea_de_los_declarados(textos):
    """Tolerancia cero, y es el que cazaría lo que pasó: un CCI con su cuenta es la coordenada para mandarle dinero
    a alguien. Se miran las dos formas, porque BBVA lo imprime con espacios y Scotiabank con guiones."""
    colados = []
    for ruta, texto in textos:
        for patron in (CCI_SEGUIDO, CCI_EN_GRUPOS):
            for m in patron.finditer(texto):
                solo_digitos = re.sub(r"[^0-9]", "", m.group(0))
                if solo_digitos not in CCIS_SEGUROS:
                    colados.append(f"{ruta}: {m.group(0)}")
    assert not colados, (
        "hay cadenas con forma de CCI que no son las declaradas seguras:\n  " + "\n  ".join(sorted(set(colados))) +
        f"\n\nLos seguros son {', '.join(CCIS_SEGUROS)}. Si hace falta otro, se inventa con oficina `999` y una "
        "cuenta que no pueda ser de nadie, y se declara en CCIS_SEGUROS con su motivo.")


def test_ningun_ruc_que_pueda_ser_de_alguien(textos):
    """Un RUC con el dígito verificador correcto o es uno de los cuatro declarados, o lleva su corrida de dígitos
    repetidos que lo delata como inventado. Lo demás podría ser de una empresa de verdad.

    Un RUC con el dígito MAL no se mira: por definición no es de nadie, que es lo que hace seguro al `20601234567`.
    """
    colados = []
    for ruta, texto in textos:
        for m in RUC.finditer(texto):
            ruc = m.group(0)
            if ruc in RUCS_SEGUROS or not es_ruc_posible(ruc) or CORRIDA.search(ruc):
                continue
            colados.append(f"{ruta}: {ruc}")
    assert not colados, (
        "hay RUC con dígito verificador válido que podrían ser de una empresa real:\n  " +
        "\n  ".join(sorted(set(colados))) +
        "\n\nO es uno de los cuatro de la regla 6, o se inventa con una corrida de dígitos repetidos "
        "(`20655555553`) y el dígito calculado. No se averigua de quién es: se reemplaza.")


def test_el_guardian_muerde():
    """La mutación del propio guardián, porque un test de datos que no se prueba a sí mismo no vale nada.

    Se comprueba con valores que NO están en el repositorio: un CCI con forma válida y un RUC con dígito correcto
    sin corrida. Si alguna de las dos reglas se relajara, esto se pone verde cuando no debe.

    **Los valores se componen aquí y no se escriben enteros**, porque este fichero también se barre a sí mismo y
    un literal con forma de CCI lo pondría rojo. Que eso pasara al escribirlo es la mejor señal de que muerde."""
    grupos = ("011", "307", "000100028" + "000", "69")
    assert re.sub(r"[^0-9]", "", " ".join(grupos)) not in CCIS_SEGUROS
    assert CCI_EN_GRUPOS.fullmatch(" ".join(grupos))
    assert CCI_SEGUIDO.fullmatch("".join(grupos))
    # Un RUC construido ahora mismo con su dígito correcto y sin corrida: el guardián lo tiene que considerar
    # posible, que es lo que lo hace caer.
    inventado = "20512333790"[:10] + str(digito_verificador("20512333790"))
    assert es_ruc_posible(inventado) and not CORRIDA.search(inventado)
    assert inventado not in RUCS_SEGUROS
    # Y al revés: el seguro por excelencia tiene el dígito mal, y por eso nunca cae.
    assert not es_ruc_posible("20601234567")
