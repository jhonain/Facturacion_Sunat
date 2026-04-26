from decimal import Decimal
from django.conf import settings
from rest_framework import serializers

from .models import Comprobante, DetalleComprobante, LogEnvioSunat, NotaCredito
from core.clientes.models import Cliente
from core.productos.models import Producto


# ─────────────────────────────────────────────────────────────────────────────
# Detalle
# ─────────────────────────────────────────────────────────────────────────────

class DetalleComprobanteWriteSerializer(serializers.Serializer):
    """
    Recibe solo los datos que el usuario ingresa.
    Los campos calculados (igv_linea, subtotal, total) se calculan en el servidor.
    """
    producto        = serializers.PrimaryKeyRelatedField(queryset=Producto.objects.all())
    descripcion     = serializers.CharField(max_length=500, required=False, allow_blank=True)
    cantidad        = serializers.DecimalField(max_digits=12, decimal_places=4)
    unidad_medida   = serializers.CharField(max_length=10, default='NIU')
    precio_unitario = serializers.DecimalField(max_digits=12, decimal_places=4)
    descuento       = serializers.DecimalField(max_digits=12, decimal_places=2, default=0)

    def validate_cantidad(self, value):
        if value <= 0:
            raise serializers.ValidationError('La cantidad debe ser mayor a 0.')
        return value

    def validate_precio_unitario(self, value):
        if value <= 0:
            raise serializers.ValidationError('El precio unitario debe ser mayor a 0.')
        return value

    def validate_descuento(self, value):
        if value < 0:
            raise serializers.ValidationError('El descuento no puede ser negativo.')
        return value


class DetalleComprobanteReadSerializer(serializers.ModelSerializer):
    producto_descripcion = serializers.CharField(source='producto.descripcion', read_only=True)

    class Meta:
        model  = DetalleComprobante
        fields = [
            'id', 'producto', 'producto_descripcion',
            'descripcion', 'cantidad', 'unidad_medida',
            'precio_unitario', 'descuento',
            'igv_linea', 'subtotal', 'total',
        ]


# ─────────────────────────────────────────────────────────────────────────────
# Log SUNAT
# ─────────────────────────────────────────────────────────────────────────────

class LogEnvioSunatSerializer(serializers.ModelSerializer):
    class Meta:
        model  = LogEnvioSunat
        fields = ['id', 'fecha_envio', 'estado_respuesta',
                  'codigo_respuesta', 'descripcion']
        read_only_fields = fields


# ─────────────────────────────────────────────────────────────────────────────
# Comprobante — Lectura
# ─────────────────────────────────────────────────────────────────────────────

class ComprobanteReadSerializer(serializers.ModelSerializer):
    detalles        = DetalleComprobanteReadSerializer(many=True, read_only=True)
    logs            = LogEnvioSunatSerializer(many=True, read_only=True)
    tipo_display    = serializers.CharField(source='get_tipo_display',   read_only=True)
    estado_display  = serializers.CharField(source='get_estado_display', read_only=True)
    moneda_display  = serializers.CharField(source='get_moneda_display', read_only=True)
    numero_completo = serializers.SerializerMethodField()
    cliente_nombre  = serializers.CharField(source='cliente.razon_social', read_only=True)
    cliente_doc     = serializers.CharField(source='cliente.numero_documento', read_only=True)

    class Meta:
        model  = Comprobante
        fields = [
            'id', 'empresa', 'serie', 'cliente',
            'cliente_nombre', 'cliente_doc',
            'tipo', 'tipo_display',
            'numero', 'numero_completo',
            'fecha_emision', 'moneda', 'moneda_display',
            'estado', 'estado_display',
            'subtotal', 'igv', 'total',
            'xml_firmado',
            'sunat_ticket', 'sunat_descripcion',
            'creado_en', 'actualizado_en',
            'detalles', 'logs',
        ]

    def get_numero_completo(self, obj):
        return f"{obj.serie.serie}-{obj.numero:08d}"


# ─────────────────────────────────────────────────────────────────────────────
# Comprobante — Escritura  (calcula IGV automáticamente)
# ─────────────────────────────────────────────────────────────────────────────

class ComprobanteWriteSerializer(serializers.ModelSerializer):
    detalles = DetalleComprobanteWriteSerializer(many=True)

    class Meta:
        model  = Comprobante
        fields = [
            'empresa', 'serie', 'cliente', 'tipo',
            'fecha_emision', 'moneda',
            'detalles',
        ]

    # ── Validación: factura requiere RUC ─────────────────────────────────────
    def validate(self, data):
        tipo    = data.get('tipo')
        cliente = data.get('cliente')

        if tipo == Comprobante.TipoComprobante.FACTURA:
            if cliente.tipo_documento != Cliente.TipoDocumento.RUC:
                raise serializers.ValidationError(
                    {'cliente': 'La factura solo puede emitirse a clientes con RUC.'}
                )
            if not cliente.numero_documento.isdigit() or len(cliente.numero_documento) != 11:
                raise serializers.ValidationError(
                    {'cliente': 'El RUC del cliente debe tener 11 dígitos.'}
                )

        if not data.get('detalles'):
            raise serializers.ValidationError(
                {'detalles': 'El comprobante debe tener al menos una línea de detalle.'}
            )

        return data

    # ── Cálculo automático de IGV y totales ──────────────────────────────────
    @staticmethod
    def _calcular_detalle(detalle_data: dict) -> dict:
        """Calcula igv_linea, subtotal y total de una línea."""
        IGV = Decimal(str(settings.IGV_PORCENTAJE))

        cantidad        = Decimal(str(detalle_data['cantidad']))
        precio_unitario = Decimal(str(detalle_data['precio_unitario']))
        descuento       = Decimal(str(detalle_data.get('descuento', 0)))
        producto: Producto = detalle_data['producto']

        valor_venta = (cantidad * precio_unitario) - descuento   # base antes de IGV
        valor_venta = valor_venta.quantize(Decimal('0.01'))

        if producto.tiene_igv():
            igv_linea = (valor_venta * IGV).quantize(Decimal('0.01'))
        else:
            igv_linea = Decimal('0.00')

        total = valor_venta + igv_linea

        return {
            **detalle_data,
            'descripcion':  detalle_data.get('descripcion') or producto.descripcion,
            'unidad_medida': detalle_data.get('unidad_medida') or producto.unidad_medida,
            'igv_linea': igv_linea,
            'subtotal':  valor_venta,
            'total':     total,
        }

    def _calcular_totales(self, detalles_calculados: list) -> dict:
        """Suma subtotal, igv y total del comprobante."""
        subtotal = sum(d['subtotal'] for d in detalles_calculados)
        igv      = sum(d['igv_linea'] for d in detalles_calculados)
        total    = subtotal + igv
        return {
            'subtotal': subtotal.quantize(Decimal('0.01')),
            'igv':      igv.quantize(Decimal('0.01')),
            'total':    total.quantize(Decimal('0.01')),
        }

    def create(self, validated_data):
        from .services import generar_xml_mock  # import local para evitar circular

        detalles_raw  = validated_data.pop('detalles')
        detalles_calc = [self._calcular_detalle(d) for d in detalles_raw]
        totales       = self._calcular_totales(detalles_calc)

        # Numeración correlativa automática
        serie = validated_data['serie']
        numero = serie.obtener_siguiente_correlativo()

        comprobante = Comprobante.objects.create(
            **validated_data,
            numero=numero,
            **totales,
        )

        for det in detalles_calc:
            DetalleComprobante.objects.create(comprobante=comprobante, **det)

        # Generar XML mock (firma simulada)
        comprobante.xml_firmado = generar_xml_mock(comprobante)
        comprobante.estado      = Comprobante.EstadoComprobante.BORRADOR
        comprobante.save(update_fields=['xml_firmado', 'estado'])

        return comprobante

    def update(self, instance, validated_data):
        # No se puede editar un comprobante ya aceptado
        if instance.estado == Comprobante.EstadoComprobante.ACEPTADO:
            raise serializers.ValidationError(
                'No se puede modificar un comprobante ACEPTADO.'
            )

        detalles_raw = validated_data.pop('detalles', [])

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if detalles_raw:
            detalles_calc = [self._calcular_detalle(d) for d in detalles_raw]
            totales       = self._calcular_totales(detalles_calc)

            for attr, value in totales.items():
                setattr(instance, attr, value)

            instance.detalles.all().delete()
            for det in detalles_calc:
                DetalleComprobante.objects.create(comprobante=instance, **det)

        instance.save()
        return instance


# ─────────────────────────────────────────────────────────────────────────────
# Nota de Crédito
# ─────────────────────────────────────────────────────────────────────────────

class NotaCreditoSerializer(serializers.ModelSerializer):
    tipo_nota_display = serializers.CharField(
        source='get_tipo_nota_display', read_only=True
    )

    class Meta:
        model  = NotaCredito
        fields = [
            'id', 'comprobante_referencia', 'comprobante_nota',
            'tipo_nota', 'tipo_nota_display',
            'motivo', 'monto_afectado',
        ]

    def validate(self, data):
        referencia     = data.get('comprobante_referencia')
        monto_afectado = data.get('monto_afectado')

        # El comprobante referenciado debe estar ACEPTADO
        if referencia and referencia.estado != Comprobante.EstadoComprobante.ACEPTADO:
            raise serializers.ValidationError(
                {'comprobante_referencia': 'Solo se puede emitir nota de crédito sobre comprobantes ACEPTADOS.'}
            )

        # El monto afectado no puede superar el total del original
        if referencia and monto_afectado:
            if monto_afectado <= 0:
                raise serializers.ValidationError(
                    {'monto_afectado': 'El monto afectado debe ser mayor a 0.'}
                )
            if monto_afectado > referencia.total:
                raise serializers.ValidationError(
                    {
                        'monto_afectado': (
                            f'El monto afectado (S/ {monto_afectado}) no puede superar '
                            f'el total del comprobante original (S/ {referencia.total}).'
                        )
                    }
                )

        return data
