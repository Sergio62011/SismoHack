from datetime import timedelta
from math import hypot


def _eventos_validos(sistema):
    eventos = {}

    for evento in sistema._eventos_activos.values():
        eventos[evento.id_evento] = evento

    for evento in sistema._historicos.values():
        if evento.id_evento not in sistema.ids_eliminados:
            eventos[evento.id_evento] = evento

    return list(eventos.values())


def _distancia(evento_a, evento_b):
    return hypot(
        evento_a.x - evento_b.x,
        evento_a.y - evento_b.y
    )


def es_candidato(evento_a, evento_b, w_horas, r_km):
    if evento_a.id_evento == evento_b.id_evento:
        return False

    # A debe tener mayor magnitud que B
    if evento_a.magnitud <= evento_b.magnitud:
        return False

    # A debe haber ocurrido estrictamente antes que B
    if evento_a.fecha_hora >= evento_b.fecha_hora:
        return False

    diferencia = evento_b.fecha_hora - evento_a.fecha_hora

    if diferencia > timedelta(hours=w_horas):
        return False

    if _distancia(evento_a, evento_b) > r_km:
        return False

    return True


def obtener_candidatos(sistema, evento):
    w_horas = sistema.parametros.w
    r_km = sistema.parametros.r

    candidatos = []

    for candidato in _eventos_validos(sistema):
        if candidato.id_evento == evento.id_evento:
            continue

        if es_candidato(candidato, evento, w_horas, r_km):
            candidatos.append(candidato)

    return candidatos


def elegir_referencia(evento, candidatos):
    if not candidatos:
        return None

    def criterio(candidato):
        diferencia = (
            evento.fecha_hora - candidato.fecha_hora
        ).total_seconds()

        distancia = _distancia(candidato, evento)

        return (
            diferencia,
            distancia,
            -candidato.magnitud,
            candidato.id_evento
        )

    return min(candidatos, key=criterio)


def recalcular_todas(sistema):
    eventos = _eventos_validos(sistema)
    print(eventos)

    # Primero se limpian las relaciones anteriores.
    for evento in eventos:
        evento.referencia = None
        evento.referenciado_por.clear()

    # Luego se calculan nuevamente.
    for evento in eventos:
        candidatos = obtener_candidatos(sistema, evento)
        print("============================================================================")
        referencia = elegir_referencia(evento, candidatos)
        print(referencia)

        if referencia is not None:
            evento.referencia = referencia.id_evento
            referencia.referenciado_por.add(evento.id_evento)
        print(evento)
        print(referencia)


def actualizar_asociaciones_de(sistema, id_evento=None):
    recalcular_todas(sistema)