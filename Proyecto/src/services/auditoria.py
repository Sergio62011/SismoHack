from collections import deque

from services.asociaciones import _eventos_validos


def _claves_ordenadas(raiz):
    resultado = []

    def recorrer(node):
        if node is None:
            return
        recorrer(node.left)
        resultado.append((node.event.calcular_clave(), node.event.id_evento))
        recorrer(node.right)

    recorrer(raiz)
    return resultado


def _alturas_recalculadas(raiz):

    def recorrer(node):
        if node is None:
            return -1, {}
        altura_izq, metadatos_izq = recorrer(node.left)
        altura_der, metadatos_der = recorrer(node.right)
        altura = 1 + max(altura_izq, altura_der)
        factor = altura_izq - altura_der
        metadatos = {}
        metadatos.update(metadatos_izq)
        metadatos.update(metadatos_der)
        metadatos[node.event.id_evento] = (altura, factor)
        return altura, metadatos

    _, metadatos = recorrer(raiz)
    return metadatos


def verificar_estructura(sistema):
    errores = []

    # === 1. Orden global BST ===
    claves = _claves_ordenadas(sistema.avl.root)
    for i in range(1, len(claves)):
        if claves[i][0] <= claves[i - 1][0]:
            errores.append(
                f"Orden BST roto: clave {claves[i][0]} "
                f"(evento {claves[i][1]}) no es mayor que "
                f"clave {claves[i - 1][0]} (evento {claves[i - 1][1]})"
            )

    # === 2. Unicidad de identificadores ===
    ids_activos = set(sistema._eventos_activos.keys())
    ids_historicos = set(sistema._historicos.keys())
    ids_eliminados = set(sistema.ids_eliminados)

    repetidos_activos = set()
    if len(ids_activos) != len(sistema._eventos_activos):
        repetidos_activos = {"(claves duplicadas en diccionario)"}

    duplicados_entre = (
        (ids_activos & ids_historicos)
        | (ids_activos & ids_eliminados)
        | (ids_historicos & ids_eliminados)
    )
    if duplicados_entre:
        errores.append(
            f"Identificadores en más de un estado: "
            f"{sorted(duplicados_entre)}"
        )

    # === 3. Correspondencia AVL ↔ diccionario de activos ===
    ids_en_arbol = {clave[1] for clave in claves}
    if ids_en_arbol != ids_activos:
        faltan_en_arbol = ids_activos - ids_en_arbol
        sobran_en_arbol = ids_en_arbol - ids_activos
        if faltan_en_arbol:
            errores.append(
                f"Eventos activos fuera del AVL: {sorted(faltan_en_arbol)}"
            )
        if sobran_en_arbol:
            errores.append(
                f"Nodos en el AVL sin evento activo: {sorted(sobran_en_arbol)}"
            )

    # === 4. Clave del evento coincide con la posición ===
    for clave, event_id in claves:
        evento = sistema._eventos_activos.get(event_id)
        if evento is None:
            continue
        if evento.calcular_clave() != clave:
            errores.append(
                f"Clave inconsistente en evento {event_id}: "
                f"nodo={clave}, calculada={evento.calcular_clave()}"
            )

    # === 5. Alturas y factores ===
    metadatos = _alturas_recalculadas(sistema.avl.root)

    def revisar_metadatos(node, profundidad):
        if node is None:
            return
        event_id = node.event.id_evento
        altura_esperada, factor_esperado = metadatos.get(event_id, (-1, 0))
        if node.height != altura_esperada:
            errores.append(
                f"Altura incorrecta en evento {event_id}: "
                f"almacenada={node.height}, esperada={altura_esperada}"
            )
        if node.balance_factor != factor_esperado:
            errores.append(
                f"Factor incorrecto en evento {event_id}: "
                f"almacenado={node.balance_factor}, "
                f"esperado={factor_esperado}"
            )
        if not sistema.avl.modo_estres and abs(factor_esperado) > 1:
            errores.append(
                f"Desbalance inesperado en modo normal: "
                f"evento {event_id}, factor={factor_esperado}"
            )
        revisar_metadatos(node.left, profundidad + 1)
        revisar_metadatos(node.right, profundidad + 1)

    revisar_metadatos(sistema.avl.root, 0)

    # === 6. Asociaciones ===
    todos = {**sistema._eventos_activos, **sistema._historicos}
    for event_id, evento in todos.items():
        if evento.referencia is not None:
            if evento.referencia == event_id:
                errores.append(
                    f"Evento {event_id} se referencia a sí mismo"
                )
            elif evento.referencia in sistema.ids_eliminados:
                errores.append(
                    f"Evento {event_id} referencia al eliminado "
                    f"{evento.referencia}"
                )
            elif evento.referencia not in todos:
                errores.append(
                    f"Evento {event_id} referencia a un evento inexistente "
                    f"{evento.referencia}"
                )
            else:
                referencia = todos[evento.referencia]
                if event_id not in referencia.referenciado_por:
                    errores.append(
                        f"Referencia no recíproca: {event_id} -> "
                        f"{evento.referencia}"
                    )
        for referenciado in evento.referenciado_por:
            if referenciado in sistema.ids_eliminados:
                errores.append(
                    f"Evento {event_id} es referenciado por el eliminado "
                    f"{referenciado}"
                )
            elif referenciado not in todos:
                errores.append(
                    f"Evento {event_id} referenciado por inexistente "
                    f"{referenciado}"
                )
            else:
                otro = todos[referenciado]
                if otro.referencia != event_id:
                    errores.append(
                        f"Asociación no recíproca: {referenciado} -> "
                        f"{event_id}"
                    )

    # === 7. Marcas de acceso costoso ===
    def revisar_acceso(node, profundidad):
        if node is None:
            return
        esperado = (
            node.event.prioridad == 3
            and profundidad > sistema.parametros.l
        )
        if node.event.acceso_costoso != esperado:
            errores.append(
                f"Marca de acceso costoso inconsistente en evento "
                f"{node.event.id_evento}: almacenada="
                f"{node.event.acceso_costoso}, esperada={esperado} "
                f"(profundidad={profundidad}, L={sistema.parametros.l})"
            )
        revisar_acceso(node.left, profundidad + 1)
        revisar_acceso(node.right, profundidad + 1)

    revisar_acceso(sistema.avl.root, 0)

    # === Indicadores ===
    por_prioridad = {1: 0, 2: 0, 3: 0}
    pendientes = 0
    for evento in sistema._eventos_activos.values():
        por_prioridad[evento.prioridad] = (
            por_prioridad.get(evento.prioridad, 0) + 1
        )
        if evento.estado == "pendiente":
            pendientes += 1

    con_acceso_costoso = sum(
        1
        for evento in sistema._eventos_activos.values()
        if evento.acceso_costoso
    )

    indicadores = {
        "activos": len(sistema._eventos_activos),
        "historicos": len(sistema._historicos),
        "eliminados": len(sistema.ids_eliminados),
        "altura": sistema.avl.height(),
        "hojas": sistema.avl.number_of_leaves(),
        "nodos_por_nivel": sistema.avl.nodes_per_level(),
        "inorden": [e.id_evento for e in sistema.avl.in_order()],
        "preorden": [e.id_evento for e in sistema.avl.pre_order()],
        "postorden": [e.id_evento for e in sistema.avl.post_order()],
        "por_niveles": [e.id_evento for e in sistema.avl.breadth_first()],
        "correcciones_aceptadas": sistema.metricas["correcciones_aceptadas"],
        "reportes_descartados": sistema.metricas["reportes_descartados"],
        "conflictos": sistema.metricas["conflictos"],
        "confirmaciones": sistema.metricas["confirmaciones"],
        "creados_por_reporte": sistema.metricas["creados_por_reporte"],
        "reactivados": sistema.metricas["reactivados"],
        "archivos_masivos": sistema.metricas["archivos_masivos"],
        "eventos_archivados": sistema.metricas["eventos_archivados"],
        "casos_ll": sistema.avl.casos_ll,
        "casos_rr": sistema.avl.casos_rr,
        "casos_lr": sistema.avl.casos_lr,
        "casos_rl": sistema.avl.casos_rl,
        "giros_simples_izquierda": sistema.avl.giros_simples_izquierda,
        "giros_simples_derecha": sistema.avl.giros_simples_derecha,
        "rotaciones_realizadas": sistema.avl.rotaciones_realizadas,
        "por_prioridad": por_prioridad,
        "pendientes": pendientes,
        "con_acceso_costoso": con_acceso_costoso,
        "modo_estres": sistema.avl.modo_estres,
    }

    return {
        "ok": len(errores) == 0,
        "errores": errores,
        "indicadores": indicadores,
    }