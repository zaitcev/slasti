#
# Slasti -- Main Application
#
# Copyright (C) 2011 Pete Zaitcev
# See file COPYING for licensing information (expect GPL 2).
#

import string

from slasti import AppError

def page_mark_html(start_response, user, base, stamp0, stamp1):
    start_response("200 OK", [('Content-type', 'text/plain')])
    return ["Page not wokrie yet: ", str(stamp0)+"."+str(stamp1), "\r\n"]

#
# Request paths:
#   ''                  -- default index (page.XXXX.XX)
#   page.1296951840.00  -- page off this down
#   export.xml          -- del-compatible XML
#   newmark             -- PUT or POST here (XXX protect)
#   anime/              -- tag (must have slash)
#   anime/page.1293667202.11  -- tag page
#   moo.xml/            -- tricky tag
#   page.1293667202.11/ -- even trickier tag
#
def app(start_response, user, base, reqpath):

    if reqpath == "":
        pass
    elif reqpath == "export.xml":
        pass
    elif reqpath == "newmark":
        start_response("403 Not Permitted", [('Content-type', 'text/plain')])
        return ["New mark does not work yet\r\n"]
    elif "/" in reqpath:
        # p = string.split(reqpath, "/", 1)
        # tag = p[0]
        # page = p[1]
        # p = string.split(page, ".")
        # if len(p) != 3 or p[0] != "page":
        #     start_response("404 Not Found", [('Content-type', 'text/plain')])
        #     return ["Not found: ", reqpath, "\r\n"]
        # try:
        #     stamp0 = int(p[1])
        #     stamp1 = int(p[2])
        # except ValueError:
        #     start_response("404 Not Found", [('Content-type', 'text/plain')])
        #     return ["Not found: ", reqpath, "\r\n"]
        # return page_tag_html(user, base, tag, stamp0, stamp1)
        start_response("404 Not Found", [('Content-type', 'text/plain')])
        return ["Tag not supported yet: ", reqpath, "\r\n"]
    else:
        p = string.split(reqpath, ".")
        if len(p) != 3 or p[0] != "page":
            start_response("404 Not Found", [('Content-type', 'text/plain')])
            return ["Not found: ", reqpath, "\r\n"]
        try:
            stamp0 = int(p[1])
            stamp1 = int(p[2])
        except ValueError:
            start_response("404 Not Found", [('Content-type', 'text/plain')])
            return ["Not found: ", reqpath, "\r\n"]
        return page_mark_html(start_response, user, base, stamp0, stamp1)

    response_headers = [('Content-type', 'text/html')]
    start_response("200 OK", response_headers)
    output = ["<html><body>"]

    output.append('<h1 align="center">')
    output.append(user['name'])
    output.append('</h1>')

    for mark in base:
        output.append(mark.html())

    output.append("</body></html>")

    return output
