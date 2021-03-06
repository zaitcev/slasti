#
# The WSGI wrapper for Slasti
#
# Copyright (C) 2011 Pete Zaitcev
# See file COPYING for licensing information (expect GPL 2).
#

import json
# import sys
import six
from six.moves import http_cookies

# CFGUSERS was replaced by  SetEnv slasti.userconf /slasti-users.conf
# CFGUSERS = "/etc/slasti-users.conf"

# Replaced by  WSGIDaemonProcess slasti python-path=/usr/lib/slasti-mod
# sys.path = sys.path + [ '/usr/lib/slasti-mod' ]

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
        except IOError as e:
            raise AppError(str(e))

        try:
            self.users = json.load(fp)
        except ValueError as e:
            raise AppError(str(e))

        fp.close()

        # In order to prevent weird tracebacks later, we introspect and make
        # sure that configuration makes sense structurally and that correct
        # fields are present. Using helpful ideas by Andrew "Pixy" Maizels.

        if not isinstance(self.users, list):
            raise AppError("Configuration is not a list [...]")

        for u in self.users:
            if not isinstance(u, dict):
                raise AppError("Configured user is not a dictionary {...}")

            if 'name' not in u:
                raise AppError("User with no name")
            if 'type' not in u:
                raise AppError("User with no type: "+u['name'])
            # Check 'root' for type 'fs' only in the future.
            if 'root' not in u:
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
    # This has to be implemented when close() becomes non-empty, due to
    # the way AppError bubbles up and bypasses the level where we close.
    #def __del__(self):
    #    pass

def do_root(environ, start_response):
    method = environ['REQUEST_METHOD']
    if method == 'GET':
        start_response("200 OK", [('Content-type', 'text/plain')])
        return [b"Slasti: The Anti-Social Bookmarking\r\n",
                b"(https://github.com/zaitcev/slasti)\r\n"]
    if method == 'HEAD':
        start_response("200 OK", [('Content-type', 'text/plain')])
        return [b'']
    raise slasti.AppGetHeadError(method)

def do_user(environ, start_response, path):
    # We will stop reloading UserBase on every call once we figure out how.
    users = UserBase()
    if 'slasti.userconf' not in environ:
        raise AppError("No environ 'slasti.userconf'")
    users.open(environ['slasti.userconf'])

    # The prefix must be either empty or absolute (no relative or None).
    pfx = environ['SCRIPT_NAME']
    if pfx == None or pfx == "/":
        pfx = ""
    if pfx != "" and pfx[0] != "/":
        pfx = "/"+pfx

    method = environ['REQUEST_METHOD']
    if method == 'POST':
        try:
            clen = int(environ["CONTENT_LENGTH"])
        except (KeyError, ValueError):
            pinput = environ['wsgi.input'].readline()
        else:
            pinput = environ['wsgi.input'].read(clen)
        # Every Unicode-in-Python preso on the Internet says to decode on the
        # border. However, this is actually disastrous, because pinput may be
        # uuencoded. It we decode it here, parse_qs returns a dictionary of
        # unicode strings, which contain split-up UTF-8 bytes, and then we're
        # dead in the water. So, don't do this.
        #if not isinstance(pinput, unicode):
        #    try:
        #        pinput = unicode(pinput, 'utf-8')
        #    except UnicodeDecodeError:
        #        start_response("400 Bad Request",
        #                       [('Content-type', 'text/plain')])
        #        return ["400 Unable to decode UTF-8 in POST\r\n"]
    else:
        pinput = None

    scheme = environ['wsgi.url_scheme']
    netloc = environ['HTTP_HOST']

    # Query is already split away by the CGI.
    parsed = path.split("/", 2)

    user = users.lookup(parsed[1])
    if user == None:
        raise slasti.App404Error("No such user: "+parsed[1])
    if user['type'] != 'fs':
        raise AppError("Unknown type of user: "+parsed[1])

    if len(parsed) >= 3:
        path = parsed[2]
    else:
        path = ""

    try:
        q = environ['QUERY_STRING']
    except KeyError:
        q = None

    c = http_cookies.SimpleCookie()
    try:
        c.load(environ['HTTP_COOKIE'])
    except http_cookies.CookieError as e:
        start_response("400 Bad Request", [('Content-type', 'text/plain')])
        return [b"400 Bad Cookie: "+slasti.safestr(six.text_type(e))+b"\r\n"]
    except KeyError:
        c = None

    ims_ts = slasti.ims_make_ts(environ.get('HTTP_IF_MODIFIED_SINCE'))

    base = slasti.tagbase.TagBase(user['root'])
    base.open()

    ctx = slasti.Context(pfx, user, base,
                         method, scheme, netloc, path,
                         q, pinput, c, ims_ts)
    output = slasti.main.app(start_response, ctx)

    base.close()
    return output

def error_return(environ, return_iter):
    return [b''] if environ['REQUEST_METHOD'] == 'HEAD' else return_iter

def error_bad_method(environ, start_response, e, ok_methods):
    start_response("405 Method Not Allowed",
                   [('Content-type', 'text/plain'), ('Allow', ok_methods)])
    return error_return(
        environ,
        [b"405 Method %s not allowed\r\n" %
         slasti.safestr(six.text_type(e))])

def application(environ, start_response):

    # import os, pwd
    # os.environ["HOME"] = pwd.getpwuid(os.getuid()).pw_dir

    path = environ['PATH_INFO']
    if six.PY2:
        if isinstance(path, basestring) and not isinstance(path, unicode):
            try:
                path = unicode(path, 'utf-8')
            except UnicodeDecodeError:
                start_response("400 Bad Request",
                               [('Content-type', 'text/plain')])
                return error_return(
                    environ,
                    ["400 Unable to decode UTF-8 in path\r\n"])
    else:
        # Graham Dumpleton talks about wsgi.path_info and wsgi.uri_encoding,
        # but none of them actually exist: it's identity encoding for the URL
        # and nothing else.
        path = path.encode('latin-1')
        try:
            path = path.decode('utf-8')
        except UnicodeDecodeError:
            start_response("400 Bad Request",
                           [('Content-type', 'text/plain')])
            return error_return(
                environ, [b"400 Unable to decode UTF-8 in path\r\n"])

    try:
        if path == None or path == "" or path == "/":
            output = do_root(environ, start_response)
        else:
            output = do_user(environ, start_response, path)
        return output

    except AppError as e:
        start_response("500 Internal Error", [('Content-type', 'text/plain')])
        return error_return(
            environ, [slasti.safestr(six.text_type(e)), b"\r\n"])
    except slasti.App400Error as e:
        start_response("400 Bad Request", [('Content-type', 'text/plain')])
        return error_return(
            environ,
            [b"400 Bad Request: %s\r\n" % slasti.safestr(six.text_type(e))])
    except slasti.AppLoginError as e:
        start_response("403 Not Permitted", [('Content-type', 'text/plain')])
        return error_return(environ, [b"403 Not Logged In\r\n"])
    except slasti.App404Error as e:
        start_response("404 Not Found", [('Content-type', 'text/plain')])
        return error_return(
            environ, [slasti.safestr(six.text_type(e))+b"\r\n"])
    except slasti.AppGetError as e:
        return error_bad_method(environ, start_response, e, 'GET')
    except slasti.AppGetHeadError as e:
        return error_bad_method(environ, start_response, e, 'GET, HEAD')
    except slasti.AppPostError as e:
        return error_bad_method(environ, start_response, e, 'POST')
    except slasti.AppGetPostError as e:
        return error_bad_method(environ, start_response, e, 'GET, POST')
    except slasti.AppGetHeadPostError as e:
        return error_bad_method(environ, start_response, e, 'GET, POST, HEAD')

# We do not have __main__ in WSGI.
# if __name__.startswith('_mod_wsgi_'):
#    ...
