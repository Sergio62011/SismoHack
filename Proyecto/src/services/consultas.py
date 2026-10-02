def primeros_k_pendientes(sistema, k):
    if isinstance(k, bool) or not isinstance(k, int) or k <= 0:
        raise ValueError("k debe ser un entero positivo")

    eventos = []
    nodos_examinados = 0

    def recorrer(node):
        nonlocal nodos_examinados

        if node is None or len(eventos) >= k:
            return

        recorrer(node.right)

        if len(eventos) >= k:
            return

        nodos_examinados += 1

        if node.event.estado == "pendiente":
            eventos.append(node.event)

        recorrer(node.left)

    recorrer(sistema.avl.root)

    return {
        "eventos": eventos,
        "nodos_examinados": nodos_examinados,
    }


def eventos_por_magnitud(sistema, magnitud_min, magnitud_max):
    if magnitud_min > magnitud_max:
        raise ValueError(
            "La magnitud mínima no puede ser mayor que la máxima"
        )

    eventos = []
    nodos_examinados = 0

    def recorrer(node):
        nonlocal nodos_examinados

        if node is None:
            return

        recorrer(node.left)

        nodos_examinados += 1

        evento = node.event

        if magnitud_min <= evento.magnitud <= magnitud_max:
            eventos.append(evento)

        recorrer(node.right)

    recorrer(sistema.avl.root)

    return {
        "eventos": eventos,
        "nodos_examinados": nodos_examinados,
    }


def eventos_por_profundidad_y_fecha(
    sistema,
    profundidad_max,
    fecha_inicio,
    fecha_fin
):
    if fecha_inicio > fecha_fin:
        raise ValueError(
            "La fecha inicial no puede ser posterior a la final"
        )

    eventos = []
    nodos_examinados = 0

    def recorrer(node):
        nonlocal nodos_examinados

        if node is None:
            return

        recorrer(node.left)

        nodos_examinados += 1

        evento = node.event

        if (
            evento.profundidad <= profundidad_max
            and fecha_inicio <= evento.fecha_hora <= fecha_fin
        ):
            eventos.append(evento)

        recorrer(node.right)

    recorrer(sistema.avl.root)

    return {
        "eventos": eventos,
        "nodos_examinados": nodos_examinados,
    }


def asociaciones_de_evento(sistema, id_evento):
    event_id = sistema._validar_id(id_evento)

    if event_id in sistema._eventos_activos:
        evento = sistema._eventos_activos[event_id]
        estado = "activo"

    elif event_id in sistema._historicos:
        evento = sistema._historicos[event_id]
        estado = "archivado"

    else:
        if event_id in sistema.ids_eliminados:
            raise ValueError(
                f"El evento {event_id} fue eliminado"
            )

        raise ValueError(
            f"No existe el evento {event_id}"
        )

    from services.asociaciones import obtener_candidatos

    candidatos = []

    for candidato in obtener_candidatos(sistema, evento):
        if candidato.id_evento in sistema._eventos_activos:
            candidato_estado = "activo"
        else:
            candidato_estado = "archivado"

        candidatos.append({
            "evento": candidato,
            "estado": candidato_estado,
        })

    referencia = None

    if evento.referencia is not None:
        referencia = (
            sistema._eventos_activos.get(evento.referencia)
            or sistema._historicos.get(evento.referencia)
        )

    referenciados_por = []

    for id_referenciado in sorted(evento.referenciado_por):
        otro = (
            sistema._eventos_activos.get(id_referenciado)
            or sistema._historicos.get(id_referenciado)
        )

        if otro is None:
            continue

        if id_referenciado in sistema._eventos_activos:
            otro_estado = "activo"
        else:
            otro_estado = "archivado"

        referenciados_por.append({
            "evento": otro,
            "estado": otro_estado,
        })

    return {
        "evento": evento,
        "estado": estado,
        "candidatos": candidatos,
        "referencia": referencia,
        "referenciados_por": referenciados_por,
        "nodos_examinados": 0,
    }


def metricas_avl(sistema):
    return {
        "cantidad": sistema.avl.size(),
        "altura": sistema.avl.height(),
        "hojas": sistema.avl.number_of_leaves(),
        "nodos_por_nivel": sistema.avl.nodes_per_level(),
    }