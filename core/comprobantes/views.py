from decimal import Decimal

from django.http import HttpResponse
from django.utils import timezone
from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import Comprobante, NotaCredito
from .serializer import (
    ComprobanteReadSerializer,
    ComprobanteWriteSerializer,
    NotaCreditoSerializer,
)
from .services import enviar_a_ose_mock
from .pdf import generar_pdf_comprobante


class ComprobanteViewSet(viewsets.ModelViewSet):
    """
    CRUD de comprobantes + acciones especiales.

    Filtros disponibles en GET /api/v1/comprobantes/:
        ?tipo=01            → solo facturas (01=Factura, 03=Boleta, 07=NC)
        ?estado=ACEPTADO    → por estado
        ?fecha_desde=2025-01-01
        ?fecha_hasta=2025-12-31
        ?ruc_cliente=20601234567
    """
    queryset = Comprobante.objects.select_related(
        'empresa', 'serie', 'cliente'
    ).prefetch_related('detalles__producto', 'logs').all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action in ['list', 'retrieve']:
            return ComprobanteReadSerializer
        return ComprobanteWriteSerializer

    # ── Filtros del listado ───────────────────────────────────────────────────
    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        tipo         = params.get('tipo')
        estado       = params.get('estado')
        fecha_desde  = params.get('fecha_desde')
        fecha_hasta  = params.get('fecha_hasta')
        ruc_cliente  = params.get('ruc_cliente')

        if tipo:
            qs = qs.filter(tipo=tipo)
        if estado:
            qs = qs.filter(estado=estado)
        if fecha_desde:
            qs = qs.filter(fecha_emision__gte=fecha_desde)
        if fecha_hasta:
            qs = qs.filter(fecha_emision__lte=fecha_hasta)
        if ruc_cliente:
            qs = qs.filter(cliente__numero_documento=ruc_cliente)

        return qs

    # ── Bloquear eliminación de comprobantes ACEPTADOS ────────────────────────
    def destroy(self, request, *args, **kwargs):
        comprobante = self.get_object()
        if comprobante.estado == Comprobante.EstadoComprobante.ACEPTADO:
            return Response(
                {'error': 'No se puede eliminar un comprobante ACEPTADO. Use una nota de crédito para anularlo.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().destroy(request, *args, **kwargs)

    # ── POST /api/v1/comprobantes/{id}/enviar/ ────────────────────────────────
    @action(detail=True, methods=['post'])
    def enviar(self, request, pk=None):
        """Envía el comprobante al OSE (mock) por primera vez."""
        comprobante = self.get_object()

        estados_no_enviables = [
            Comprobante.EstadoComprobante.ACEPTADO,
            Comprobante.EstadoComprobante.ANULADO,
        ]
        if comprobante.estado in estados_no_enviables:
            return Response(
                {'error': f'No se puede enviar un comprobante en estado {comprobante.estado}.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        comprobante.estado = Comprobante.EstadoComprobante.ENVIADO
        comprobante.save(update_fields=['estado'])

        resultado = enviar_a_ose_mock(comprobante)
        return Response(resultado, status=status.HTTP_200_OK)

    # ── POST /api/v1/comprobantes/{id}/reenviar/ ──────────────────────────────
    @action(detail=True, methods=['post'])
    def reenviar(self, request, pk=None):
        """Reenvía un comprobante que fue RECHAZADO."""
        comprobante = self.get_object()

        if comprobante.estado != Comprobante.EstadoComprobante.RECHAZADO:
            return Response(
                {'error': 'Solo se pueden reenviar comprobantes en estado RECHAZADO.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        comprobante.estado = Comprobante.EstadoComprobante.ENVIADO
        comprobante.save(update_fields=['estado'])

        resultado = enviar_a_ose_mock(comprobante)
        return Response(resultado, status=status.HTTP_200_OK)

    # ── POST /api/v1/comprobantes/{id}/anular/ ────────────────────────────────
    @action(detail=True, methods=['post'])
    def anular(self, request, pk=None):
        """Anula directamente (solo ACEPTADOS). Lo correcto es vía nota de crédito."""
        comprobante = self.get_object()
        if not comprobante.puede_anularse():
            return Response(
                {'error': 'Solo se pueden anular comprobantes ACEPTADOS.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        comprobante.estado = Comprobante.EstadoComprobante.ANULADO
        comprobante.save(update_fields=['estado'])
        return Response({'mensaje': 'Comprobante anulado correctamente.'})

    # ── GET /api/v1/comprobantes/{id}/pdf/ ────────────────────────────────────
    @action(detail=True, methods=['get'])
    def pdf(self, request, pk=None):
        """Devuelve la representación imprimible del comprobante en PDF."""
        comprobante = self.get_object()
        pdf_bytes   = generar_pdf_comprobante(comprobante)

        nombre_archivo = comprobante.nombre_archivo_sunat()
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{nombre_archivo}.pdf"'
        return response


# ── Endpoints específicos por tipo ────────────────────────────────────────────

class FacturaViewSet(viewsets.ModelViewSet):
    """
    POST /api/v1/facturas/ — Emitir factura (solo tipo 01).
    El serializer valida automáticamente que el cliente tenga RUC.
    """
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Comprobante.objects.select_related(
            'empresa', 'serie', 'cliente'
        ).prefetch_related('detalles__producto', 'logs').filter(
            tipo=Comprobante.TipoComprobante.FACTURA
        )

    def get_serializer_class(self):
        if self.action in ['list', 'retrieve']:
            return ComprobanteReadSerializer
        return ComprobanteWriteSerializer

    def perform_create(self, serializer):
        serializer.save(tipo=Comprobante.TipoComprobante.FACTURA)


class BoletaViewSet(viewsets.ModelViewSet):
    """
    POST /api/v1/boletas/ — Emitir boleta (solo tipo 03).
    Acepta clientes con DNI u otros documentos.
    """
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Comprobante.objects.select_related(
            'empresa', 'serie', 'cliente'
        ).prefetch_related('detalles__producto', 'logs').filter(
            tipo=Comprobante.TipoComprobante.BOLETA
        )

    def get_serializer_class(self):
        if self.action in ['list', 'retrieve']:
            return ComprobanteReadSerializer
        return ComprobanteWriteSerializer

    def perform_create(self, serializer):
        serializer.save(tipo=Comprobante.TipoComprobante.BOLETA)


# ── Nota de Crédito ───────────────────────────────────────────────────────────

class NotaCreditoViewSet(viewsets.ModelViewSet):
    queryset           = NotaCredito.objects.select_related(
        'comprobante_referencia', 'comprobante_nota'
    ).all()
    serializer_class   = NotaCreditoSerializer
    permission_classes = [IsAuthenticated]
