from django.db import models
from core.empresa.models import Empresa

class Cliente(models.Model):
    class TipoDocumento(models.TextChoices):
        RUC      = '6', 'RUC'
        DNI      = '1', 'DNI'
        CARNET   = '4', 'Carnet de Extranjería'
        PASAPORTE = '7', 'Pasaporte'
        SIN_DOC  = '-', 'Sin Documento'

    empresa         = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name='clientes'
    )
    tipo_documento  = models.CharField(
        max_length=1,
        choices=TipoDocumento.choices,
        default=TipoDocumento.DNI
    )
    numero_documento = models.CharField(max_length=20)
    razon_social     = models.CharField(max_length=200)
    direccion        = models.CharField(max_length=300, blank=True)
    correo           = models.EmailField(blank=True)
    telefono         = models.CharField(max_length=20, blank=True)
    activo           = models.BooleanField(default=True)
    creado_en        = models.DateTimeField(auto_now_add=True)

    def es_persona_juridica(self) -> bool:
        return self.tipo_documento == self.TipoDocumento.RUC

    def es_persona_natural(self) -> bool:
        return self.tipo_documento == self.TipoDocumento.DNI

    def __str__(self):
        return f"{self.numero_documento} - {self.razon_social}"

    class Meta:
        verbose_name        = 'Cliente'
        verbose_name_plural = 'Clientes'
        ordering            = ['razon_social']
        unique_together     = ('empresa', 'numero_documento')