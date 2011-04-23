#
# Slasti -- the main package
#
# Copyright (C) 2011 Pete Zaitcev
# See file COPYING for licensing information (expect GPL 2).
#

class AppError(Exception):
    pass
class App404Error(Exception):
    pass
class AppGetError(Exception):
    pass

class Context:
    def __init__(self, pfx, user, base, method, path, pinput, coos):
        # prefix: Path where the application is mounted in WSGI or empty string.
        self.prefix = pfx;
        # user: Username.
        self.user = user;
        # base: The open tag database for the user.
        self.base = base;
        # method: The HTTP method (GET, POST, or garbage)
        self.method = method;
        # path: The remaining path after the user. Not the full URL path.
        # This may be empty (we permit user with no trailing slash).
        self.path = path;
        # pinput: The 1 line of input for POST.
        self.pinput = pinput;
        # cookies: Cookie class.
        self.cookies = coos;

import main, tagbase
