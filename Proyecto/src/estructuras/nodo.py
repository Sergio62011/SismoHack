class NodoAVL:

  def __init__(self, valor):
    self.valor = valor
    self.altura = 0
    self.hijoIzquierdo = None
    self.hijoDerecho = None
    self.padre = None

  def getValor(self):
    return self.valor

  def setValor(self, valor):
    self.valor = valor

  def getHijoIzquierdo(self):
    return self.hijoIzquierdo

  def setHijoIzquierdo(self, nodo):
    self.hijoIzquierdo = nodo

  def getHijoDerecho(self):
    return self.hijoDerecho

  def setHijoDerecho(self, nodo):
    self.hijoDerecho = nodo

  def getPadre(self):
    return self.padre

  def setPadre(self, nodo):
    self.padre = nodo

  def getAltura(self):
    return self.altura

  def setAltura(self, h):
    self.altura = h