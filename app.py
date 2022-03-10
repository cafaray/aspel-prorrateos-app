from crypt import methods
from distutils.log import error
from email.policy import default
import functools
import os
from unittest import result
from urllib import response
from urllib.parse import urlparse
from urllib.request import Request
# import logging.config
from flask import Flask, redirect, url_for, render_template, request, session, flash, jsonify
import requests
import json
from jinja2 import TemplateNotFound
from datetime import datetime, timedelta
# import calendar
from openpyxl import Workbook
from decouple import config

app = Flask(__name__) # , template_folder='templates', static_folder='static')
# logging_conf_path = os.path.normpath(os.path.join(os.path.dirname(__file__), 'logging.conf'))
# print('===> logging conf path: ', logging_conf_path)
# logging.config.fileConfig(logging_conf_path)
# log = logging.getLogger(__name__)

app.secret_key = "c29ydGUuYmlvdGVjc2EuY29tL2FkbWluCg=="
app.permanent_session_lifetime= timedelta(hours=2)
app.config['EXPLAIN_TEMPLATE_LOADING'] = True

FILE_LOCATION = config('FILE_LOCATION')
BASE_URL_COI = config('BASE_URL_COI')
BASE_URL_SAE = config('BASE_URL_SAE')
BASE_URL_PONDERADOS = config('BASE_URL_PONDERADOS')

print(f'Working with \n * FILE_LOCATION: {FILE_LOCATION}\n * BASE_URL_COI: {BASE_URL_COI}\n * BASE_URL_SAE: {BASE_URL_SAE}\n * BASE_URL_PONDERADOS: {BASE_URL_PONDERADOS}')

@app.route('/api/impuestos/<id>', methods=['PUT'])
def update_impuesto(id: int):
    try:        
        #payload = {'account':account, 'business_unit_id':businessUnitId, 'weighted': weighted}
        if (request.method=='PUT'):            
            #print('request', id, request.form)
            payload = request.get_json()            
            url = BASE_URL_PONDERADOS+'/cuentas/'+id            
            #print('url:', url)
            #print('payload:', payload)
            response=invoke(url, 'PUT', payload=payload)
            if (response and response.ok):
                result = response.json()
                print('result put impuesto:', result)
                return result
            else:
                print('response', response.status_code)
                return {'status':'ko'}
    except Exception as e:
        print(f'Exception in {request.method} impuesto:', e)
        return e


@app.route('/api/ponderados/<id>/detalles', methods=['POST', 'PUT', 'DELETE'])
def update_ponderado(id:int):
    try:        
        #payload = {'account':account, 'business_unit_id':businessUnitId, 'weighted': weighted}
        if (request.method=='POST'):            
            #print('request', id, request.form)
            payload = request.get_json()
            # payload = {'baseAccount': request.form.get('baseAccount'), 'businessAreaId': request.form.get('businessUnit'), 'percentage':request.form.get('percentage') }
            url = BASE_URL_PONDERADOS+'/ponderados/'+id+'/details'
            #print('url:', url)
            #print('payload:', payload)
            response=invoke(url, 'POST', payload=payload)
            if (response and response.ok):
                result = response.json()
                #print('result post porcentajes:', result)
                return result
            else:
                print('response', response.status_code)
                return {'status':'ko'}
        if (request.method=='PUT'):            
            payload = request.get_json()
            url = f'{BASE_URL_PONDERADOS}/ponderados/{id}/details'
            #print('url:', url)
            #print('payload:', payload)
            response=invoke(url, 'PUT', payload=payload)
            if (response and response.ok):
                result = response.json()
                #print('result put porcentajes:', result)
                return result
            else:
                print('response', response.status_code)
                return {'status':'ko'}
        if (request.method=='DELETE'):            
            payload = request.get_json()
            url = f'{BASE_URL_PONDERADOS}/ponderados/{id}/details'
            #print('url:', url)
            #print('payload:', payload)
            response=invoke(url, 'DELETE', payload=payload)
            if (response and response.ok):
                result = response.json()
                #print('result delete porcentaje:', result)
                return result
            else:
                print('response', response.status_code)
                return {'status':'ko'}
    except Exception as e:
        print(f'Exception in {request.method} update_ponderado:', e)
        return e    

def genera_excel_poliza(data):
    try:        
        wb = Workbook()
        ws = wb.active
        ws.title = 'Poliza Dr'
        # Header ->
        ws['A3'] = data['tipo']
        ws['B3'] = data['numero']
        ws['C3'] = data['concepto']
        ws['D3'] = data['dia']
        # Header <-

        # details ->
        j = 4
        for detalle in data['detalles']:
            ws['A'+str(j)] = ''
            ws['B'+str(j)] = detalle['cuenta_contable']
            ws['C'+str(j)] = detalle['departamento']
            ws['D'+str(j)] = detalle['concepto']
            ws['E'+str(j)] = detalle['tipo_cambio']
            if detalle['cargo']>0:
                ws['F'+str(j)] = detalle['cargo']
            else:
                ws['F'+str(j)] = ''
            if detalle['abono']>0:
                ws['G'+str(j)] = detalle['abono']
            else:
                ws['G'+str(j)] = ''
            j = j + 1
        # ->
        ws['B'+str(j)] = 'FIN_PARTIDAS'
        filename = f"{FILE_LOCATION}poliza_diario_venta_{data['numero']}.xlsx"
        wb.save(filename = filename)
        return filename
    except Exception as e:
        print('Error while generar_archivo:', e)
        raise e

def genera_poliza_diario(documents, date_from, number_invoice):
    try:
        TIPO_POLIZA = "Dr"
        DEPARTAMENTO_DEFAULT = 0
        CUENTA_CLIENTE_DEFAULT = "1150-003-000"
        CUENTA_DEPARTAMENTO = "4100-001-000"
        CUENTA_DEPARTAMENTO_IMPUESTO_0 = "4100-001-000"
        CUENTA_IMPUESTO = "2170-001-000"
        CUENTA_IMPUESTO_0 = "2170-002-000"

        concepto = "Ventas del dia " + date_from.strftime("%d-%m-%Y")
        folio = number_invoice
        day = datetime.now().day
        poliza = {'tipo': TIPO_POLIZA, 'numero': folio, 'concepto': concepto, 'dia': day, 'detalles': []}
        detalles = []
        # detalles: por cada documento
        x = 1
        for document in documents:
            detalle_cliente, detalle_departamento, detalle_impuesto = {}, {}, {} # {'cuenta_contable':'', 'departamento':'', 'concepto': '', 'tipo_cambio':0, 'cargo':0, 'abono':0}
            cuenta_contable = document['CUENTA_CONTABLE']
            if cuenta_contable!='':
                detalle_cliente['cuenta_contable'] = cuenta_contable
            else:
                detalle_cliente['cuenta_contable'] = CUENTA_CLIENTE_DEFAULT
            detalle_cliente['departamento'] = 0
            detalle_cliente['concepto'] = document['NOMBRE'] + " - " + document['CVE_CLPV'] + " Doc. " + document['CVE_DOC']
            detalle_cliente['tipo_cambio'] = document['TIPO_CAMBIO']
            detalle_cliente['cargo'] = document['IMPORTE']
            detalle_cliente['abono'] = 0
            detalles.append(detalle_cliente)

            if document['IVA'] > 0:
                detalle_departamento['cuenta_contable'] = CUENTA_DEPARTAMENTO
            else:
                detalle_departamento['cuenta_contable'] = CUENTA_DEPARTAMENTO_IMPUESTO_0                    
            detalle_departamento['departamento'] = document['items'][0]['CENTRO_COSTOS'] # first item detailed in document gives the value
            detalle_departamento['concepto'] = "Doc. " + document['DESCRIPCION'] + " " + document['FECHA_DOC'] + " " + document['NOMBRE']
            detalle_departamento['tipo_cambio'] = document['TIPO_CAMBIO']
            detalle_departamento['cargo'] = 0
            detalle_departamento['abono'] = document['TOTAL']
            detalles.append(detalle_departamento)

            if document['IVA'] > 0:
                detalle_impuesto['cuenta_contable'] = CUENTA_IMPUESTO
                detalle_impuesto['concepto'] = "IVA 16% Doc. " + document['CVE_DOC']
            else:
                detalle_impuesto['cuenta_contable'] = CUENTA_IMPUESTO_0
                detalle_impuesto['concepto'] = "IVA 0% Doc. " + document['CVE_DOC']
            detalle_impuesto['departamento'] = 0                
            detalle_impuesto['tipo_cambio'] = document['TIPO_CAMBIO']
            detalle_impuesto['cargo'] = 0
            detalle_impuesto['abono'] = document['IVA']
            detalles.append(detalle_impuesto)
            print(f'\n===> detalles {x}:', detalles)
            x = x + 1

        #itera
        #print('detalles:', detalles)
        poliza['detalles'] = detalles
        return poliza
    except Exception as e:
        print('Error while genera_poliza', e)
        return None

@app.route('/api/facturasdiario', methods=['POST'])
def procesa_diario_ventas():
    try:        
        #payload = {'account':account, 'business_unit_id':businessUnitId, 'weighted': weighted}
        payload = request.get_json()
        #print('payload:', payload)
        date_from = datetime.strptime(payload['dateFrom'], '%Y-%m-%d').date()
        number_invoice = payload['numberInvoice']
        #print('date to query:', date_from)
        if (request.method=='POST'):
            documents = documentos_venta_sae(date_from, date_to)
            if len(documents)>0:
                poliza = genera_poliza_diario(documents, date_from, number_invoice)
                if (poliza):
                    print("\n\n\nRecord:\n", poliza, "\n\n\n")
                    # ===> genera el archivo excel:
                    filename = genera_excel_poliza(poliza)
                    if filename:                        
                        print('File created' + filename)            
                        
                        ejercicio = date_from.year
                        periodo = date_from.month
                        #print('ejercicio: ', ejercicio, 'periodo:', periodo)
                        print(f'Updating invoice number to {number_invoice} under {ejercicio}-{periodo}')
                        url = f'{BASE_URL_COI}folios/{ejercicio}'
                        payload = json.dumps({"periodo": periodo, "tipo": "Dr", "folio": number_invoice})
                        response = invoke(url, 'PUT', payload=payload) #, content_type="'Content-Type': 'application/json'")
                        print('response invoke update folio', response)
                        if (response and response.status_code and response.ok):                            
                            result = response.json()
                            return {'status': 'ok', 'details': f'Se ha generado el archivo {filename}'}
                        else:
                            return {'status': 'ko', 'details': response.status_code}
                    else:
                        return {'status': 'ko', 'details': 'Error generating the file'}
                else:
                    return {'status': 'ko', 'details': 'Error generating the structured data for the invoice'}
            else:
                return {'status': 'ko', 'details': 'Error generating the structured data for the invoice'}
        else:
            return {'status': 'ko', 'details': 'Error getting documents'}
    except Exception as e:
        print(f'Exception in {request.method} procesa_diario_ventas:', e)
        return {'status': 'ko', 'details': f'Exception in method {str(e)}'}

def genera_poliza_venta(documents, date_from, date_to, number_invoice):
    try:
        TIPO_POLIZA = "Dr"
        CUENTA_IMPORTE_DEBE = "5000-001-001"
        CUENTA_IMPORTE_HABER = "1190-005-000"

        wb = Workbook()
        ws = wb.active
        ws.title = 'Poliza Dr'
        # Header ->
        ws['A3'] = TIPO_POLIZA
        ws['B3'] = number_invoice
        ws['C3'] = f'Costo de ventas del periodo: {date_from.strftime("%d-%m-%Y")} - {date_to.strftime("%d-%m-%Y")}'
        ws['D3'] = datetime.now().day
        # Header <-

        # detalles: por cada documento
        j = 4        
        for document in documents:
            ws['A'+str(j)] = ''
            
            ws['B'+str(j)] = CUENTA_IMPORTE_DEBE
            ws['C'+str(j)] = document['items'][0]['CENTRO_COSTOS']
            ws['D'+str(j)] = f'Doc. {document["IDENTIFICADOR"]}, {document["FECHA_DOC"]}    {document["CVE_CLPV"]} - {document["NOMBRE"]}'
            ws['E'+str(j)] = document['TIPO_CAMBIO']            
            ws['F'+str(j)] = document['IMPORTE']
            ws['G'+str(j)] = 0
            j = j + 1

            for item in document['items']:
                
                ws['B'+str(j)] = CUENTA_IMPORTE_HABER
                ws['C'+str(j)] = item['CENTRO_COSTOS']
                ws['D'+str(j)] = f'Costo de ventas. Doc. {document["CVE_DOC"]} {document["FECHA_DOC"]} {item["CVE_ART"]}-{item["DESCRIPCION"]}'
                ws['E'+str(j)] = item['TIPO_CAMBIO']            
                ws['F'+str(j)] = 0
                ws['G'+str(j)] = item['IMPORTE']
                j = j + 1
        # ->        
        ws['B'+str(j)] = 'FIN_PARTIDAS'        
        filename = f'{FILE_LOCATION}polizas_venta_{number_invoice}.xlsx'
        wb.save(filename = filename)
        return filename
    except Exception as e:
        print('Error while generar_archivo:', e)
        raise e

@app.route('/api/facturas', methods=['POST'])
def procesa_ventas():
    try:        
        #payload = {'account':account, 'business_unit_id':businessUnitId, 'weighted': weighted}
        payload = request.get_json()
        #print('payload:', payload)
        date_from = datetime.strptime(payload['dateFrom'], '%Y-%m-%d').date()
        date_to = datetime.strptime(payload['dateTo'], '%Y-%m-%d').date()
        number_invoice = payload['numberInvoice']
        #print('date to query:', date_from)
        if (request.method=='POST'):
            #print('requiring documents')
            documents = documentos_venta_sae(date_from, date_to)
            for document in documents:
                sum_haber = 0
                for item in document['items']:
                    sum_haber = sum_haber + item['IMPORTE']
                #print('sum of partida.importe0', sum_haber)
                document['IMPORTE'] = round(sum_haber, 2)
            #print('gatered documents:', len(documents))
            if len(documents)>0:
                # ===> genera el archivo excel:
                filename = genera_poliza_venta(documents, date_from, date_to, number_invoice)
                if (filename):
                    print('File created' + filename)
                    ejercicio = date_from.year
                    periodo = date_from.month
                    #print('ejercicio: ', ejercicio, 'periodo:', periodo)
                    print(f'Updating invoice number to {number_invoice} under {ejercicio}-{periodo}')
                    url = f'{BASE_URL_COI}folios/{ejercicio}'
                    payload = json.dumps({"periodo": periodo, "tipo": "Dr", "folio": number_invoice})
                    response = invoke(url, 'PUT', payload=payload) #, content_type="'Content-Type': 'application/json'")
                    print('response invoke update folio', response)
                    if (response and response.status_code and response.ok):                            
                        result = response.json()
                        print('result', result)
                        return {'status': 'ok', 'details': f'Se ha generado el archivo {filename}'}
                    else:
                        return {'status': 'ko', 'details': response.status_code}
                else:
                    return {'status': 'ko', 'details': 'Error generating the file'}
            else:
                return {'status': 'ko', 'details': 'Error getting documents'}
    except Exception as e:
        print(f'Exception in {request.method} procesa_ventas:', e)
        return {'status': 'ko', 'details': f'Exception in method {str(e)}'}

@app.route('/api/ponderados', methods=['POST', 'DELETE'])
def update_ponderados():
    try:        
        #payload = {'account':account, 'business_unit_id':businessUnitId, 'weighted': weighted}
        if (request.method=='POST'):            
            #print('request', id, request.form)
            payload = request.get_json()            
            url = BASE_URL_PONDERADOS+'/ponderados'
            #print('url:', url)
            #print('payload:', payload)
            response=invoke(url, 'POST', payload=payload)
            if (response and response.ok):
                result = response.json()
                #print('result post porcentaje:', result)
                return result
            else:
                print('response', response.status_code)
                return {'status':'ko'}
        if (request.method=='DELETE'):            
            payload = request.get_json()
            url = BASE_URL_PONDERADOS+'/ponderados'
            #print('url:', url)
            #print('payload:', payload)
            response=invoke(url, 'DELETE', payload=payload)
            if (response and response.ok):
                result = response.json()
                #print('result delete porcentaje:', result)
                return result
            else:
                print('response', response.status_code)
                return {'status':'ko'}
    except Exception as e:
        print(f'Exception in {request.method} update_ponderados:', e)
        return {'status': 'ko', 'details': f'Exception in method {str(e)}'}

### Función en desuso. Se utilizo como parte del ejemplo.
def get_segment(request): 
    try:
        segment = request.path.split('/')[-1]
        if segment == '':
            segment = 'index.html'
        return segment    
    except Exception as e:
        print('Exception while getting segment:', e)
        return None          

def validate_user(email: str, password: str):
    try:
        url_login = BASE_URL_PONDERADOS + '/sec/login'        
        credentials = {'user': email, 'password': password}
        print('calling to loging: ', url_login, credentials)
        response = requests.post(url_login, data=credentials)
        print(response)
        if(response.ok):            
            data = response.json()
            print('===> token generated', data['token'])
            print('===> login response.headers', response.headers['x-user-id'])
            session['token'] = data['token']
            session['user'] = email
            session['userId'] = response.headers['x-user-id']
            return True
        else: 
            return False
    except Exception as e:
        print(e)
        return False

def invoke(url, method, payload=None, content_type='application/json'):
    try:     
        token = session.get('token', '')
        user_id = session.get('userId', '')
        headers = {'x-auth':token, 'userId': user_id, 'Content-Type': content_type}
        if payload:
            print('invoking at', method, url, headers, payload)
            req = requests.Request(method, url, headers=headers, data=payload)
        else:    
            print('invoking at', method, url, headers)
            req = requests.Request(method, url, headers=headers)
        prepped = req.prepare()
        print('req', prepped)
        print('payload', payload)
        s = requests.Session()
        response = s.send(prepped, timeout=200)
        print('response.status', response.status_code)
        print('response.ok', response.ok)
        return response
    except Exception as e:
        print(' ** Exception invoking:\n===>', method, url, '\n===>payload:',payload, '\n==========\nError:', e, '\n==========')
        raise e

def porcentajes(args):
    try:
        #print('args', args)
        query_params = '?'
        if (args['supplier']): query_params = query_params + 'supplier=' + args['supplier'] + '&'
        if (args['concept']): query_params = query_params + 'concept=' + args['concept']        
        url = f'{BASE_URL_PONDERADOS}/ponderados{query_params}'
        response = invoke(url, 'GET')
        #print('response of invoke', response)
        if (response and response.ok):
            result = response.json()
            #print('result get porcentajes:', result)
            return result
        else:
            print('response', response.status_code)
            return []
    except Exception as e:
        print('Exception getting porcentajes:', e)
        return e

def ponderado(args):
    try:
        #print('args', args)
        params = ''
        if (args['weighted']): params = args['weighted']        
        url = f'{BASE_URL_PONDERADOS}/ponderados/{params}/details'
        response = invoke(url, 'GET')
        #print('response of invoke', response)
        result = {'total': 0, 'weight': params, 'data': []}
        if (response and response.ok):
            data = response.json()
            if len(data)>0:
                suma = 0
                for i in data:
                    suma = suma + i['percentage']
                suma = round(suma, 2)
                result = {'total': (suma*100), 'weight': params, 'data': data}
                # print('result', result)                
            return result
        else:
            print('response', response.status_code)
            return response
    except Exception as e:
        print('Exception getting ponderado: ', e)
        return e

def unidades():
    try:
        if request.method=='GET':
            # get all unidades
            url = f'{BASE_URL_PONDERADOS}/unidades'
            response = invoke(url, 'GET')
            if (response.ok):
                result = response.json()
                # print('result', result)
                return result
            else:
                print('response.status_code:', response.status_code)
                return []
        elif request.method=='POST':
            url = '{BASE_URL_PONDERADOS}/unidades'
            response = invoke(url, 'POST')
            if (response and response.ok):
                result = response.json()
                # print('result', result)
                return result
            else:
                print('response.status_code:', response.status_code)
                return []

    except Exception as e:
        print(f'Exception {request.method} unidades:', e)
        return e

def conceptos():
    try:
        if request.method=='GET':
            # get all unidades
            url = f'{BASE_URL_SAE}conceptos'
            response = invoke(url, 'GET')
            if (response.ok):
                result = response.json()
                # print('result', result)
                return result
            else:
                print('response.status_code:', response.status_code)
                return []        
    except Exception as e:
        print(f'Exception {request.method} conceptos:', e)
        return e

def cuentas_base():
    try:
        if request.method=='GET':
            url = BASE_URL_COI+'cuentas'
            response = invoke(url, 'GET')
            if (response.ok):
                result = response.json()
                return result
            else:
                print('response.status_code:', response.status_code)
    except Exception as e:
        print(f'Exception {request.method} cuentasBase:', e)
        return e

def tipos_poliza_coi():
    try:
        if request.method=='GET':
            url = BASE_URL_COI+'polizas/tipos'
            response = invoke(url, 'GET')
            if (response.ok):
                result = response.json()
                return result
            else:
                print('response.status_code:', response.status_code)
    except Exception as e:
        print(f'Exception {request.method} cuentasBase:', e)
        return e

def departamentos_coi():
    try:
        if request.method=='GET':
            url = BASE_URL_COI+'deptos'
            response = invoke(url, 'GET')
            if (response.ok):
                result = response.json()
                return result
            else:
                print('response.status_code:', response.status_code)
    except Exception as e:
        print(f'Exception {request.method} departamentos:', e)
        return e

def ultimo_periodo():
    try:
        if request.method=='GET':
            url = BASE_URL_COI+'periodos/ultimo'
            response = invoke(url, 'GET')
            if (response.ok):
                result = response.json()
                return result
            else:
                print('response:', response.status_code)
    except Exception as e:
        print(f'Exception {request.method} ultimo_periodo:', e)
        return e

def impuestos():
    try:
        if request.method=='GET':
            # get all unidades            
            url = BASE_URL_PONDERADOS+'/cuentas'
            response = invoke(url, 'GET')
            #print('response', response)
            if (response.ok):
                result = response.json()
                # print('result', result)
                return result
            else:
                print('response.status_code:', response.status_code)
                return []
    except Exception as e:
        print('Exception getting impuestos:', e)
        return e    

def proveedores():
    try:
        if request.method=='GET':
            # get all unidades
            url = BASE_URL_SAE+'proveedores'
            response = invoke(url, 'GET')
            if (response.ok):
                result = response.json()
                # print('result', result)
                return result
            else:
                print('response.status_code:', response.status_code)
                return []        
    except Exception as e:
        print('Exception getting proveedores:', e)
        return e

def documentos_compra_sae(date_from, date_to):
    try:
        if request.method=='GET':
            # get all unidades
            params = '?from={0}&to={1}'.format(date_from, date_to)
            url = f'{BASE_URL_SAE}compras/details{params}'
            response = invoke(url, 'GET')
            if (response.ok):
                result = response.json()
                #print('result', result)
                return result
            else:
                print('response.status_code:', response.status_code)
                return []        
    except Exception as e:
        print('Exception getting documentos_compra_sae:', e)
        return e

def deprecated_documentos_venta_sae(date_from, date_to):
    try:
        if request.method=='GET':
            # get all unidades
            params = '?from={0}&to={1}'.format(date_from, date_to)
            url = f'{BASE_URL_SAE}facturas{params}'
            response = invoke(url, 'GET')
            if (response.ok):
                result = response.json()
                #print('result', result)
                return result
            else:
                print('response.status_code:', response.status_code)
                return []        
    except Exception as e:
        print('Exception getting documentos_ventas_sae:', e)
        return e

def siguiente_folio(tipo, ejercicio, periodo):
    try:
        url = BASE_URL_COI+"folios/{0}/next?tipo={1}&periodo={2}".format(ejercicio, tipo, periodo)
        
        response = invoke(url, 'GET')
        if (response.ok):
            result = response.json()
            print('get next folio:', result)
            return result
        else:
            print('get next folio:', response.status_code)
            return response.json()
    except Exception as e:
        print('Exception getting next folio:', e)
        raise e

def documentos_venta_sae(date_from, date_to):
    try:
        params = '?from={0}&to={1}'.format(date_from, date_to)
        url = f'{BASE_URL_SAE}facturas{params}'
        response = invoke(url, 'GET')        
        if (response and response.ok):                        
            result = response.json()
            #print('result facturas', result)
            return result
        else:
            print('response: ', response.status_code)
            return []        
    except Exception as e:
        print('Exception getting facturas: ', e)
        raise e

def close_session(token):
    try:
        url_logout = BASE_URL_PONDERADOS + '/sec/logout'        
        data = {'session': token}
        print('calling to logout: ', url_logout, data)
        response = requests.post(url_logout, data=data)
        print(response)
        if(response.status_code==200 or response.status_code==204):
            return True
        else: 
            return False        
    except Exception as e:
        print(e)
        return False

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method=='POST':
        print('Come to Login-POST', request.form)
        print(len(request.form))
        if(len(request.form) < 2): 
            return redirect('home/page-500.html')
        is_session = validate_user(request.form['email'], request.form['password'])
        print('Result from validate user and create session is: ', is_session)
        if is_session:
            session.permanent = False
            user = request.form['email']
            #log.info('===> user logged {}'.format(user))
            session['user'] = user  
            return redirect(url_for('home'))
        else:
            flash("Usuario o contraseña incorrecto!", "danger")
            return render_template("/home/login.html")
    else:
        if 'user' in session:
            return redirect(url_for('home'))
        return render_template('/home/login.html')

@app.route('/unidades', methods=['POST', 'GET'])
def unidades_negocio():
    data = unidades()
    if (data):
        print('sendig data to form:', data) 
    else:
        data = []
    return render_template('home/unidades.html', data= data)


@app.route('/pfacturasdiario', methods=['GET'])
def polizas_ventas():
    try:
        print('params:',request.args)
        date_from = request.args.get('datefrom')    
        if date_from:
            data = documentos_venta_sae(date_from, date_from)
            print('\n\n\ndata: ok')
            print('\nrequesting next folio ...')
            df = datetime.strptime(date_from, '%Y-%m-%d')
            ejercicio = df.year
            periodo = df.month
            folio = siguiente_folio('Dr', ejercicio, periodo)            
            if(folio['folio']>0):
                next_folio = folio['folio']
            else:
                next_folio = 'Imposible determinarlo para: {0} {1}-{2}'.format('Dr', ejercicio, periodo)
        else:
            data = []
            next_folio = 'valor calculado con la consulta'
            date_from = ''
        return render_template('home/pfacturasdiario.html', data=data, next_folio=next_folio, date_from=date_from)
    except Exception as e:
        print('some error ocurrs:', e)
        return render_template('home/page-500.html', error=e)

@app.route('/pcompras', methods=['GET'])
def polizas_compras():
    # print('params:',request.args)
    date_from = request.args.get('datefrom')
    date_to = request.args.get('dateto')
    if date_from and date_to:
        data = documentos_compra_sae(date_from, date_to)
    else:
        data = []
    doctypescoi = tipos_poliza_coi()
    baseaccounts = cuentas_base()
    doctypessae = [{"TIPO": "C", "DESCRIP":"Compras"}, {"TIPO": "V", "DESCRIP":"Ventas"}]
    divisionscoi = departamentos_coi() 
    lastperiod = ultimo_periodo() 
    return render_template('home/pcompras.html', data=data, doctypescoi=doctypescoi, doctypessae=doctypessae, baseaccounts=baseaccounts, divisionscoi=divisionscoi, lastperiod=lastperiod)

@app.route('/pfacturas', methods=['GET'])
def polizas_facturas():
    try:
        # print('params:',request.args)
        date_from = request.args.get('datefrom')
        date_to = request.args.get('dateto')
        if date_from and date_to:
            data = documentos_venta_sae(date_from, date_to)
            for document in data:
                sum_haber = 0
                for item in document['items']:
                    sum_haber = sum_haber + item['IMPORTE']
                #print('sum of partida.importe0', sum_haber)
                document['IMPORTE'] = round(sum_haber, 2)
            df = datetime.strptime(date_from, '%Y-%m-%d')
            ejercicio = df.year
            periodo = df.month
            folio = siguiente_folio('Dr', ejercicio, periodo)            
            if(folio['folio']>0):
                next_folio = folio['folio']
            else:
                next_folio = 'Imposible determinarlo para: {0} {1}-{2}'.format('Dr', ejercicio, periodo)
        else:
            data = []
            next_folio = ''
        doctypescoi = tipos_poliza_coi()
        baseaccounts = cuentas_base()
        doctypessae = [{"TIPO": "C", "DESCRIP":"Compras"}, {"TIPO": "V", "DESCRIP":"Ventas"}]
        divisionscoi = departamentos_coi() 
        lastperiod = ultimo_periodo() 
        return render_template('home/pfacturas.html', data=data, doctypescoi=doctypescoi, doctypessae=doctypessae, baseaccounts=baseaccounts, divisionscoi=divisionscoi, lastperiod=lastperiod, next_folio=next_folio, date_from=date_from, date_to=date_to)
    except Exception as e:
        return render_template('home/page-500.html', error=e)

@app.route('/ponderado_detalle', methods=['GET'])
def ponderado_detalle():
    try:
        if (request.method=='GET'):
            # print('request.weighted=',request.args.get('weighted'))
            weighted = request.args.get('weighted')
            data = ponderado({'weighted': weighted})                
            if (data):
                # print('===> getting business units')
                units = unidades()
                # print(units)
                #print('sending data to form:\nbase:', len(data), '\nunits: ', len(units))
            else:
                units = []
                data = []
            return render_template('home/ponderado_detalle.html', data=data, businessUnits=units)
    except Exception as e:
        print('Occurs an exception at ponderado_detalle.GET:', e)
        units = []
        data = []
        return render_template('home/page-500.html', error='Error getting data for ponderado_detalle:'+e)

@app.route('/impuestos', methods=['GET'])
def cuentas_impuesto():        
    data = impuestos()
    if (data):
        print('sending data to form data:', len(data))
    else:
        data=[]
    # print('finally the structure is: ', data)
    return render_template('home/impuestos.html', data=data)

@app.route('/ponderados', methods=['GET'])
def ponderaciones():
    try:
        print('request.supplier=',request.args.get('supplier'))
        supplier = request.args.get('supplier')
        concept = request.args.get('concept')
        data = porcentajes({'supplier': supplier, 'concept':concept})
        suppliers = proveedores()
        concepts = conceptos()
        if (data):
            print('sending data to form data:', len(data), 'suppliers:', len(suppliers), 'concepts', len(concepts))        
        else:
            data=[]
            concepts=[]
            suppliers=[]
        # print('finally the structure is: ', data)
        return render_template('home/ponderados.html', data=data, suppliers=suppliers, concepts=concepts)
    except Exception as e:
        error = 'Exception loading ponderaciones: {err}'.format(err=e)
        print(error)        
        return render_template('home/page-500.html', error=error)

@app.route('/', defaults={'path': 'index.html'})
# @app.route('/<path>')
def home(path):
    print('Come to home', path)
    if 'user' in session:
        try:
            return render_template('home/index.html')
        except TemplateNotFound:
            return render_template('home/page-404.html'), 404
    else:
        return redirect(url_for('login'))

@app.route('/logout')
def logout():
    message = "Has salido de la sesión!"
    if ('token' in session):
        token = session['token']
    else:
        token = None
    print('closing session: ', token)
    if (token):        
        not_session = close_session(token)
        print('close session:', not_session)
        message = message + ' Cierre existoso'
    
    session.pop('user', None)
    session.pop('token', None)
    flash(message, "info")
    return redirect(url_for('login'))

if __name__=="__main__":
    #log.info('>>>>> Starting server at http://{}/v1/stats/ <<<<<'.format('0.0.0.0:5000'))  host='0.0.0.0',
    app.run(  port=8080, debug=True )  # debug=True, host='0.0.0.0', port=8080
