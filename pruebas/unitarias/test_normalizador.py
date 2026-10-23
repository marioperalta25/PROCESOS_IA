"""Pruebas unitarias para el modulo de normalizacion de textos y datos."""

import unittest

from procesos_ia.dominio.evaluaciones import DefinicionResultado
from procesos_ia.dominio.normalizador import (
    limpiar_espacios,
    normalizar_clave_comparacion,
    normalizar_datos_modelo,
    normalizar_texto,
    quitar_acentos,
    reemplazar_enies,
)


class TestNormalizador(unittest.TestCase):
    """Casos de prueba para verificar transformaciones de saneamiento."""

    def test_reemplazo_enies_directas_y_mayusculas(self) -> None:
        self.assertEqual(reemplazar_enies("español"), "espanol")
        self.assertEqual(reemplazar_enies("ESPAÑOL"), "ESPANOL")
        self.assertEqual(reemplazar_enies("villaseñor"), "villasenor")
        self.assertEqual(reemplazar_enies("COMPAÑÍA"), "COMPANÍA")
        self.assertEqual(reemplazar_enies("niño"), "nino")
        self.assertEqual(reemplazar_enies(""), "")

    def test_reemplazo_enies_descompuestas_nfd(self) -> None:
        # Forma descompuesta NFD (n + caracter combinatorio tilde U+0303)
        nfd_enie = "n\u0303"
        nfd_enie_mayus = "N\u0303"
        self.assertEqual(reemplazar_enies(f"espa{nfd_enie}ol"), "espanol")
        self.assertEqual(reemplazar_enies(f"ESPA{nfd_enie_mayus}OL"), "ESPANOL")

    def test_quitar_acentos_conserva_letras_base(self) -> None:
        self.assertEqual(quitar_acentos("Habla Español"), "Habla Espanol")
        self.assertEqual(quitar_acentos("José Olmedo"), "Jose Olmedo")
        self.assertEqual(quitar_acentos("MÁXIMO ÁNGEL ÚRSULA"), "MAXIMO ANGEL URSULA")
        self.assertEqual(quitar_acentos("cigüeña"), "ciguena")
        self.assertEqual(quitar_acentos(""), "")

    def test_limpiar_espacios_redundantes_y_saltos(self) -> None:
        entrada = "  Charlotte   \t  NC \n\r   "
        self.assertEqual(limpiar_espacios(entrada), "Charlotte NC")
        self.assertEqual(limpiar_espacios("    "), "")

    def test_normalizar_texto_completo(self) -> None:
        entrada = "   José   Olmedo   Villaseñor   "
        esperado = "Jose Olmedo Villasenor"
        self.assertEqual(normalizar_texto(entrada), esperado)

    def test_normalizar_datos_modelo_recursivo(self) -> None:
        datos_entrada = {
            "contacto": {
                "owner": "   Esperanza   UrbietA   ",
                "detalles": "Habla español con fluidez",
            },
            "registro": [
                {"ciudad": "Bogotá", "telefono": 123456789},
                "  Compañía Eléctrica  ",
            ],
            "contador": 42,
            "activo": True,
        }
        esperado = {
            "contacto": {
                "owner": "Esperanza UrbietA",
                "detalles": "Habla espanol con fluidez",
            },
            "registro": [
                {"ciudad": "Bogota", "telefono": 123456789},
                "Compania Electrica",
            ],
            "contador": 42,
            "activo": True,
        }
        resultado = normalizar_datos_modelo(datos_entrada)
        self.assertEqual(resultado, esperado)

    def test_normalizar_clave_comparacion(self) -> None:
        self.assertEqual(
            normalizar_clave_comparacion("Habla Español"),
            normalizar_clave_comparacion("habla espanol"),
        )
        self.assertEqual(
            normalizar_clave_comparacion("NOMBRE LATINO"),
            "nombre latino",
        )

    def test_definicion_resultado_acepta_y_canonico_tolerante(self) -> None:
        definicion = DefinicionResultado(
            clave="idioma",
            criterio="Detectar idioma",
            opciones=("Habla Español", "No Definido"),
        )
        # Debe aceptar coincidencia exacta
        self.assertTrue(definicion.acepta("Habla Español"))
        # Debe aceptar coincidencia con variacion de tildes o enie
        self.assertTrue(definicion.acepta("habla espanol"))
        self.assertTrue(definicion.acepta("Habla Espanol"))
        # No debe aceptar opciones ajenas
        self.assertFalse(definicion.acepta("Ingles"))

        # El valor canonico debe mapear a la etiqueta oficial
        self.assertEqual(definicion.valor_canonico("habla espanol"), "Habla Español")
        self.assertEqual(definicion.valor_canonico("Habla Espanol"), "Habla Español")
        self.assertEqual(definicion.valor_canonico("No Definido"), "No Definido")

    def test_formatear_columnas_delimitadas_columna_unica(self) -> None:
        from procesos_ia.dominio.normalizador import formatear_columnas_delimitadas
        valores = {"nombre": "  José Villaseñor  ", "edad": "30"}
        resultado = formatear_columnas_delimitadas(valores, ["nombre"])
        self.assertEqual(resultado, "Jose Villasenor")

    def test_formatear_columnas_delimitadas_multiples_columnas(self) -> None:
        from procesos_ia.dominio.normalizador import formatear_columnas_delimitadas
        valores = {"owner": "  Esperanza  ", "negocio": "Compañía Eléctrica"}
        resultado = formatear_columnas_delimitadas(valores, ["owner", "negocio"])
        self.assertEqual(resultado, "owner: Esperanza | negocio: Compania Electrica")


if __name__ == "__main__":
    unittest.main()
