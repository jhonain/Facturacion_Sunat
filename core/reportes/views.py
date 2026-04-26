from django.db.models import Sum, Count, Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

from core.comprobantes.models import Comprobante


class LibroVentasView(APIView):
    """
    GET /api/v1/reportes/ventas-por-periodo/?mes=1&anio=2025&empresa=1

    Retorna:
    - Lista de comprobantes del periodo (facturas y boletas, excluye anulados)
    - Totales: base_imponible, igv, total
    - Resumen por tipo de comprobante
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        mes     = request.query_params.get('mes')
        anio    = request.query_params.get('anio')
        empresa = request.query_params.get('empresa')

        # Validaciones de parámetros
        if not mes or not anio:
            return Response(
                {'error': 'Los parámetros "mes" y "anio" son obligatorios.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            mes  = int(mes)
            anio = int(anio)
            if not (1 <= mes <= 12):
                raise ValueError
        except ValueError:
            return Response(
                {'error': 'Mes debe ser un número entre 1 y 12, y anio un número válido.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Filtrar comprobantes del periodo (excluye borradores y anulados)
        qs = Comprobante.objects.select_related(
            'empresa', 'serie', 'cliente'
        ).filter(
            fecha_emision__year=anio,
            fecha_emision__month=mes,
        ).exclude(
            estado__in=[
                Comprobante.EstadoComprobante.BORRADOR,
                Comprobante.EstadoComprobante.ANULADO,
            ]
        ).filter(
            tipo__in=[
                Comprobante.TipoComprobante.FACTURA,
                Comprobante.TipoComprobante.BOLETA,
            ]
        )

        if empresa:
            qs = qs.filter(empresa_id=empresa)

        # Serializar lista de comprobantes
        comprobantes_data = []
        for c in qs.order_by('fecha_emision', 'serie__serie', 'numero'):
            comprobantes_data.append({
                'id':              c.id,
                'fecha_emision':   str(c.fecha_emision),
                'tipo':            c.tipo,
                'tipo_display':    c.get_tipo_display(),
                'serie_numero':    f"{c.serie.serie}-{c.numero:08d}",
                'ruc_cliente':     c.cliente.numero_documento,
                'cliente':         c.cliente.razon_social,
                'moneda':          c.moneda,
                'base_imponible':  str(c.subtotal),
                'igv':             str(c.igv),
                'total':           str(c.total),
                'estado':          c.estado,
                'estado_display':  c.get_estado_display(),
            })

        # Totales globales
        totales = qs.aggregate(
            total_base_imponible = Sum('subtotal'),
            total_igv            = Sum('igv'),
            total_general        = Sum('total'),
            cantidad_facturas     = Count('id', filter=Q(tipo=Comprobante.TipoComprobante.FACTURA)),
            cantidad_boletas      = Count('id', filter=Q(tipo=Comprobante.TipoComprobante.BOLETA)),
        )

        return Response({
            'periodo': {
                'mes':  mes,
                'anio': anio,
            },
            'resumen': {
                'cantidad_facturas':    totales['cantidad_facturas'] or 0,
                'cantidad_boletas':     totales['cantidad_boletas'] or 0,
                'total_comprobantes':   qs.count(),
                'total_base_imponible': str(totales['total_base_imponible'] or 0),
                'total_igv':            str(totales['total_igv'] or 0),
                'total_general':        str(totales['total_general'] or 0),
            },
            'comprobantes': comprobantes_data,
        })


class DashboardView(APIView):
    """
    GET /api/v1/reportes/dashboard/?empresa=1

    Retorna resumen del mes actual:
    - Total facturas emitidas
    - Total boletas emitidas
    - Monto total
    - Comprobantes RECHAZADOS pendientes de reenvío
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from django.utils import timezone
        hoy     = timezone.now().date()
        empresa = request.query_params.get('empresa')

        qs = Comprobante.objects.filter(
            fecha_emision__year=hoy.year,
            fecha_emision__month=hoy.month,
        ).exclude(estado=Comprobante.EstadoComprobante.BORRADOR)

        if empresa:
            qs = qs.filter(empresa_id=empresa)

        resumen = qs.aggregate(
            total_facturas  = Count('id', filter=Q(tipo=Comprobante.TipoComprobante.FACTURA)),
            total_boletas   = Count('id', filter=Q(tipo=Comprobante.TipoComprobante.BOLETA)),
            monto_total     = Sum('total'),
            rechazados      = Count('id', filter=Q(estado=Comprobante.EstadoComprobante.RECHAZADO)),
        )

        # Detalle de rechazados (para mostrar alertas en el dashboard)
        rechazados_detalle = list(
            qs.filter(estado=Comprobante.EstadoComprobante.RECHAZADO)
            .values('id', 'serie__serie', 'numero', 'cliente__razon_social', 'sunat_descripcion')
        )

        return Response({
            'mes':   hoy.month,
            'anio':  hoy.year,
            'total_facturas':  resumen['total_facturas'] or 0,
            'total_boletas':   resumen['total_boletas'] or 0,
            'monto_total':     str(resumen['monto_total'] or 0),
            'rechazados':      resumen['rechazados'] or 0,
            'rechazados_detalle': rechazados_detalle,
        })
