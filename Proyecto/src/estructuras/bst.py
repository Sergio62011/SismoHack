from src.estructuras.nodo import Nodo


class ArbolBST:

  def __init__(self):
    self.raiz = None


  # --------------------------------------------------
  # INSERTAR
  # --------------------------------------------------

  # método público de insertar
  def insertar(self, dato):

    nodo = Nodo(dato)

    if self.raiz is None:

      self.raiz = nodo

      # la raíz no tiene padre
      nodo.setPadre(None)

      print(
        "El valor ",
        dato,
        " se ha insertado como raíz del árbol"
      )

    else:

      self._insertar(
        nodo,
        self.raiz
      )


  # método privado de insertar
  def _insertar(self, nodo, raizActual):

    # se valida igualdad
    if raizActual.getValor() == nodo.getValor():

      print(
        "Ya existe un nodo con valor ",
        nodo.getValor()
      )

    else:

      # si es menor se va por la izquierda
      if nodo.getValor() < raizActual.getValor():

        izq = raizActual.getHijoIzquierdo()

        if izq is None:

          raizActual.setHijoIzquierdo(nodo)

          # se establece el padre
          nodo.setPadre(raizActual)

          print(
            nodo.getValor(),
            " se ha insertado como hijo izquierdo de ",
            raizActual.getValor()
          )

        else:

          self._insertar(
            nodo,
            izq
          )


      # si es mayor se va por la derecha
      else:

        der = raizActual.getHijoDerecho()

        if der is None:

          raizActual.setHijoDerecho(nodo)

          # se establece el padre
          nodo.setPadre(raizActual)

          print(
            nodo.getValor(),
            " se ha insertado como hijo derecho de ",
            raizActual.getValor()
          )

        else:

          self._insertar(
            nodo,
            der
          )


  # --------------------------------------------------
  # BUSCAR
  # --------------------------------------------------

  # método público de buscar
  def buscar(self, dato):

    if self.raiz is None:

      print("El árbol está vacío")

      return None

    else:

      return self._buscar(
        dato,
        self.raiz
      )


  # método privado de buscar
  def _buscar(self, dato, raizActual):

    if dato == raizActual.getValor():

      return raizActual


    if dato < raizActual.getValor():

      izq = raizActual.getHijoIzquierdo()

      if izq is None:

        return None

      else:

        return self._buscar(
          dato,
          izq
        )


    else:

      der = raizActual.getHijoDerecho()

      if der is None:

        return None

      else:

        return self._buscar(
          dato,
          der
        )


  # --------------------------------------------------
  # RECORRIDO PREORDEN
  # raíz - izquierda - derecha
  # --------------------------------------------------

  def preorden(self):

    if self.raiz is None:

      print("El árbol está vacío")

    else:

      self._preorden(
        self.raiz
      )


  def _preorden(self, raizActual):

    if raizActual is not None:

      print(
        raizActual.getValor()
      )

      self._preorden(
        raizActual.getHijoIzquierdo()
      )

      self._preorden(
        raizActual.getHijoDerecho()
      )


  # --------------------------------------------------
  # RECORRIDO INORDEN
  # izquierda - raíz - derecha
  # --------------------------------------------------

  def inorden(self):

    if self.raiz is None:

      print("El árbol está vacío")

    else:

      self._inorden(
        self.raiz
      )


  def _inorden(self, raizActual):

    if raizActual is not None:

      self._inorden(
        raizActual.getHijoIzquierdo()
      )

      print(
        raizActual.getValor()
      )

      self._inorden(
        raizActual.getHijoDerecho()
      )


  # --------------------------------------------------
  # RECORRIDO POSORDEN
  # izquierda - derecha - raíz
  # --------------------------------------------------

  def posorden(self):

    if self.raiz is None:

      print("El árbol está vacío")

    else:

      self._posorden(
        self.raiz
      )


  def _posorden(self, raizActual):

    if raizActual is not None:

      self._posorden(
        raizActual.getHijoIzquierdo()
      )

      self._posorden(
        raizActual.getHijoDerecho()
      )

      print(
        raizActual.getValor()
      )


  # --------------------------------------------------
  # ELIMINAR
  # --------------------------------------------------

  # método público de eliminar
  def eliminar(self, dato):

    if self.raiz is None:

      print("El árbol está vacío")

    else:

      nodo = self.buscar(dato)

      if nodo is None:

        print(
          "No existe un nodo con valor ",
          dato
        )

      else:

        self._eliminar(
          nodo
        )

        print(
          "Se eliminó el nodo ",
          dato
        )


  # método privado de eliminar
  def _eliminar(self, nodo):

    # ------------------------------------------------
    # CASO 1
    # el nodo es una hoja
    # ------------------------------------------------

    if (
      nodo.getHijoIzquierdo() is None
      and
      nodo.getHijoDerecho() is None
    ):

      padre = nodo.getPadre()

      # si el nodo es la raíz
      if padre is None:

        self.raiz = None

      else:

        # se determina si es hijo izquierdo
        if padre.getHijoIzquierdo() == nodo:

          padre.setHijoIzquierdo(None)

        # de lo contrario es hijo derecho
        else:

          padre.setHijoDerecho(None)

      nodo.setPadre(None)

      return


    # ------------------------------------------------
    # CASO 2
    # solamente tiene hijo derecho
    # ------------------------------------------------

    if nodo.getHijoIzquierdo() is None:

      hijo = nodo.getHijoDerecho()
      padre = nodo.getPadre()

      # si el nodo es la raíz
      if padre is None:

        self.raiz = hijo

        hijo.setPadre(None)

      else:

        # si el nodo es hijo izquierdo
        if padre.getHijoIzquierdo() == nodo:

          padre.setHijoIzquierdo(hijo)

        else:

          padre.setHijoDerecho(hijo)

        # el hijo ahora apunta al padre del nodo eliminado
        hijo.setPadre(padre)

      nodo.setPadre(None)
      nodo.setHijoDerecho(None)

      return


    # ------------------------------------------------
    # CASO 2
    # solamente tiene hijo izquierdo
    # ------------------------------------------------

    if nodo.getHijoDerecho() is None:

      hijo = nodo.getHijoIzquierdo()
      padre = nodo.getPadre()

      # si el nodo es la raíz
      if padre is None:

        self.raiz = hijo

        hijo.setPadre(None)

      else:

        # si el nodo es hijo izquierdo
        if padre.getHijoIzquierdo() == nodo:

          padre.setHijoIzquierdo(hijo)

        else:

          padre.setHijoDerecho(hijo)

        # el hijo ahora apunta al padre del nodo eliminado
        hijo.setPadre(padre)

      nodo.setPadre(None)
      nodo.setHijoIzquierdo(None)

      return


    # ------------------------------------------------
    # CASO 3
    # el nodo tiene dos hijos
    #
    # se utiliza el PREDECESOR
    # ------------------------------------------------

    predecesor = self._getPredecesor(
      nodo
    )

    # se copia el valor del predecesor
    # en el nodo que se desea eliminar
    nodo.setValor(
      predecesor.getValor()
    )

    # se elimina físicamente el predecesor
    self._eliminar(
      predecesor
    )


  # --------------------------------------------------
  # OBTENER PREDECESOR
  #
  # retorna el mayor nodo del subárbol izquierdo
  # --------------------------------------------------

  def _getPredecesor(self, nodo):

    actual = nodo.getHijoIzquierdo()

    while actual.getHijoDerecho() is not None:

      actual = actual.getHijoDerecho()

    return actual


  # --------------------------------------------------
  # DIBUJAR
  # --------------------------------------------------

  def dibujar(self):

    if self.raiz is None:

      print("El árbol está vacío")

    else:

      print("\nÁrbol BST:")
      print("-----------")

      self._dibujar(
        self.raiz,
        "",
        "R"
      )


  # método para dibujar conceptualmente el árbol binario
  def _dibujar(self, raizActual, espacio, posicion):

    if raizActual is not None:

      self._dibujar(
        raizActual.getHijoDerecho(),
        espacio + "     ",
        "D"
      )

      print(
        espacio +
        posicion + "── " +
        str(raizActual.getValor())
      )

      self._dibujar(
        raizActual.getHijoIzquierdo(),
        espacio + "     ",
        "I"
      )