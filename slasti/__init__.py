#
# Slasti -- the main package
#
# Copyright (C) 2011 Pete Zaitcev
# See file COPYING for licensing information (expect GPL 2).
#

import six
from six.moves.urllib.parse import parse_qs, quote, quote_plus


class AppError(Exception):
    pass
class App400Error(Exception):
    pass
class AppLoginError(Exception):
    pass
class App404Error(Exception):
    pass
class AppGetError(Exception):
    pass
class AppPostError(Exception):
    pass
class AppGetPostError(Exception):
    pass


def safestr(u):
    if isinstance(u, six.text_type):
        return u.encode('utf-8')
    return u

# The to_str() is used to coerce header fields, in case their encoding
# is known correct (meaning, ASCII already -- either base64 or UTF-8+URL).
# The WSGI platform insists they to be str, both on py2 and py3, but we
# may end with either unicode on py2, or bytes on py3. The former happens
# because request headers are upconverted to unicode and then leak through.
# The latter happens because hash, base64, or other libraries insist on
# outputting bytes. Unfortunately, we cannot simply do str(s), because
# that yeilds "b's'".
def to_str(s):
    if not isinstance(s, str):
        if isinstance(s, six.text_type):
            s = s.encode('ascii')
        else:
            s = s.decode('ascii')
    return s

def escapeURLComponent(s):
    if six.PY2:
        # Turn s into a bytes first, quote_plus blows up otherwise
        return quote_plus(s.encode('utf-8')).decode('utf-8')
    else:
        return quote_plus(s)

def escapeURL(s):
    # quote_plus() doesn't work as it clobbers the :// portion of the URL
    # Make sure the resulting string is safe to use within HTML attributes.
    # N.B. Mooneyspace.com hates when we reaplace '&' with %26, so don't.
    # On output, the remaining & will be turned into &amp; by the templating
    # engine. No unescaped-entity problems should result here.
    s = s.replace('"', '%22')
    s = s.replace("'", '%27')
    # s = s.replace('&', '%26')
    s = s.replace('<', '%3C')
    s = s.replace('>', '%3E')
    return s

html_escape_table = {
    ">": "&gt;",
    "<": "&lt;",
    "&": "&amp;",
    '"': "&quot;",
    "'": "&apos;",
    "\\": "&#92;",
    }

def escapeHTML(text):
    """Escape strings to be safe for use anywhere in HTML

    Should be used for escaping any user-supplied strings values before
    outputting them in HTML. The output is safe to use HTML running text and
    within HTML attributes (e.g. value="%s").

    Escaped chars:
      < and >   HTML tags
      &         HTML entities
      " and '   Allow use within HTML tag attributes
      \\        Shouldn't actually be necessary, but better safe than sorry
    """
    # performance idea: compare with cgi.escape-like implementation
    return "".join(html_escape_table.get(c,c) for c in text)


class Context:
    def __init__(self, pfx, user, base, method, scheme, netloc, path,
                 query, pinput, coos):
        # prefix: Path where the application is mounted in WSGI or empty string.
        self.prefix = pfx
        # user: User entry.
        self.user = user
        # base: The open tag database for the user.
        self.base = base
        # method: The HTTP method (GET, POST, or garbage)
        self.method = method
        # scheme: http or https
        self._scheme = scheme
        # netloc: host.domain:port
        self._netloc = netloc
        # path: The remaining path after the user. Not the full URL path.
        # This may be empty (we permit user with no trailing slash).
        self.path = path
        # _query: The query string as bytes. Use get_query_args() to access.
        self._query = query
        # _pinput: The 1 line of input for POST as bytes.
        #          Use get_pinput_args() to access
        self._pinput = pinput
        # cookies: Cookie class. May be None.
        self.cookies = coos
        # flogin: Login flag, to be derived from self.user and self.cookies.
        self.flogin = 0
        # j2env: the jinja2.Environment
        self.j2env = None

        self._query_args = None
        self._pinput_args = None

    def create_jsondict(self):
        userpath = self.prefix+'/'+self.user['name']

        jsondict = {
                    "href_tags": "%s/tags" % userpath,
                    "href_new": "%s/new" % userpath,
                   }

        if self.flogin:
            jsondict["href_export"]= userpath + '/export.xml'
            jsondict["href_login"] = None
            jsondict["hrefa_new"] = \
                    "%s://%s%s/new" % (self._scheme, self._netloc, userpath)
            jsondict["flogin"] = "1"
        else:
            jsondict["href_export"]= None
            jsondict["href_login"] = "%s/login" % userpath
            if self.path and self.path != "login" and self.path != "edit":
                jsondict["href_login"] += '?savedref=%s' % self.path

        userstr = '<a href="%s/">%s</a>' % (userpath, self.user['name'])
        jsondict['_main_path'] = userstr

        jsondict['_page_prev'] = "-"
        jsondict['_page_this'] = "-"
        jsondict['_page_next'] = "-"

        return jsondict

    def _parse_args(self, args):
        if args is None:
            return {}

        # The parse_qs() will parse %-escapes incorrectly if in unicode, but
        # naked UTF-8 makes it blow up on py3. Solution: first make everything
        # bytes, then %-encode all 8-bit characters, while leaving all the
        # relevant syntax alone.
        if isinstance(args, six.text_type):
            args = args.encode('utf-8')
        args = quote(args, '%&=+')

        qdic = dict()
        qdic_ = parse_qs(args)
        for key in qdic_:
            val = qdic_[key][0]

            key = to_str(key)

            if isinstance(val, six.binary_type):
                val = val.decode('utf-8', 'replace')

            qdic[key] = val

        return qdic

    def get_query_arg(self, argname):
        if self._query_args is None:
            self._query_args = self._parse_args(self._query)
        return self._query_args.get(argname, None)

    def get_pinput_arg(self, argname):
        if self._pinput_args is None:
            self._pinput_args = self._parse_args(self._pinput)
        return self._pinput_args.get(argname, None)


import slasti.main, slasti.tagbase
