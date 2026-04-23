from django.db import models

from core.empresa.models import Empresa, SerieComprobante
from core.clientes.models import Cliente
from core.productos.models import Producto


class Comprobante(models.Model):

    class TipoComprobante(models.TextChoices):
        FACTURA      = '01', 'Factura Electrónica'
        BOLETA       = '03', 'Boleta de Venta'
        NOTA_CREDITO = '07', 'Nota de Crédito'
        NOTA_DEBITO  = '08', 'Nota de Débito'

    class EstadoComprobante(models.TextChoices):
        BORRADOR  = 'BORRADOR',  'Borrador'
        ENVIADO   = 'ENVIADO',   'Enviado a SUNAT'
        ACEPTADO  = 'ACEPTADO',  'Aceptado por SUNAT'
        RECHAZADO = 'RECHAZADO', 'Rechazado por SUNAT'
        ANULADO   = 'ANULADO',   'Anulado'

    class MonedaComprobante(models.TextChoices):
        SOLES   = 'PEN', 'Soles'
        DOLARES = 'USD', 'Dólares'

    empresa       = models.ForeignKey(
        Empresa,
        on_delete=models.PROTECT,
        related_name='comprobantes'
    )
    serie         = models.ForeignKey(
        SerieComprobante,
        on_delete=models.PROTECT,
        related_name='comprobantes'
    )
    cliente       = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name='comprobantes'
    )
    tipo          = models.CharField(
        max_length=2,
        choices=TipoComprobante.choices
    )
    numero        = models.IntegerField()
    fecha_emision = models.DateField()
    moneda        = models.CharField(
        max_length=3,
        choices=MonedaComprobante.choices,
        default=MonedaComprobante.SOLES
    )
    estado        = models.CharField(
        max_length=10,
        choices=EstadoComprobante.choices,
        default=EstadoComprobante.BORRADOR
    )

    # Totales
    subtotal      = models.DecimalField(max_digits=12, decimal_places=2)
    igv           = models.DecimalField(max_digits=12, decimal_places=2)
    total         = models.DecimalField(max_digits=12, decimal_places=2)

    # XML firmado (requerimiento)
    xml_firmado   = models.TextField(blank=True)

    # Respuesta SUNAT
    sunat_ticket      = models.CharField(max_length=50, blank=True)
    sunat_cdr         = models.TextField(blank=True)
    sunat_descripcion = models.CharField(max_length=500, blank=True)

    creado_en     = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def es_factura(self) -> bool:
        return self.tipo == self.TipoComprobante.FACTURA

    def es_boleta(self) -> bool:
        return self.tipo == self.TipoComprobante.BOLETA

    def fue_aceptado(self) -> bool:
        return self.estado == self.EstadoComprobante.ACEPTADO

    def puede_anularse(self) -> bool:
        return self.estado == self.EstadoComprobante.ACEPTADO

    def nombre_archivo_sunat(self) -> str:
        return f"{self.empresa.ruc}-{self.tipo}-{self.serie.serie}-{self.numero:08d}"

    def __str__(self):
        return f"{self.serie.serie}-{self.numero:08d} | {self.cliente.razon_social}"

    class Meta:
        verbose_name        = 'Comprobante'
        verbose_name_plural = 'Comprobantes'
        ordering            = ['-fecha_emision', '-numero']
        unique_together     = ('empresa', 'serie', 'numero')


class DetalleComprobante(models.Model):

    comprobante     = models.ForeignKey(
        Comprobante,
        on_delete=models.CASCADE,
        related_name='detalles'
    )
    producto        = models.ForeignKey(
        Producto,
        on_delete=models.PROTECT,
        related_name='detalles'
    )
    descripcion     = models.CharField(max_length=500)
    cantidad        = models.DecimalField(max_digits=12, decimal_places=4)
    unidad_medida   = models.CharField(max_length=10, default='NIU')
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=4)

    # Campo requerimiento
    descuento       = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    igv_linea       = models.DecimalField(max_digits=12, decimal_places=2)
    subtotal        = models.DecimalField(max_digits=12, decimal_places=2)
    total           = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"{self.descripcion} x{self.cantidad}"

    class Meta:
        verbose_name        = 'Detalle de Comprobante'
        verbose_name_plural = 'Detalles de Comprobante'


class LogEnvioSunat(models.Model):

    comprobante      = models.ForeignKey(
        Comprobante,
        on_delete=models.CASCADE,
        related_name='logs'
    )
    fecha_envio      = models.DateTimeField(auto_now_add=True)
    estado_respuesta = models.CharField(max_length=20)
    codigo_respuesta = models.CharField(max_length=10)
    descripcion      = models.CharField(max_length=500)

    def __str__(self):
        return f"{self.comprobante} → {self.estado_respuesta}"

    class Meta:
        verbose_name        = 'Log de Envío SUNAT'
        verbose_name_plural = 'Logs de Envío SUNAT'
        ordering            = ['-fecha_envio']


class NotaCredito(models.Model):

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

    comprobante_referencia = models.ForeignKey(
        Comprobante,
        on_delete=models.PROTECT,
        related_name='notas_credito'
    )
    comprobante_nota = models.OneToOneField(
        Comprobante,
        on_delete=models.PROTECT,
        related_name='nota_credito_detalle'
    )
    tipo_nota      = models.CharField(
        max_length=2,
        choices=TipoNota.choices
    )
    motivo         = models.CharField(max_length=500)
    monto_afectado = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"NC → {self.comprobante_referencia} | {self.get_tipo_nota_display()}"

    class Meta:
        verbose_name        = 'Nota de Crédito'
        verbose_name_plural = 'Notas de Crédito'