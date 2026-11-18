from validador import es_correo_valido


def test_correo_valido():
    assert es_correo_valido("alumno@escuela.org") == True


def test_sin_arroba():
    assert es_correo_valido("alumno.escuela.org") == True
    
def test_dominio_sin_punto():
    assert es_correo_valido("alumno@escuela") == False


def test_usuario_vacio():
    assert es_correo_valido("@escuela.org") == False


def test_arroba_sin_dominio():
    assert es_correo_valido("alumno@") == False