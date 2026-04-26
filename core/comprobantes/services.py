"""
services.py — Lógica de negocio de comprobantes
Generación de XML UBL 2.1, firma XMLDSig y envío SOAP a SUNAT beta.
"""
import base64
import zipfile
import io
import logging
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from cryptography.hazmat.primitives.serialization import pkcs12
from lxml import etree
from signxml import XMLSigner, methods
from requests import Session

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Cargar certificado .pfx
# ─────────────────────────────────────────────────────────────────────────────

def _cargar_certificado():
    """
    Lee el .pfx y retorna (clave_privada, certificado, cadena).
    """
    cert_path = Path(settings.BASE_DIR) / settings.SUNAT_CERT_PATH
    cert_pass = settings.SUNAT_CERT_PASSWORD.encode() if settings.SUNAT_CERT_PASSWORD else None

    print("CERT PATH:", cert_path)
    print("EXISTS:", cert_path.exists())

    with open(cert_path, 'rb') as f:
        pfx_data = f.read()

    private_key, certificate, additional_certs = pkcs12.load_key_and_certificates(
        pfx_data, cert_pass
    )
    return private_key, certificate, additional_certs


# ─────────────────────────────────────────────────────────────────────────────
# 2. Generar XML UBL 2.1 completo
# ─────────────────────────────────────────────────────────────────────────────

def _generar_xml(comprobante) -> bytes:
    """
    Genera el XML UBL 2.1 conforme a SUNAT.
    Retorna bytes UTF-8 del XML sin firmar.
    """
    IGV_PORCENTAJE = str(settings.IGV_PORCENTAJE * 100)
    ruc_empresa = settings.SUNAT_CERT_RUC
    fecha_emision = str(comprobante.fecha_emision)
    hora_emision = datetime.now().strftime('%H:%M:%S')
    moneda = comprobante.moneda
    serie_num = f"{comprobante.serie.serie}-{comprobante.numero:08d}"

    NS = {
        None: 'urn:oasis:names:specification:ubl:schema:xsd:Invoice-2',
        'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
        'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
        'ext': 'urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2',
    }

    def sub(parent, ns_prefix, tag, text=None, **attribs):
        ns_map = {
            'cac': NS['cac'],
            'cbc': NS['cbc'],
            'ext': NS['ext'],
        }
        full_tag = f"{{{ns_map[ns_prefix]}}}{tag}"
        el = etree.SubElement(parent, full_tag, **attribs)
        if text is not None:
            el.text = str(text)
        return el

    root = etree.Element(
        '{urn:oasis:names:specification:ubl:schema:xsd:Invoice-2}Invoice',
        nsmap=NS
    )

    # Extensiones para firma
    ext_content = etree.SubElement(
        root,
        '{urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2}UBLExtensions'
    )
    ext_item = etree.SubElement(
        ext_content,
        '{urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2}UBLExtension'
    )
    etree.SubElement(
        ext_item,
        '{urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2}ExtensionContent'
    )

    # Cabecera
    sub(root, 'cbc', 'UBLVersionID', '2.1')
    sub(root, 'cbc', 'CustomizationID', '2.0')
    sub(
        root, 'cbc', 'ProfileID', '0101',
        schemeName='SUNAT:Identificador de Tipo de Operacion',
        schemeAgencyName='PE:SUNAT',
        schemeURI='urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo17',
    )
    sub(root, 'cbc', 'ID', serie_num)
    sub(root, 'cbc', 'IssueDate', fecha_emision)
    sub(root, 'cbc', 'IssueTime', hora_emision)
    sub(
        root, 'cbc', 'InvoiceTypeCode', comprobante.tipo,
        listAgencyName='PE:SUNAT',
        listName='SUNAT:Identificador de Tipo de Documento',
        listURI='urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo01',
    )
    sub(
        root, 'cbc', 'Note',
        _monto_en_letras(float(comprobante.total), moneda),
        languageLocaleID='1000'
    )
    sub(root, 'cbc', 'DocumentCurrencyCode', moneda)

    # Emisor
    supplier = sub(root, 'cac', 'AccountingSupplierParty')
    party_s = sub(supplier, 'cac', 'Party')
    party_name_s = sub(party_s, 'cac', 'PartyName')
    sub(party_name_s, 'cbc', 'Name', comprobante.empresa.razon_social)

    postal_s = sub(party_s, 'cac', 'PostalAddress')
    sub(postal_s, 'cbc', 'ID', '150101')  # Ubigeo

    # Dirección según orden UBL/SUNAT
    sub(postal_s, 'cbc', 'StreetName', comprobante.empresa.direccion or 'SIN DIRECCION')
    sub(postal_s, 'cbc', 'CitySubdivisionName', 'LIMA')   # Urbanización / zona
    sub(postal_s, 'cbc', 'CityName', 'LIMA')
    sub(postal_s, 'cbc', 'CountrySubentity', 'LIMA')      # Departamento
    sub(postal_s, 'cbc', 'District', 'LIMA')
    country_s = sub(postal_s, 'cac', 'Country')
    sub(country_s, 'cbc', 'IdentificationCode', 'PE')

    party_tax_s = sub(party_s, 'cac', 'PartyTaxScheme')
    sub(party_tax_s, 'cbc', 'RegistrationName', comprobante.empresa.razon_social)
    sub(party_tax_s, 'cbc', 'CompanyID', ruc_empresa, schemeID='6')
    tax_scheme_s = sub(party_tax_s, 'cac', 'TaxScheme')
    sub(tax_scheme_s, 'cbc', 'ID', '6')
    sub(tax_scheme_s, 'cbc', 'Name', 'RUC')
    sub(tax_scheme_s, 'cbc', 'TaxTypeCode', 'VAT')

    party_legal_s = sub(party_s, 'cac', 'PartyLegalEntity')
    sub(party_legal_s, 'cbc', 'RegistrationName', comprobante.empresa.razon_social)

    # Cliente
    customer = sub(root, 'cac', 'AccountingCustomerParty')
    party_c = sub(customer, 'cac', 'Party')
    party_tax_c = sub(party_c, 'cac', 'PartyTaxScheme')
    sub(party_tax_c, 'cbc', 'RegistrationName', comprobante.cliente.razon_social)
    sub(
        party_tax_c, 'cbc', 'CompanyID',
        comprobante.cliente.numero_documento,
        schemeID=comprobante.cliente.tipo_documento
    )
    tax_scheme_c = sub(party_tax_c, 'cac', 'TaxScheme')
    sub(tax_scheme_c, 'cbc', 'ID', comprobante.cliente.tipo_documento)
    sub(
        tax_scheme_c, 'cbc', 'Name',
        'RUC' if comprobante.cliente.tipo_documento == '6' else 'DOC'
    )
    sub(tax_scheme_c, 'cbc', 'TaxTypeCode', 'VAT')

    party_legal_c = sub(party_c, 'cac', 'PartyLegalEntity')
    sub(party_legal_c, 'cbc', 'RegistrationName', comprobante.cliente.razon_social)

    # Impuestos
    tax_total = sub(root, 'cac', 'TaxTotal')
    sub(tax_total, 'cbc', 'TaxAmount', str(comprobante.igv), currencyID=moneda)
    tax_subtotal = sub(tax_total, 'cac', 'TaxSubtotal')
    sub(tax_subtotal, 'cbc', 'TaxableAmount', str(comprobante.subtotal), currencyID=moneda)
    sub(tax_subtotal, 'cbc', 'TaxAmount', str(comprobante.igv), currencyID=moneda)
    tax_cat = sub(tax_subtotal, 'cac', 'TaxCategory')
    sub(tax_cat, 'cbc', 'ID', 'S', schemeID='UN/ECE 5305', schemeName='Tax Category Identifier')
    sub(tax_cat, 'cbc', 'Percent', IGV_PORCENTAJE)
    tax_scheme_igv = sub(tax_cat, 'cac', 'TaxScheme')
    sub(tax_scheme_igv, 'cbc', 'ID', '1000')
    sub(tax_scheme_igv, 'cbc', 'Name', 'IGV')
    sub(tax_scheme_igv, 'cbc', 'TaxTypeCode', 'VAT')

    # Totales
    legal_total = sub(root, 'cac', 'LegalMonetaryTotal')
    sub(legal_total, 'cbc', 'LineExtensionAmount', str(comprobante.subtotal), currencyID=moneda)
    sub(legal_total, 'cbc', 'TaxExclusiveAmount', str(comprobante.subtotal), currencyID=moneda)
    sub(legal_total, 'cbc', 'TaxInclusiveAmount', str(comprobante.total), currencyID=moneda)
    sub(legal_total, 'cbc', 'PayableAmount', str(comprobante.total), currencyID=moneda)

    # Detalle
    for i, det in enumerate(comprobante.detalles.select_related('producto').all(), start=1):
        line = sub(root, 'cac', 'InvoiceLine')
        sub(line, 'cbc', 'ID', str(i))
        sub(line, 'cbc', 'InvoicedQuantity', str(det.cantidad), unitCode=det.unidad_medida)
        sub(line, 'cbc', 'LineExtensionAmount', str(det.subtotal), currencyID=moneda)

        pricing = sub(line, 'cac', 'PricingReference')
        alt_cond = sub(pricing, 'cac', 'AlternativeConditionPrice')
        precio_con_igv = det.precio_unitario * (
            Decimal('1') + Decimal(str(settings.IGV_PORCENTAJE))
        )
        sub(alt_cond, 'cbc', 'PriceAmount', f'{precio_con_igv:.4f}', currencyID=moneda)
        sub(alt_cond, 'cbc', 'PriceTypeCode', '01')

        line_tax = sub(line, 'cac', 'TaxTotal')
        sub(line_tax, 'cbc', 'TaxAmount', str(det.igv_linea), currencyID=moneda)
        line_tsub = sub(line_tax, 'cac', 'TaxSubtotal')
        sub(line_tsub, 'cbc', 'TaxableAmount', str(det.subtotal), currencyID=moneda)
        sub(line_tsub, 'cbc', 'TaxAmount', str(det.igv_linea), currencyID=moneda)
        line_tcat = sub(line_tsub, 'cac', 'TaxCategory')
        sub(line_tcat, 'cbc', 'ID', 'S', schemeID='UN/ECE 5305', schemeName='Tax Category Identifier')
        sub(line_tcat, 'cbc', 'Percent', IGV_PORCENTAJE)
        sub(
            line_tcat, 'cbc', 'TaxExemptionReasonCode', '10',
            listAgencyName='PE:SUNAT',
            listName='Afectacion del IGV',
            listURI='urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo07'
        )
        line_ts = sub(line_tcat, 'cac', 'TaxScheme')
        sub(line_ts, 'cbc', 'ID', '1000')
        sub(line_ts, 'cbc', 'Name', 'IGV')
        sub(line_ts, 'cbc', 'TaxTypeCode', 'VAT')

        item = sub(line, 'cac', 'Item')
        sub(item, 'cbc', 'Description', det.descripcion)

        price = sub(line, 'cac', 'Price')
        sub(price, 'cbc', 'PriceAmount', str(det.precio_unitario), currencyID=moneda)

    return etree.tostring(root, xml_declaration=True, encoding='UTF-8', pretty_print=False)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Firmar XML
# ─────────────────────────────────────────────────────────────────────────────

def _firmar_xml(xml_bytes: bytes) -> bytes:
    """
    Firma el XML UBL usando XMLDSig enveloped.
    Inserta ds:Signature dentro de ext:ExtensionContent.
    """
    from cryptography.hazmat.primitives.serialization import (
        Encoding, PrivateFormat, NoEncryption,
    )
    import re

    private_key, certificate, _ = _cargar_certificado()

    key_pem = private_key.private_bytes(
        Encoding.PEM,
        PrivateFormat.TraditionalOpenSSL,
        NoEncryption(),
    )
    cert_pem = certificate.public_bytes(Encoding.PEM)

    EXT = 'urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2'
    DS  = 'http://www.w3.org/2000/09/xmldsig#'
    CAC = 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2'
    CBC = 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2'

    root = etree.fromstring(xml_bytes)

    signature_id = "LlamaPeSign"

    # Nodo UBL de firma
    cac_sig = etree.SubElement(root, f'{{{CAC}}}Signature')
    cac_sig_id = etree.SubElement(cac_sig, f'{{{CBC}}}ID')
    cac_sig_id.text = signature_id

    signatory = etree.SubElement(cac_sig, f'{{{CAC}}}SignatoryParty')
    party_id_cont = etree.SubElement(signatory, f'{{{CAC}}}PartyIdentification')
    party_id_el = etree.SubElement(party_id_cont, f'{{{CBC}}}ID')
    party_id_el.text = settings.SUNAT_CERT_RUC

    party_name_cont = etree.SubElement(signatory, f'{{{CAC}}}PartyName')
    party_name_el = etree.SubElement(party_name_cont, f'{{{CBC}}}Name')
    party_name_el.text = "EMPRESA"

    dig_sig_att = etree.SubElement(cac_sig, f'{{{CAC}}}DigitalSignatureAttachment')
    ext_ref = etree.SubElement(dig_sig_att, f'{{{CAC}}}ExternalReference')
    uri_el = etree.SubElement(ext_ref, f'{{{CBC}}}URI')
    uri_el.text = f"#{signature_id}"

    signer = XMLSigner(
        method=methods.enveloped,
        signature_algorithm='rsa-sha256',
        digest_algorithm='sha256',
        c14n_algorithm='http://www.w3.org/TR/2001/REC-xml-c14n-20010315',
    )

    # Importante: NO pasar reference_uri ni id_attribute.
    signed_root = signer.sign(
        root,
        key=key_pem,
        cert=cert_pem,
    )

    # Tomar la firma tal cual la generó SignXML
    ds_sig = signed_root.find(f'.//{{{DS}}}Signature')
    if ds_sig is not None:
        ds_sig.set("Id", signature_id)

        parent = ds_sig.getparent()
        if parent is not None:
            parent.remove(ds_sig)

        ext_content_el = signed_root.find(f'.//{{{EXT}}}ExtensionContent')
        if ext_content_el is not None:
            ext_content_el.append(ds_sig)

    signed_bytes = etree.tostring(
        signed_root,
        xml_declaration=False,
        encoding='unicode',
        pretty_print=False,
    ).encode('UTF-8')

    signed_bytes = b"<?xml version='1.0' encoding='UTF-8'?>\n" + signed_bytes

    # Quitar saltos de línea en el certificado
    signed_bytes = re.sub(
        b'(<ds:X509Certificate[^>]*>)(.*?)(</ds:X509Certificate>)',
        lambda m: m.group(1) + m.group(2).replace(b'\n', b'') + m.group(3),
        signed_bytes,
        flags=re.DOTALL,
    )
    return signed_bytes


# ─────────────────────────────────────────────────────────────────────────────
# 4. Empaquetar en ZIP
# ─────────────────────────────────────────────────────────────────────────────

def _crear_zip(nombre_archivo: str, xml_firmado) -> bytes:
    """
    SUNAT sendBill: ZIP con un único XML.
    """
    if isinstance(xml_firmado, str):
        xml_firmado = xml_firmado.encode('UTF-8')

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{nombre_archivo}.xml", xml_firmado)
    return buffer.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# 5. Enviar a SUNAT
# ─────────────────────────────────────────────────────────────────────────────

def _enviar_soap(nombre_archivo: str, zip_bytes: bytes) -> dict:
    """
    Envía el ZIP al servicio sendBill de SUNAT beta.
    Para sendBill, SUNAT devuelve el CDR en la misma respuesta SOAP.
    """
    ruc = settings.SUNAT_CERT_RUC
    usuario = f"{ruc}{settings.SUNAT_USUARIO_SOL}"
    clave = settings.SUNAT_CLAVE_SOL
    wsdl_url = settings.SUNAT_URL_BETA

    print("RUC:", ruc)
    print("USUARIO_SOL:", settings.SUNAT_USUARIO_SOL)
    print("USUARIO CONCAT:", usuario)
    print("CLAVE_SOL:", clave)
    print("WSDL_URL:", wsdl_url)
    print("NOMBRE_ARCHIVO:", nombre_archivo)

    session = Session()

    try:
        zip_b64 = base64.b64encode(zip_bytes).decode('ascii')

        soap_body = f"""<?xml version="1.0" encoding="utf-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:ser="http://service.sunat.gob.pe"
                  xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">
  <soapenv:Header>
    <wsse:Security>
      <wsse:UsernameToken>
        <wsse:Username>{usuario}</wsse:Username>
        <wsse:Password>{clave}</wsse:Password>
      </wsse:UsernameToken>
    </wsse:Security>
  </soapenv:Header>
  <soapenv:Body>
    <ser:sendBill>
      <fileName>{nombre_archivo}.zip</fileName>
      <contentFile>{zip_b64}</contentFile>
    </ser:sendBill>
  </soapenv:Body>
</soapenv:Envelope>"""

        endpoint = wsdl_url.replace('?wsdl', '')
        headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': 'urn:sendBill',
        }

        print("ENDPOINT:", endpoint)
        print("SOAP BODY SIZE:", len(soap_body))

        resp = session.post(
            endpoint,
            data=soap_body.encode('utf-8'),
            headers=headers,
            timeout=30
        )

        print("HTTP STATUS:", resp.status_code)
        print("RESPONSE COMPLETO:", resp.text[:2000])

        if resp.status_code != 200:
            return {
                'estado': 'RECHAZADO',
                'codigo': str(resp.status_code),
                'descripcion': f'Error HTTP {resp.status_code}: {resp.text[:300]}',
                'cdr_xml': '',
            }

        root_resp = etree.fromstring(resp.content)

        fault_str = root_resp.find('.//{http://schemas.xmlsoap.org/soap/envelope/}faultstring')
        fault_code = root_resp.find('.//{http://schemas.xmlsoap.org/soap/envelope/}faultcode')
        if fault_str is not None:
            return {
                'estado': 'RECHAZADO',
                'codigo': fault_code.text.split('.')[-1] if fault_code is not None and fault_code.text else '9999',
                'descripcion': fault_str.text or 'Error SOAP SUNAT',
                'cdr_xml': '',
            }

        cdr_b64_el = root_resp.find('.//{http://service.sunat.gob.pe}applicationResponse')
        if cdr_b64_el is None:
            cdr_b64_el = root_resp.find('.//applicationResponse')
        if cdr_b64_el is None:
            cdr_b64_el = root_resp.find('.//{http://service.sunat.gob.pe}return')

        if cdr_b64_el is None or not cdr_b64_el.text:
            return {
                'estado': 'RECHAZADO',
                'codigo': '9998',
                'descripcion': 'SUNAT no devolvió applicationResponse/CDR',
                'cdr_xml': '',
            }

        cdr_zip_bytes = base64.b64decode(cdr_b64_el.text)
        cdr_xml = _extraer_cdr(cdr_zip_bytes)
        codigo, descripcion = _parsear_cdr(cdr_xml)
        estado = 'ACEPTADO' if codigo == '0' else 'RECHAZADO'

        return {
            'estado': estado,
            'codigo': codigo,
            'descripcion': descripcion,
            'cdr_xml': cdr_xml,
        }

    except Exception as exc:
        logger.error(f"Error SOAP SUNAT: {exc}")
        return {
            'estado': 'RECHAZADO',
            'codigo': '9999',
            'descripcion': f'Error de conexión con SUNAT: {str(exc)}',
            'cdr_xml': '',
        }


def _extraer_cdr(cdr_zip_bytes: bytes) -> str:
    """Extrae el XML del CDR desde el ZIP de respuesta de SUNAT."""
    try:
        with zipfile.ZipFile(io.BytesIO(cdr_zip_bytes)) as zf:
            for name in zf.namelist():
                if name.endswith('.xml'):
                    return zf.read(name).decode('utf-8')
    except Exception:
        pass
    return ''


def _parsear_cdr(cdr_xml: str) -> tuple:
    """
    Extrae código y descripción del CDR de SUNAT.
    """
    if not cdr_xml:
        return '9999', 'Sin respuesta CDR'

    try:
        root = etree.fromstring(cdr_xml.encode('utf-8'))
        ns = {
            'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
            'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
        }
        codigo = root.find('.//cac:DocumentResponse/cac:Response/cbc:ResponseCode', ns)
        desc = root.find('.//cac:DocumentResponse/cac:Response/cbc:Description', ns)
        return (
            codigo.text if codigo is not None else '0',
            desc.text if desc is not None else 'Aceptado',
        )
    except Exception:
        return '0', 'Aceptado'


# ─────────────────────────────────────────────────────────────────────────────
# 6. Funciones públicas
# ─────────────────────────────────────────────────────────────────────────────

def generar_xml_y_firmar(comprobante) -> bytes:
    """
    Genera el XML UBL 2.1 completo y lo firma con el .pfx.
    """
    xml_bytes = _generar_xml(comprobante)
    xml_firmado = _firmar_xml(xml_bytes)

    print("TIPO XML_FIRMADO:", type(xml_firmado))
    print("PRIMEROS BYTES:", xml_firmado[:100] if isinstance(xml_firmado, bytes) else str(xml_firmado)[:100])

    if isinstance(xml_firmado, bytes):
        xml_firmado_texto = xml_firmado.decode('utf-8', errors='replace')
    else:
        xml_firmado_texto = str(xml_firmado)

    comprobante.xml_firmado = xml_firmado_texto
    comprobante.save(update_fields=['xml_firmado'])

    return xml_firmado


def _debug_zip(zip_bytes: bytes):
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            print("[ZIP] NAMES:", zf.namelist())
            for name in zf.namelist():
                if name.endswith('.xml'):
                    data = zf.read(name)
                    print("[ZIP] Archivo XML:", name)
                    print("[ZIP] XML primeros 300 bytes:", data[:300])
                    break
    except Exception as e:
        print("[ZIP] Error al leer ZIP:", e)


def enviar_a_sunat(comprobante) -> dict:
    """
    Flujo completo real:
      1. Generar XML UBL 2.1
      2. Firmar con .pfx
      3. Empaquetar en ZIP
      4. Enviar SOAP a SUNAT beta
      5. Procesar CDR y actualizar estado
    """
    from .models import LogEnvioSunat

    nombre_archivo = comprobante.nombre_archivo_sunat()

    xml_firmado = generar_xml_y_firmar(comprobante)
    print("XML FIRMADO (primeros 2000 chars):", xml_firmado[:2000])

    zip_bytes = _crear_zip(nombre_archivo, xml_firmado)
    print("[ZIP] TAMAÑO en bytes:", len(zip_bytes))
    print("[ZIP] TAMAÑO base64:", len(base64.b64encode(zip_bytes)))

    _debug_zip(zip_bytes)

    resultado = _enviar_soap(nombre_archivo, zip_bytes)

    nuevo_estado = (
        comprobante.EstadoComprobante.ACEPTADO
        if resultado['estado'] == 'ACEPTADO'
        else comprobante.EstadoComprobante.RECHAZADO
    )

    comprobante.estado = nuevo_estado
    comprobante.sunat_ticket = f"INT-{comprobante.id}-{timezone.now().strftime('%Y%m%d%H%M%S')}"
    comprobante.sunat_descripcion = resultado['descripcion']
    comprobante.sunat_cdr = resultado.get('cdr_xml', '')
    comprobante.save(update_fields=['estado', 'sunat_ticket', 'sunat_descripcion', 'sunat_cdr'])

    LogEnvioSunat.objects.create(
        comprobante=comprobante,
        estado_respuesta=resultado['estado'],
        codigo_respuesta=resultado['codigo'],
        descripcion=resultado['descripcion'],
    )

    return {
        'estado': resultado['estado'],
        'codigo': resultado['codigo'],
        'descripcion': resultado['descripcion'],
        'ticket': comprobante.sunat_ticket,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 7. Aliases de compatibilidad
# ─────────────────────────────────────────────────────────────────────────────

def generar_xml_mock(comprobante) -> str:
    """
    Alias para serializer.py.
    """
    try:
        return generar_xml_y_firmar(comprobante)
    except Exception as exc:
        logger.warning(f"Firma real falló, usando XML básico sin firma: {exc}")
        return _generar_xml_basico(comprobante)


def enviar_a_ose_mock(comprobante) -> dict:
    """
    Alias para views.py.
    """
    return enviar_a_sunat(comprobante)


# ─────────────────────────────────────────────────────────────────────────────
# 8. Fallback
# ─────────────────────────────────────────────────────────────────────────────

def _generar_xml_basico(comprobante) -> str:
    """XML mínimo sin firma — solo para desarrollo local."""
    detalles_xml = ''
    for i, det in enumerate(comprobante.detalles.all(), start=1):
        detalles_xml += f"""
        <cac:InvoiceLine>
            <cbc:ID>{i}</cbc:ID>
            <cbc:InvoicedQuantity unitCode="{det.unidad_medida}">{det.cantidad}</cbc:InvoicedQuantity>
            <cbc:LineExtensionAmount currencyID="{comprobante.moneda}">{det.subtotal}</cbc:LineExtensionAmount>
            <cac:Item><cbc:Description>{det.descripcion}</cbc:Description></cac:Item>
            <cac:Price>
                <cbc:PriceAmount currencyID="{comprobante.moneda}">{det.precio_unitario}</cbc:PriceAmount>
            </cac:Price>
        </cac:InvoiceLine>"""

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
         xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
         xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
    <cbc:UBLVersionID>2.1</cbc:UBLVersionID>
    <cbc:ID>{comprobante.serie.serie}-{comprobante.numero:08d}</cbc:ID>
    <cbc:IssueDate>{comprobante.fecha_emision}</cbc:IssueDate>
    <cbc:InvoiceTypeCode>{comprobante.tipo}</cbc:InvoiceTypeCode>
    <cbc:DocumentCurrencyCode>{comprobante.moneda}</cbc:DocumentCurrencyCode>
    <cbc:Note>SIN FIRMA - Solo desarrollo</cbc:Note>
    {detalles_xml}
</Invoice>"""


# ─────────────────────────────────────────────────────────────────────────────
# 9. Monto en letras
# ─────────────────────────────────────────────────────────────────────────────

def _monto_en_letras(monto: float, moneda: str) -> str:
    """Convierte monto numérico a letras en formato SUNAT."""
    entero = int(monto)
    centavos = round((monto - entero) * 100)
    moneda_texto = 'SOLES' if moneda == 'PEN' else 'DÓLARES AMERICANOS'

    unidades = ['', 'UNO', 'DOS', 'TRES', 'CUATRO', 'CINCO',
                'SEIS', 'SIETE', 'OCHO', 'NUEVE']
    decenas = ['', 'DIEZ', 'VEINTE', 'TREINTA', 'CUARENTA',
               'CINCUENTA', 'SESENTA', 'SETENTA', 'OCHENTA', 'NOVENTA']
    especiales = {
        10: 'DIEZ', 11: 'ONCE', 12: 'DOCE', 13: 'TRECE',
        14: 'CATORCE', 15: 'QUINCE', 16: 'DIECISÉIS',
        17: 'DIECISIETE', 18: 'DIECIOCHO', 19: 'DIECINUEVE',
    }
    centenas = ['', 'CIENTO', 'DOSCIENTOS', 'TRESCIENTOS', 'CUATROCIENTOS',
                'QUINIENTOS', 'SEISCIENTOS', 'SETECIENTOS', 'OCHOCIENTOS', 'NOVECIENTOS']

    def num_a_letras(n: int) -> str:
        if n == 0:
            return 'CERO'
        if n == 100:
            return 'CIEN'
        if n < 10:
            return unidades[n]
        if n in especiales:
            return especiales[n]
        if n < 100:
            d, u = divmod(n, 10)
            return decenas[d] + (' Y ' + unidades[u] if u else '')
        if n < 1000:
            c, r = divmod(n, 100)
            return centenas[c] + (' ' + num_a_letras(r) if r else '')
        if n < 1_000_000:
            m, r = divmod(n, 1000)
            miles = 'MIL' if m == 1 else num_a_letras(m) + ' MIL'
            return miles + (' ' + num_a_letras(r) if r else '')
        return str(n)

    return f"SON {num_a_letras(entero)} Y {centavos:02d}/100 {moneda_texto}"