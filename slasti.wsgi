#
# The WSGI wrapper for Slasti
#
# Copyright (C) 2011 Pete Zaitcev
# See file COPYING for licensing information (expect GPL 2).
#

import string
import json
import types
import sys

# CFGUSERS was replaced by  SetEnv slasti.userconf /slasti-users.conf
# CFGUSERS = "/etc/slasti-users.conf"

# XXX Learn how to install Python modules. Jeez.
sys.path = sys.path + [ '/usr/lib/slasti-mod' ]
import slasti
from slasti import AppError

# The idea here is the same as with the file-backed tags database:
# something simple to implement but with an API that presumes a higher
# performance implementation later, if necessary.
class UserBase:
    def __init__(self):
        self.users = None

    def open(self, userconf):
        try:
            fp = open(userconf, 'r')
        except IOError, e:
            raise AppError(str(e))

        try:
            self.users = json.load(fp)
        except ValueError, e:
            raise AppError(str(e))

        fp.close()

        # [{ 'name':'zaitcev', 'type':'fs', 'root':'/var/www/slasti/zaitcev' },
        #  { 'name':'piyokun', 'type':'fs', 'root':'/var/www/slasti/piyokun' }]

        # In order to prevent weird tracebacks later, we introspect and make
        # sure that configuration makes sense structurally and that correct
        # fields are present. Using helpful ideas by Andrew "Pixy" Maizels.

        if not (type(self.users) is types.ListType):
            raise AppError("Configuration is not a list [...]")

        for u in self.users:
            if not (type(u) is types.DictType):
                raise AppError("Configured user is not a dictionary {...}")

            if not u.has_key('name'):
                raise AppError("User with no name")
            if not u.has_key('type'):
                raise AppError("User with no type: "+u['name'])
            # Check 'root' for type 'fs' only in the future.
            if not u.has_key('root'):
                raise AppError("User with no root: "+u['name'])

    def lookup(self, name):
        if self.users == None:
            return None
        for u in self.users:
            if u['name'] == name:
                return u
        return None

    def close(self):
        pass

def do_root(environ, start_response):
    # XXX This really needs some kind of a pretty picture.
    start_response("200 OK", [('Content-type', 'text/plain')])
    return ["Slasti: The Anti-Social Bookmarking\r\n",
            "(https://github.com/zaitcev/slasti)\r\n"]

## Based on James Gardner's environ dump.
def do_environ(environ, start_response):
    sorted_keys = environ.keys()
    sorted_keys.sort()

    response_headers = [('Content-type', 'text/html')]
    start_response("200 OK", response_headers)
    output = ["<html><body><h1><kbd>environ</kbd></h1><p>"]

    for kval in sorted_keys:
        output.append("<br />")
        output.append(kval)
        output.append("=")
        output.append(str(environ[kval]))

    output.append("</p></body></html>")

    return output

def do_user(environ, start_response, path):
    # We will stop reloading UserBase on every call once we figure out how.
    users = UserBase()

    if not environ.has_key('slasti.userconf'):
        start_response("500 Internal Error", [('Content-type', 'text/plain')])
        return ["Configuration error: no environ 'slasti.userconf'"]

    try:
        users.open(environ['slasti.userconf'])
    except AppError, e:
        start_response("500 Internal Error", [('Content-type', 'text/plain')])
        return ["Configuration error: ", str(e)]

    # Query is already split away by the CGI.
    parsed = string.split(path, "/", 2)

    user = users.lookup(parsed[1])
    if user == None:
        start_response("404 Not Found", [('Content-type', 'text/plain')])
        return ["No such user: ", parsed[1], "\r\n"]

    response_headers = [('Content-type', 'text/html')]
    start_response("200 OK", response_headers)
    output = ["<html><body>"]

    output.append("<p>")
    # output.append(user.name)
    output.append("</p>")

    output.append("</body></html>")
    users.close()
    return output

def application(environ, start_response):

    # import os, pwd
    # os.environ["HOME"] = pwd.getpwuid(os.getuid()).pw_dir

    # XXX This is incorrect. Must indentify existing resource or 404 first.
    if environ['REQUEST_METHOD'] != 'GET':
        start_response("405 Method Not Allowed",
                         [('Content-type', 'text/plain'),
                          ('Allow', 'GET')])
        return ["Method not allowed: ", environ['REQUEST_METHOD']]

    path = environ['PATH_INFO']
    if path == None or path == "" or path == "/":
        return do_root(environ, start_response)
    elif path == "/environ":
        return do_environ(environ, start_response)
    else:
        return do_user(environ, start_response, path)

# We do not have __main__ in WSGI.
# if __name__.startswith('_mod_wsgi_'):
#    ...
