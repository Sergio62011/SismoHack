from services.historial import Accion

def _es_elegible(evento, sistema):
    if evento.prioridad != 1:
        return False

    antiguedad = sistema.reloj.antiguedad_horas(
        evento.fecha_hora
    )

    return antiguedad > sistema.parametros.T


def _buscar_ramas_elegibles(node, sistema, profundidad=0):
    if node is None:
        return [], True, 0

    ramas_izquierda, izquierda_valida, cantidad_izquierda = (
        _buscar_ramas_elegibles(
            node.left,
            sistema,
            profundidad + 1
        )
    )

    ramas_derecha, derecha_valida, cantidad_derecha = (
        _buscar_ramas_elegibles(
            node.right,
            sistema,
            profundidad + 1
        )
    )

    nodo_valido = _es_elegible(node.evento, sistema)

    cantidad = 1 + cantidad_izquierda + cantidad_derecha

    subarbol_valido = (
        nodo_valido
        and izquierda_valida
        and derecha_valida
    )

    ramas = []
    ramas.extend(ramas_izquierda)
    ramas.extend(ramas_derecha)

    if subarbol_valido:
        ramas.append({
            "raiz": node.evento,
            "profundidad": profundidad,
            "cantidad": cantidad,
        })

    return ramas, subarbol_valido, cantidad


def _seleccionar_rama(ramas):
    if not ramas:
        return None

    return max(
        ramas,
        key=lambda rama: (
            rama["cantidad"],
            rama["profundidad"],
            rama["raiz"].id_evento,
        )
    )


def previsualizar_archivo(sistema):
    ramas, _, _ = _buscar_ramas_elegibles(
        sistema.avl.root,
        sistema
    )

    rama = _seleccionar_rama(ramas)

    if rama is None:
        return {
            "elegible": False,
            "raiz": None,
            "profundidad": None,
            "cantidad": 0,
            "ids": [],
            "eventos": [],
            "mensaje": "No existe una rama elegible para archivar.",
        }

    ids = []
    eventos = []

    def recoger(node):
        if node is None:
            return

        if node.evento.id_evento in ids:
            return

        ids.append(node.evento.id_evento)
        eventos.append(node.evento)

        recoger(node.left)
        recoger(node.right)

    # Necesitamos localizar la raíz seleccionada.
    def buscar(node):
        if node is None:
            return None

        if node.evento.id_evento == rama["raiz"].id_evento:
            return node

        resultado = buscar(node.left)

        if resultado is not None:
            return resultado

        return buscar(node.right)

    raiz = buscar(sistema.avl.root)
    recoger(raiz)

    return {
        "elegible": True,
        "raiz": rama["raiz"],
        "profundidad": rama["profundidad"],
        "cantidad": rama["cantidad"],
        "ids": ids,
        "eventos": eventos,
        "mensaje": (
            "Rama elegible seleccionada por cantidad de nodos, "
            "profundidad de la raíz e ID de la raíz."
        ),
    }


def archivar_rama(sistema):
    estado_antes = sistema._snapshot()

    try:
        ramas, _, _ = _buscar_ramas_elegibles(
            sistema.avl.root,
            sistema
        )

        rama = _seleccionar_rama(ramas)

        if rama is None:
            return {
                "archivado": False,
                "raiz": None,
                "ids": [],
                "cantidad": 0,
                "mensaje": "No existe una rama elegible para archivar.",
            }

        # Se localiza la raíz seleccionada.
        raiz = None

        def buscar(node):
            if node is None:
                return None

            if node.evento.id_evento == rama["raiz"].id_evento:
                return node

            resultado = buscar(node.left)

            if resultado is not None:
                return resultado

            return buscar(node.right)

        raiz = buscar(sistema.avl.root)

        # Se fija el conjunto antes de modificar el AVL.
        eventos = []

        def recoger(node):
            if node is None:
                return

            eventos.append(node.evento)
            recoger(node.left)
            recoger(node.right)

        recoger(raiz)

        ids = [evento.id_evento for evento in eventos]

        # Ahora sí se modifica el escenario.
        for evento in eventos:
            sistema.avl.delete(evento.calcular_clave())

            sistema._eventos_activos.pop(
                evento.id_evento,
                None
            )

            evento.ubicacion = "archivado"

            sistema._historicos[evento.id_evento] = evento

        sistema.metricas["archivos_masivos"] += 1
        sistema.metricas["eventos_archivados"] += len(eventos)
        sistema.actualizar_marcas_acceso_costoso()

        sistema.historial.registro_accion(
            Accion(
                f"archivar_rama {rama['raiz'].id_evento}",
                estado_antes
            )
        )

        return {
            "archivado": True,
            "raiz": rama["raiz"],
            "ids": ids,
            "cantidad": len(eventos),
            "mensaje": (
                f"Se archivó la rama con raíz "
                f"{rama['raiz'].id_evento}."
            ),
        }

    except Exception:
        sistema._restaurar(estado_antes)
        raise