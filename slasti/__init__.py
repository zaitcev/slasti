#
# Slasti -- the main package
#
# Copyright (C) 2011 Pete Zaitcev
# See file COPYING for licensing information (expect GPL 2).
#

import urllib

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
    if isinstance(u, unicode):
        return u.encode('utf-8')
    return u

def escapeURLComponent(s):
    # Turn s into a bytes first, quote_plus blows up otherwise
    return unicode(urllib.quote_plus(s.encode("utf-8")))

class Context:
    def __init__(self, pfx, user, base, method, path, query, pinput, coos):
        # prefix: Path where the application is mounted in WSGI or empty string.
        self.prefix = pfx
        # user: Username.
        self.user = user
        # base: The open tag database for the user.
        self.base = base
        # method: The HTTP method (GET, POST, or garbage)
        self.method = method
        # path: The remaining path after the user. Not the full URL path.
        # This may be empty (we permit user with no trailing slash).
        self.path = path
        # query: The query string
        self.query = query
        # pinput: The 1 line of input for POST.
        self.pinput = pinput
        # cookies: Cookie class. May be None.
        self.cookies = coos
        # flogin: Login flag, to be derived from self.user and self.cookies.
        self.flogin = 0

    def create_jsondict(self):
        userpath = self.prefix+'/'+self.user['name']

        jsondict = {"name_user": self.user["name"],
                    "href_user": userpath,
                    "href_tags": "%s/tags" % userpath,
                    "href_new": "%s/new" % userpath,
                   }
        if self.flogin:
            jsondict["href_export"]= userpath + '/export.xml'
            jsondict["href_login"] = None
        else:
            jsondict["href_export"]= None
            jsondict["href_login"] = "%s/login" % userpath
            if self.path and self.path != "login" and self.path != "edit":
                jsondict["href_login"] += '?savedref=%s' % self.path
        return jsondict

import main, tagbase
