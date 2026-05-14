from django.db import models

#clientes
class TipoDocumento(models.TextChoices):
    RUC       = '6', 'RUC'
    DNI       = '1', 'DNI'
    CARNET    = '4', 'Carnet de Extranjería'
    PASAPORTE = '7', 'Pasaporte'
    SIN_DOC   = '-', 'Sin Documento'

#Empresa
class RegimenTributario(models.TextChoices):
    GENERAL = 'RG',   'Régimen General'
    ESPECIAL = 'RER', 'Régimen Especial de Renta'
    MYPE     = 'RMT', 'Régimen MYPE Tributario'
    NRUS     = 'NRUS','Nuevo RUS'

#SerieComprobante
class TipoSerie(models.TextChoices):
    FACTURA      = 'F',  'Factura'
    BOLETA       = 'B',  'Boleta'
    NOTA_CREDITO = 'FC', 'Nota de Crédito'

#Producto
class TipoAfectacionIGV(models.TextChoices):
    GRAVADO_ONEROSA      = '10', 'Gravado - Operación Onerosa'
    EXONERADO_ONEROSA    = '20', 'Exonerado - Operación Onerosa'
    INAFECTO_ONEROSA     = '30', 'Inafecto - Operación Onerosa'

#Comprobante
class TipoComprobante(models.TextChoices):
    FACTURA      = '01', 'Factura Electrónica'
    BOLETA       = '03', 'Boleta de Venta'
    NOTA_CREDITO = '07', 'Nota de Crédito'
    NOTA_DEBITO  = '08', 'Nota de Débito'

#estado comprobante
class EstadoComprobante(models.TextChoices):
    BORRADOR  = 'BORRADOR',  'Borrador'
    ENVIADO   = 'ENVIADO',   'Enviado a SUNAT'
    ACEPTADO  = 'ACEPTADO',  'Aceptado por SUNAT'
    RECHAZADO = 'RECHAZADO', 'Rechazado por SUNAT'
    ANULADO   = 'ANULADO',   'Anulado'

#moneda
class MonedaComprobante(models.TextChoices):
    SOLES   = 'PEN', 'Soles'
    DOLARES = 'USD', 'Dólares'


#Tipo Nota de Crédito
class TipoNota(models.TextChoices):
    ANULACION         = '01', 'Anulación de la operación'
    ANULACION_RUC     = '02', 'Anulación por error en el RUC'
    CORRECCION        = '03', 'Corrección por error en la descripción'
    DESCUENTO_GLOBAL  = '04', 'Descuento global'
    DESCUENTO_ITEM    = '05', 'Descuento por ítem'
    DEVOLUCION_TOTAL  = '06', 'Devolución total'
    DEVOLUCION_ITEM   = '07', 'Devolución por ítem'
    BONIFICACION      = '08', 'Bonificación'
    DISMINUCION_VALOR = '09', 'Disminución en el valor'


