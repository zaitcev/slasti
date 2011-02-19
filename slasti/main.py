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

# XXX This is temporary. We'll do pages at root when we have pages.
def root_mark_html(start_response, user, base):
    response_headers = [('Content-type', 'text/html')]
    start_response("200 OK", response_headers)
    output = ["<html><body>\n"]

    output.append('<h1 align="center">')
    output.append(user['name'])
    output.append('</h1>\n')

    for mark in base:
        output.append(mark.html())

    output.append("</body></html>\n")

    return output

# full_mark_html() would be a Netscape bookmarks file, perhaps.
def full_mark_xml(start_response, user, base):
    response_headers = [('Content-type', 'text/xml')]
    start_response("200 OK", response_headers)
    output = []
    output.append('<?xml version="1.0" encoding="UTF-8"?>')
    # <posts user="zaitcev" update="2010-12-16T20:17:55Z" tag="" total="860">
    # We omit total. Also, we noticed that Del.icio.us often miscalculates
    # the total, so obviously it's not used by any applications.
    # We omit the last update as well. Our data base does not keep it.
    output.append('<posts user="'+user['name']+'" tag="">\n')
    for mark in base:
        output.append(mark.xml())
    output.append("</posts>\n")
    return output

#
# Request paths:
#   ''                  -- default index (page.XXXX.XX)
#   page.1296951840.00  -- page off this down
#   export.xml          -- del-compatible XML
#   newmark             -- PUT or POST here (XXX protect)
#   mark.1296951840.00
#   anime/              -- tag (must have slash)
#   anime/page.1293667202.11  -- tag page
#   moo.xml/            -- tricky tag
#   page.1293667202.11/ -- even trickier tag
#
def app(start_response, user, base, reqpath):
    if reqpath == "":
        return root_mark_html(start_response, user, base)
    elif reqpath == "export.xml":
        return full_mark_xml(start_response, user, base)
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
