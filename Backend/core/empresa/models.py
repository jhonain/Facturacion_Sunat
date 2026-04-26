from django.db import models

class Empresa(models.Model):
    class RegimenTributario(models.TextChoices):
        GENERAL = 'RG',   'Régimen General'
        ESPECIAL = 'RER', 'Régimen Especial de Renta'
        MYPE     = 'RMT', 'Régimen MYPE Tributario'
        NRUS     = 'NRUS','Nuevo RUS'

    ruc               = models.CharField(max_length=11, unique=True)
    razon_social      = models.CharField(max_length=200)
    nombre_comercial  = models.CharField(max_length=200, blank=True)
    direccion         = models.TextField()
    regimen_tributario = models.CharField(
        max_length=4,
        choices=RegimenTributario.choices,
        default=RegimenTributario.GENERAL
    )
    activa     = models.BooleanField(default=True)
    creado_en  = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.ruc} - {self.razon_social}"

    class Meta:
        verbose_name        = 'Empresa'
        verbose_name_plural = 'Empresas'
        ordering            = ['razon_social']


class SerieComprobante(models.Model):

    class TipoSerie(models.TextChoices):
        FACTURA      = 'F',  'Factura'
        BOLETA       = 'B',  'Boleta'
        NOTA_CREDITO = 'FC', 'Nota de Crédito'

    empresa            = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name='series'
    )
    tipo               = models.CharField(max_length=2, choices=TipoSerie.choices)
    serie              = models.CharField(max_length=4)
    correlativo_actual = models.IntegerField(default=0)

    def obtener_siguiente_correlativo(self) -> int:
        self.correlativo_actual += 1
        self.save(update_fields=['correlativo_actual'])
        return self.correlativo_actual

    def __str__(self):
        return f"{self.serie} - {self.get_tipo_display()}"

    class Meta:
        unique_together     = ('empresa', 'serie')
        verbose_name        = 'Serie de Comprobante'
        verbose_name_plural = 'Series de Comprobante'
        ordering            = ['serie']