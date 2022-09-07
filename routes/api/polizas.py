import app
import os
from flask import request

from decouple import config
import xml.etree.ElementTree as ET
from app.app import UPLOAD_FOLDER
from datetime import datetime, timedelta
UPLOAD_FOLDER = config('UPLOAD_FOLDER')


@app.route('/api/gastos/cfdi', methods = ['POST'])
def anexa_cfdi():
    try:
        if request.method == 'POST':
            f = request.files['file']
            filename = os.path.join(UPLOAD_FOLDER, f.filename)
            print('file will be saved in:', filename)
            f.save(filename)

            # set search params            
            print(f'''XML-CFDI ===> Working with xml search params:
            PREFIX: {config('XML_GASTOS_PREFIJO')}
            COMPLEMENTO: {config('XML_GASTOS_COMPLEMENTO')}
            TIMBRE_FISCAL_DIGITAL: {config('XML_GASTOS_COMPLEMENTO_TIMBRE_FISCAL')}
            ''')

            # parse an xml file by name
            tree = ET.parse(filename)
            root = tree.getroot()
            # By default, the prefix should be `cfdi`, but it could be other one:
            if 'cfdi:' in root.tag:
                search_prefix_by = 'cfdi:'
            else:
                search_prefix_by = config('XML_GASTOS_PREFIJO')
            print(f'searching prefix:', search_prefix_by)
            is_cfdi = search_prefix_by in root.tag
            print('isCFDI:',  is_cfdi)
            record_cfdi = {}
            if is_cfdi:
                # complement attributes: Timbre fiscal digital                
                complement_attribute = ['UUID', 'FechaTimbrado']                
                complemento = root.find(search_prefix_by+config('XML_GASTOS_COMPLEMENTO'))
                tfd = complemento.find(config('XML_GASTOS_TIMBRE_FISCAL_PREFIJO')+config('XML_GASTOS_COMPLEMENTO_TIMBRE_FISCAL')).attrib
                for attr in complement_attribute:
                    record_cfdi[attr] = tfd[attr]
                print('cfdi translated:', record_cfdi)
                return {'status': 'ok', 'cfdi': record_cfdi}
            else:
                return {'status': 'ko', 'message': f'It seems the uploaded XML file is not a valid CFDI, prefix found {search_prefix_by}'}
    except Exception as e:
        print('Exception reading file', e)
        return {'status': 'ko', 'message':e.args[0]}


@app.route('/api/gastos/polizas', methods=['POST'])
def gastos_polizas():
    status_process = []
    TIPO_POLIZA = 'Dr'
    IMPORTE_CARGO_CERO = 0
    IMPORTE_ABONO_CERO = 0
    CUENTA_IMPUESTO = "1200-001-000"
    DESCRIPCION_IMPUESTO_IVAIEPS = "IVA ACREDITABLE PENDIENTE DE PAGO"

    CUENTA_IMPUESTO_CLAVE = 1
    CUENTA_RETENCION_ISR_CLAVE = 2
    CUENTA_RETENCION_IVA_CLAVE = 3
       
    CUENTA_RETENCIONES_HONORARIOS_ISR = "2150-001-001"
    DESCRIPCION_IMPUESTO_RETENCIONES_HONORARIOS_ISR = "RETENCION 10% ISR"
    
    CUENTA_RETENCIONES_HONORARIOS_IVA = "2150-001-004"
    DESCRIPCION_IMPUESTO_RETENCIONES_HONORARIOS_IVA = "RETENCION 10% IVA"
    
    CUENTA_PROVEEDORES = "2110-003-001"
    DESCRIPCION_CUENTA_PROVEEDORES = "PROVEEDORES"
    es_cfdi = 0
    uuid = ''

    try:
        payload = request.get_json()
        print('payload received to process invoice: ', payload)
        status_process.append({'id': 'payload received', 'request': payload, 'response': 'n/a'})
        documento = payload['document']
        if 'cfdi' in payload: 
            uuid = payload['cfdi']['UUID']
            es_cfdi = 1
        
        detalles = payload['weights']

        fecha_aplicacion = documento['appliedDate']
        df = datetime.strptime(fecha_aplicacion, '%Y-%m-%d')
        ejercicio = df.year
        periodo = df.month
        status_process.append({'id': 'search next folio', 'request': {'tipo':TIPO_POLIZA, 'ejercicio':ejercicio, 'periodo':periodo}, 'response':'n/a'})
        folio = siguiente_folio(TIPO_POLIZA, ejercicio, periodo)
        status_process.append({'id': 'search next folio', 'request': '','folio': folio})
        
        cargo_total = 0
        if(folio['folio']>0):
            next_folio = folio['folio']
        else:
            next_folio = 'Imposible determinar un folio para: {0} {1}-{2}'.format('Dr', ejercicio, periodo)
            raise Exception('Imposible determinar un folio para: {0} {1}-{2}'.format('Dr', ejercicio, periodo))
            
        dia = datetime.now().day
        descripcionPoliza = f'{documento["description"]} {documento["appliedDate"]} {documento["supplier"]} {documento["reference"]}'
        auxiliares = []
        save_status_process('defining auxiliars', detalles, 'n/a')
        for detalle in detalles:
            cargo = detalle['value']
            cargo_total = cargo_total + cargo
            abono = IMPORTE_ABONO_CERO
            cuenta_contable = detalle['id'][0:12]
            tipo_cambio = documento['exchangeRate']
            unidad_negocio = detalle['id'][15:]
            auxiliares.append({'cuentaContable':cuenta_contable, 'unidadNegocio':unidad_negocio, 'descripcion':descripcionPoliza, 'tipoCambio':tipo_cambio, 'cargo':cargo, 'abono':abono})
        
        # Manejo para los impuestos
        if documento['tax4']>0:
            cargo = documento['tax4']
            cargo_total = cargo_total + cargo
            abono = IMPORTE_ABONO_CERO
            valor_cuenta = impuesto(CUENTA_IMPUESTO_CLAVE)
            if valor_cuenta:
                cuenta_contable = valor_cuenta['cuenta']
                descripcion = valor_cuenta['impuesto']
            else:
                cuenta_contable = CUENTA_IMPUESTO
                descripcion = DESCRIPCION_IMPUESTO_IVAIEPS            
            auxiliares.append({'cuentaContable':cuenta_contable, 'unidadNegocio':'', 'descripcion':descripcion, 'tipoCambio':1, 'cargo':cargo, 'abono':abono})

        if documento['taxes']>0:
            if documento['tax1']>0:
                abono = documento['tax1']
                valor_cuenta = impuesto(CUENTA_RETENCION_ISR_CLAVE)
                if valor_cuenta:
                    cuenta_contable = valor_cuenta['cuenta']
                    descripcion = valor_cuenta['impuesto']
                else:
                    cuenta_contable = CUENTA_RETENCIONES_HONORARIOS_ISR
                    descripcion = DESCRIPCION_IMPUESTO_RETENCIONES_HONORARIOS_ISR
                auxiliares.append({'cuentaContable':cuenta_contable, 'unidadNegocio':'', 'descripcion':descripcion, 'tipoCambio':1, 'cargo':IMPORTE_CARGO_CERO, 'abono':abono})
            if documento['tax2']>0:
                abono = documento['tax2']
                valor_cuenta = impuesto(CUENTA_RETENCION_ISR_CLAVE)
                if valor_cuenta:
                    cuenta_contable = valor_cuenta['cuenta']
                    descripcion = valor_cuenta['impuesto']
                else:
                    cuenta_contable = CUENTA_RETENCIONES_HONORARIOS_ISR
                    descripcion = DESCRIPCION_IMPUESTO_RETENCIONES_HONORARIOS_ISR
                auxiliares.append({'cuentaContable':cuenta_contable, 'unidadNegocio':'', 'descripcion':descripcion, 'tipoCambio':1, 'cargo':IMPORTE_CARGO_CERO, 'abono':abono})

            if documento['tax3']>0:
                abono = documento['tax3']
                valor_cuenta = impuesto(CUENTA_RETENCION_IVA_CLAVE)
                if valor_cuenta:
                    cuenta_contable = valor_cuenta['cuenta']
                    descripcion = valor_cuenta['impuesto']
                else:
                    cuenta_contable = CUENTA_RETENCIONES_HONORARIOS_IVA 
                    descripcion = DESCRIPCION_IMPUESTO_RETENCIONES_HONORARIOS_IVA
                auxiliares.append({'cuentaContable':cuenta_contable, 'unidadNegocio':'', 'descripcion':descripcion, 'tipoCambio':1, 'cargo':IMPORTE_CARGO_CERO, 'abono':abono})
                
        # anexa detalle en cuenta de proveedores 
        # print('====>', cargo_total, '-', documento['taxes'], '  = ', cargo_total - documento['taxes'])
        auxiliares.append({'cuentaContable': CUENTA_PROVEEDORES, 'unidadNegocio':'', 'descripcion':DESCRIPCION_CUENTA_PROVEEDORES, 'tipoCambio':1, 'cargo':IMPORTE_CARGO_CERO, 'abono':cargo_total-documento['taxes']})
        save_status_process('defining auxiliars', f'tax4: {documento["tax4"]}, taxes: {documento["taxes"]}', auxiliares)
        poliza = {
            'numeroFolio': next_folio, 'descripcion':descripcionPoliza, 'tipo':TIPO_POLIZA, 'numeroDia': dia, 'fecha': fecha_aplicacion,
            'periodo': periodo, 'ejercicio': ejercicio, 'cfdi': es_cfdi, 'uuid': uuid,
            'auxiliares': auxiliares
        }
        print('invoice prepared to be inserted:', poliza)
        save_status_process('invoice prepared to be inserted:', poliza, 'n/a')
                
        response = inserta_poliza_coi(poliza)
        save_status_process('invoice prepared to be inserted:', poliza, response)
        print('insert poliza and auxiliar results in:', response) 
        if 'auxiliars' in response and response['auxiliars']>0:
            save_status_process('actualiza_contabilizado:', f'reference: {documento["reference"]}, supplierId: {documento["supplierId"]}, chargeId: {documento["chargeId"]}, conceptId: {documento["conceptId"]}', 'n/a')
            response = actualiza_contabilizado(documento['reference'], documento['supplierId'], documento['chargeId'], documento['conceptId'])
            save_status_process('actualiza_contabilizado:', f'reference: {documento["reference"]}, supplierId: {documento["supplierId"]}, chargeId: {documento["chargeId"]}, conceptId: {documento["conceptId"]}', response)
            save_status_process('actualiza_folio:', f'tipo poliza: {TIPO_POLIZA}, ejercicio: {ejercicio}, periodo: {periodo}, folio: {next_folio}', 'n/a')
            response = actualiza_folio(TIPO_POLIZA, ejercicio, periodo, next_folio)
            save_status_process('actualiza_folio:', f'tipo poliza: {TIPO_POLIZA}, ejercicio: {ejercicio}, periodo: {periodo}, folio: {next_folio}', response)            
            save_status_process('__end', next_folio)
            
            return {'status': 'ok', 'data':payload}
        else:
            return {'status': 'ko', 'message':f'Algo ha ido mal y no se ha insertado la poliza correctamente. {response}'}
    except Exception as e:
        print(f'Exception in {request.method} gastos_polizas:', e)
        save_status_process('__end', next_folio)
        return {'status': 'ko', 'message':e.args[0]}
