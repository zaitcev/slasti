#
# Slasti -- Main Application
#
# Copyright (C) 2011 Pete Zaitcev
# See file COPYING for licensing information (expect GPL 2).
#

import string
import time

from slasti import AppError

PAGESZ = 25

BLACKSTAR = "&#9733;"
WHITESTAR = "&#9734;"

def page_back(mark):
    mark = mark.pred()
    if mark == None:
        return None
    # In all other cases, we'll return something, even if 1 entry back.
    n = 1
    while n < PAGESZ:
        m = mark.pred()
        if m == None:
            return mark
        mark = m
        n += 1
    return mark

def page_anchor_html(mark, path, text):
    if mark == None:
        return '[-]'
    (stamp0, stamp1) = mark.key()
    return '[<a href="%s/page.%d.%02d">%s</a>]' % (path, stamp0, stamp1, text)

def mark_anchor_html(mark, path, text):
    if mark == None:
        return '[-]'
    (stamp0, stamp1) = mark.key()
    return '[<a href="%s/mark.%d.%02d">%s</a>]' % (path, stamp0, stamp1, text)

def page_mark_html(start_response, pfx, user, base, stamp0, stamp1):
    mark_top = base.lookup(stamp0, stamp1)
    if mark_top == None:
        # We have to have at least one mark to display a page
        start_response("404 Not Found", [('Content-type', 'text/plain')])
        return ["Page not found: ", str(stamp0), str(stamp1), "\r\n"]

    path = pfx+'/'+user['name']

    start_response("200 OK", [('Content-type', 'text/html')])
    output = ["<html><body>\n"]

    # align=center does not match individual mark's style
    output.append('<h1><a href="%s/">%s</a> / %s</h1>\n' % \
             (path, user['name'], page_anchor_html(mark_top, path, BLACKSTAR)))

    mark = mark_top
    mark_next = None
    n = 0
    while n < PAGESZ:
        (stamp0, stamp1) = mark.key()
        datestr = time.strftime("%Y-%m-%d", time.gmtime(stamp0))

        output.append("<p>%s %s " % \
                      (datestr, mark_anchor_html(mark, path, WHITESTAR)))
        output.append(mark.html())
        output.append("</p>\n")

        mark_next = mark.succ()
        if mark_next == None:
            break
        mark = mark_next
        n += 1

    output.append("<hr />\n")
    output.append(page_anchor_html(page_back(mark_top), path, "&laquo;"))
    output.append(page_anchor_html(mark_top,            path, BLACKSTAR))
    output.append(page_anchor_html(mark_next,           path, "&raquo;"))
    output.append("<br />\n")

    output.append("</body></html>\n")
    return output

def page_empty_html(start_response, pfx, user, base):
    path = pfx+'/'+user['name']

    start_response("200 OK", [('Content-type', 'text/html')])
    output = ["<html><body>\n"]

    output.append('<h1>')
    output.append(user['name'])
    output.append(' / [-]</h1>\n')

    output.append("<hr />\n")
    output.append('[-] [-] [-]')
    output.append("<br />\n")

    output.append("</body></html>\n")
    return output

def one_mark_html(start_response, pfx, user, base, stamp0, stamp1):
    mark = base.lookup(stamp0, stamp1)
    if mark == None:
        start_response("404 Not Found", [('Content-type', 'text/plain')])
        return ["Mark not found: ", str(stamp0), str(stamp1), "\r\n"]

    path = pfx+'/'+user['name']

    start_response("200 OK", [('Content-type', 'text/html')])
    output = ["<html><body>\n"]

    output.append('<h1><a href="%s/">%s</a></h1>\n' % (path, user['name']))

    output.append("<p>")
    datestr = time.strftime("%Y-%m-%d", time.gmtime(stamp0))
    output.append(datestr)
    output.append("<br />\n")
    output.append(mark.html())
    output.append("</p>\n")

    output.append("<hr />\n")
    output.append(mark_anchor_html(mark.pred(), path, "&laquo;"))
    output.append(mark_anchor_html(mark,        path, WHITESTAR))
    output.append(mark_anchor_html(mark.succ(), path, "&raquo;"))
    output.append("<br />\n")

    output.append("</body></html>\n")
    return output

def root_mark_html(start_response, pfx, user, base):
    mark = base.first()
    if mark == None:
        return page_empty_html(start_response, pfx, user, base)
    (stamp0, stamp1) = mark.key()
    return page_mark_html(start_response, pfx, user, base, stamp0, stamp1)

    ## The non-paginated version
    #
    # response_headers = [('Content-type', 'text/html')]
    # start_response("200 OK", response_headers)
    # output = ["<html><body>\n"]
    #
    # # align=center does not match individual mark's style
    # output.append('<h1>')
    # output.append(user['name'])
    # output.append('</h1>\n')
    #
    # for mark in base:
    #     (stamp0, stamp1) = mark.key()
    #     datestr = time.strftime("%Y-%m-%d", time.gmtime(stamp0))
    #
    #     output.append("<p>%s %s " % \
    #                   (datestr, mark_anchor_html(mark, path, WHITESTAR)))
    #     output.append(mark.html())
    #     output.append("</p>\n")
    #
    # output.append("</body></html>\n")
    # return output

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
#   mark.1296951840.00
#   export.xml          -- del-compatible XML
#   newmark             -- PUT or POST here (XXX protect)
#   anime/              -- tag (must have slash)
#   anime/page.1293667202.11  -- tag page
#   moo.xml/            -- tricky tag
#   page.1293667202.11/ -- even trickier tag
#
def app(start_response, pfx, user, base, reqpath):
    if reqpath == "":
        return root_mark_html(start_response, pfx, user, base)
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
        if len(p) != 3:
            start_response("404 Not Found", [('Content-type', 'text/plain')])
            return ["Not found: ", reqpath, "\r\n"]
        try:
            stamp0 = int(p[1])
            stamp1 = int(p[2])
        except ValueError:
            start_response("404 Not Found", [('Content-type', 'text/plain')])
            return ["Not found: ", reqpath, "\r\n"]
        if p[0] == "mark":
            return one_mark_html(start_response, pfx, user, base, stamp0, stamp1)
        if p[0] == "page":
            return page_mark_html(start_response, pfx, user, base, stamp0, stamp1)
        start_response("404 Not Found", [('Content-type', 'text/plain')])
        return ["Not found: ", reqpath, "\r\n"]
