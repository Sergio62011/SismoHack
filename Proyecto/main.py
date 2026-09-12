from src.estructuras.avl import AVL
from src.modelo.evento import Evento


def mostrar_eventos(titulo, eventos):
    print(titulo)
    for evento in eventos:
        print(f"  K={evento.clave()} -> Evento {evento.id_evento}")


def main():
    arbol = AVL()

    eventos = [
        Evento(10, 5.2, 20.0, 120.0, 300.0, "2026-09-07T10:00:00Z", 1, "P3", "pendiente"),
        Evento(20, 4.8, 35.0, 200.0, 250.0, "2026-09-07T10:05:00Z", 1, "P2", "pendiente"),
        Evento(5, 5.2, 50.0, 180.0, 330.0, "2026-09-07T10:10:00Z", 1, "P3", "pendiente"),
        Evento(30, 6.1, 15.0, 210.0, 310.0, "2026-09-07T10:15:00Z", 1, "P3", "pendiente"),
        Evento(15, 3.9, 80.0, 400.0, 500.0, "2026-09-07T10:20:00Z", 1, "P1", "pendiente"),
    ]

    for evento in eventos:
        arbol.insertar(evento)

    mostrar_eventos("Recorrido inorder ascendente:", arbol.inorder())
    mostrar_eventos("Recorrido preorder:", arbol.preorder())
    mostrar_eventos("Recorrido postorder:", arbol.postorder())

    print(f"Altura del arbol: {arbol.altura()}")
    print(f"Factor de balance de la raiz: {arbol.factor_balance()}")
    print(f"Cantidad de hojas: {arbol.cantidad_hojas()}")

    evento_buscado = eventos[2]
    encontrado = arbol.buscar(evento_buscado)
    print(f"Busqueda de K={evento_buscado.clave()}: {encontrado}")

    claves_ordenadas = [evento.clave() for evento in arbol.inorder()]
    print(f"El inorder mantiene orden BST: {claves_ordenadas == sorted(claves_ordenadas)}")


if __name__ == "__main__":
    main()
