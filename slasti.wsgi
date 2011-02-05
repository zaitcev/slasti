#
# The WSGI wrapper for Slasti
#
# Copyright (C) 2011 Pete Zaitcev
# See file COPYING for licensing information (expect GPL 2).
#

import json

CFGUSERS = "/etc/slasti-users.conf"

class AppError(Exception):
    pass

class UserBase:
    def __init__(self):
        self.users = None

    def open(self):
        try:
            fp = open(CFGUSERS, 'r')
        except IOError, e:
            raise AppError(str(e))

        try:
            self.users = json.load(fp)
        except ValueError, e:
            raise AppError(str(e))

        fp.close()

        # [{'root': '/var/www/slasti/zaitcev', 'type': 'fs', 'name': 'zaitcev'},
        #  {'root': '/var/www/slasti/piyokun', 'type': 'fs', 'name': 'piyokun'}]

    def close(self):
        pass

def application(environ, start_response):

    # import os, pwd
    # os.environ["HOME"] = pwd.getpwuid(os.getuid()).pw_dir

    # if environ.has_key('mod_wsgi.version'):
    #     output = 'Hello mod_wsgi!'
    # else:
    #     output = 'Hello other WSGI hosting mechanism!'

    # if environ['REQUEST_METHOD'] == 'POST':
    #    start_response('200 OK', [('content-type', 'text/html')])
    #    return ['Hello, ', fields['name'], '!']

    ## typical hello world:
    # status = '200 OK'
    # output = 'Hello World!'
    # response_headers = [('Content-type', 'text/plain'),
    #                     ('Content-Length', str(len(output)))]
    # start_response(status, response_headers)
    # return [output]

    users = UserBase()
    try:
        users.open()
    except AppError, e:
        start_response("500 Internal Error", [('Content-type', 'text/plain')])
        return ["Configuration error: ", str(e)]

    ## Based on James Gardner's environ dump:
    response_headers = [('Content-type', 'text/html')]

    sorted_keys = environ.keys()
    sorted_keys.sort()

    start_response('200 OK', response_headers)

    output = ['<html><body><h1><kbd>environ</kbd></h1><p>']

    for kval in sorted_keys:
        output.append('<br />')
        output.append(kval)
        output.append('=')
        output.append(str(environ[kval]))

    output.append('</p></body></html>')

    users.close()
    return output

# We do not have __main__ in WSGI.
# if __name__.startswith('_mod_wsgi_'):
#    ...
