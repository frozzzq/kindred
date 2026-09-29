from src.agente.oraciones import Oracionador


def _partir(fragmentos):
    salida = []
    oracionador = Oracionador(salida.append)
    for fragmento in fragmentos:
        oracionador.agregar(fragmento)
    oracionador.terminar()
    return salida


def test_la_primera_oracion_sale_en_cuanto_esta_completa():
    salida = []
    oracionador = Oracionador(salida.append)

    oracionador.agregar("¡Eso! Ya ")

    assert salida == ["¡Eso!"]


def test_las_siguientes_se_juntan_hasta_un_minimo_para_no_sonar_entrecortado():
    salida = _partir(["Hola. ", "Sí. ", "No. ", "Esta es una oración bastante más larga que las otras. ", "Fin."])

    assert salida[0] == "Hola."
    assert salida[1].startswith("Sí. No. Esta es una oración")
    assert salida[-1] == "Fin."


def test_no_corta_decimales_ni_pierde_texto():
    salida = _partir(["Pesa 3.", "5 kilos. ", "Y cuesta 20 pesos"])

    assert " ".join(salida) == "Pesa 3.5 kilos. Y cuesta 20 pesos"
