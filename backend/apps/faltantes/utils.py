"""
Normalización de nombres de productos faltantes para agruparlos en reportes.

Reglas (documentadas para la sustentación):
1. Minúsculas.
2. Solo letras, números y espacios; los espacios repetidos se reducen a uno.
3. Plural simple, palabra por palabra, solo en palabras de 5 letras o más:
   - termina en vocal tildada + "s" (compás, autobús) → no se cambia
   - termina en "ces"                         → "z"      (lápices → lápiz)
   - termina en "es" tras consonante (no "s") → sin "es" (colores → color, papeles → papel)
   - termina en "s"                           → sin "s"  (cuadernos → cuaderno, tijeras → tijera)
4. Sin tildes ni diéresis (á→a, ü→u). La ñ se conserva.

Ejemplos: "Lápices  de Colores" → "lapiz de color";  "CUADERNOS rayados" → "cuaderno rayado".
Limitación conocida: es una regla sencilla, no un singularizador completo del español.
"""
import re
import unicodedata

VOCALES = set("aeiouáéíóú")
LONGITUD_MINIMA = 5


def quitar_tildes(texto):
    resultado = []
    for caracter in unicodedata.normalize("NFD", texto):
        # Conserva la virgulilla de la ñ (n + U+0303); elimina las demás marcas.
        if unicodedata.category(caracter) == "Mn":
            if caracter == "̃" and resultado and resultado[-1] == "n":
                resultado.append(caracter)
            continue
        resultado.append(caracter)
    return unicodedata.normalize("NFC", "".join(resultado))


def singularizar(palabra):
    if len(palabra) < LONGITUD_MINIMA:
        return palabra
    if re.search(r"[áéíóú]s$", palabra):
        return palabra
    if palabra.endswith("ces"):
        return palabra[:-3] + "z"
    if palabra.endswith("es") and palabra[-3] not in VOCALES and palabra[-3] != "s":
        return palabra[:-2]
    if palabra.endswith("s") and not palabra.endswith("ss"):
        return palabra[:-1]
    return palabra


def normalizar_nombre(texto):
    texto = unicodedata.normalize("NFC", (texto or "").lower())
    texto = re.sub(r"[\W_]+", " ", texto)
    palabras = [singularizar(palabra) for palabra in texto.split()]
    return quitar_tildes(" ".join(palabras))
