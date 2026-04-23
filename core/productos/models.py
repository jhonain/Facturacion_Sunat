from django.db import models

from core.empresa.models import Empresa


class CategoriaProducto(models.Model):

    empresa     = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name='categorias'
    )
    nombre      = models.CharField(max_length=100)
    descripcion = models.CharField(max_length=300, blank=True)
    activa      = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name        = 'Categoría'
        verbose_name_plural = 'Categorías'
        ordering            = ['nombre']
        unique_together     = ('empresa', 'nombre')


class Producto(models.Model):

    class TipoAfectacionIGV(models.TextChoices):
        GRAVADO_ONEROSA      = '10', 'Gravado - Operación Onerosa'
        EXONERADO_ONEROSA    = '20', 'Exonerado - Operación Onerosa'
        INAFECTO_ONEROSA     = '30', 'Inafecto - Operación Onerosa'

    empresa          = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name='productos'
    )
    categoria        = models.ForeignKey(
        CategoriaProducto,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='productos'
    )
    codigo           = models.CharField(max_length=50)
    descripcion      = models.CharField(max_length=500)
    unidad_medida    = models.CharField(max_length=10, default='NIU')
    precio_unitario  = models.DecimalField(max_digits=12, decimal_places=4)
    tipo_afectacion_igv = models.CharField(
        max_length=2,
        choices=TipoAfectacionIGV.choices,
        default=TipoAfectacionIGV.GRAVADO_ONEROSA
    )
    activo           = models.BooleanField(default=True)
    creado_en        = models.DateTimeField(auto_now_add=True)

    def tiene_igv(self) -> bool:
        return self.tipo_afectacion_igv == self.TipoAfectacionIGV.GRAVADO_ONEROSA

    def precio_con_igv(self) -> float:
        from django.conf import settings
        if self.tiene_igv():
            return float(self.precio_unitario) * (1 + settings.IGV_PORCENTAJE)
        return float(self.precio_unitario)

    def __str__(self):
        return f"{self.codigo} - {self.descripcion}"

    class Meta:
        verbose_name        = 'Producto'
        verbose_name_plural = 'Productos'
        ordering            = ['descripcion']
        unique_together     = ('empresa', 'codigo')