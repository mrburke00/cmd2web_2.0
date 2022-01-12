#!//usr/bin/env python
import subprocess
import json
import sys
from flask import Flask,request,send_file,abort,Response
import argparse
import io
import re
import random
import cmd2web
from werkzeug.datastructures import ImmutableDict
from flask import render_template
from OpenSSL import SSL
import os
parse = os.path.abspath('parse_src')
sys.path.insert(1,parse)
import fortran_wrapper
app = Flask(__name__, template_folder = "web_src/template", static_folder="web_src/static", static_url_path='')

config = None
server = None
timeout=10
add_accesss_control = True

@app.after_request
def after_request(response):
    if add_accesss_control:
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers',
                             'Content-Type,Authorization')
        response.headers.add('Access-Control-Allow-Methods',
                             'GET,PUT,POST,DELETE,OPTIONS')
    return response

@app.route('/info')
def info():
    return json.dumps(server.get_info())

@app.route('/parse', methods=['GET', 'POST'])
def index():
    data = ""
    file_data = ""
    sequence = ""
    file_input = False
    if request.method == "POST": # if form has been posted
        sequence = request.form.get("sequence")
        if not sequence:
            try: 
                file_data = request.files['file'].read()

            except: 
                print('1')
                return cmd2web.Server.error('File failed to open')
            args = request.args.to_dict()
            args['service'] = 'parse'
            tmp = str(file_data)
            sequence = tmp[2:-1]
            args['sequence'] = sequence ## this will need to change when handling multiple sequences
            request.args = args
            file_input = True
        else:
            args = request.args.to_dict()
            args['service'] = 'parse' # add service argument
            args['sequence'] = sequence # add sequence argument from form 
            request.args = args
        data = service(file_input=file_input)
    # still need to handle files 
    return render_template('parse.html', jsonfile=data)

@app.route('/')
def service(file_input):
    service = request.args.get('service')
    if not service:
        print('1')
        return cmd2web.Server.error('No service specified')

    if not server.has_service(service):
        print('2')
        return cmd2web.Server.error('Unknown service')

    if not server.services[service].args_match(request.args):
        print('3')
        return cmd2web.Server.error('Argument mismatch')

    service_instance = server.services[service].copy()

    try:
        cmd = service_instance.make_cmd(request.args)
    except Exception as e:
        print(e)
        return cmd2web.Server.error(str(e))

    #print(' '.join(cmd))
    print("file_input", file_input)
    if file_input: ## this only handles one sequence 
        f_cmd = " ".join(cmd)
        print(f_cmd)
        return fortran_wrapper.fortran_wrap_file_single(f_cmd)

    out_file_name = '/tmp/' + str(random.randint(0,sys.maxsize)) + '.out'
    f_cmd = " ".join(cmd)
    f = open(out_file_name, 'w')




    try:
        os.system(f_cmd + ' > ' + out_file_name)
        #proc = subprocess.check_call(cmd,
        #                             stderr=sys.stderr,
        #                             stdout=f,
        #                             timeout=timeout)
    except subprocess.TimeoutExpired as e:
        print('Time Out')
        return cmd2web.Server.error('Time limit for current request exceed.')
    #except Exception as e:
    #    print("shit")
    #    return cmd2web.Server.error(str(e))

    f.close()

    return service_instance.process_result(out_file_name, script = service)

if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='command to web server.')

    parser.add_argument('--config',
                        dest='config',
                        required=True,
                        help='Configuration file.')

    parser.add_argument('--port',
                        dest='port',
                        type=int,
                        default="8080",
                        help='Port to run on (default 8080)')

    parser.add_argument('--host',
                        dest='host',
                        default="127.0.0.1",
                        help='Server hos (default 127.0.0.1)')

    parser.add_argument('--timeout',
                        dest='timeout',
                        type=int,
                        default=10,
                        help='Max runtime (sec) for a command (default 10)')

    parser.add_argument('--ssl_key',
                        dest='ssl_key',
                        help='Path to the SSL key')

    parser.add_argument('--ssl_cert',
                        dest='ssl_cert',
                        help='Path to the SSL key')

    parser.add_argument('--no_access_control_header',
                        dest='no_access_control_header',
                        action='store_true',
                        help='Path to the SSL key')

    args = parser.parse_args()
    timeout = args.timeout
    server = cmd2web.Server.load(args.config)

    if args.no_access_control_header:
        add_accesss_control = False


    if args.ssl_key and args.ssl_cert:
        context = SSL.Context(SSL.SSLv23_METHOD)
        context.use_privatekey_file('yourserver.key')
        context.use_certificate_file('yourserver.crt')
        try:
            app.run(host=args.host, port=args.port, ssl_context=context)
        except Exception as e:
            sys.exit('ERROR starting the server. "' + str(e) + '"')
    else:
        try:
            app.run(host=args.host, port=args.port)
        except Exception as e:
            sys.exit('ERROR starting the server. "' + str(e) + '"')
