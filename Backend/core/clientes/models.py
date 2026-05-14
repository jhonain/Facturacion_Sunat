from django.db import models
from core.empresa.models import Empresa
from config.choices import TipoDocumento

class Cliente(models.Model):

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
        return self.tipo_documento == TipoDocumento.RUC

    def es_persona_natural(self) -> bool:
        return self.tipo_documento == TipoDocumento.DNI

    def __str__(self):
        return f"{self.numero_documento} - {self.razon_social}"

    class Meta:
        verbose_name        = 'Cliente'
        verbose_name_plural = 'Clientes'
        ordering            = ['razon_social']
        unique_together     = ('empresa', 'numero_documento')