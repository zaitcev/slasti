#
# Import XML from Del.icio.us into Slasti
#
# Copyright (C) 2011 Pete Zaitcev
# See file COPYING for licensing information (expect GPL 2).
#
# requires:
#  ElementTree as built into Python 2.7 (xml.etree)
#

import sys
import time
from xml.etree import ElementTree

TAG = "del2sla"

def Usage():
    print >>sys.stderr, "Usage: "+TAG+" target_dir bookmarks.xml"
    sys.exit(2)

class AppError(Exception):
    pass

#
# The open database (any back-end in theory, hardcoded files for now)
#
class TagBase:
    def __init__(self, dirname0):
        d = dirname0
        if len(d) > 1 and d[-1] == '/':
            d = dirname0[:-1]
        self.dirname = d

def do(dirname, xmlname):
    base = TagBase(dirname)

    try:
        # Verify XML has UTF-8 encoding perhaps?
        etree = ElementTree.parse(xmlname)
    except IOError, e:
        raise AppError(str(e))
    except ElementTree.ParseError, e:
        raise AppError(xmlname+": "+str(e))
    etroot = etree.getroot()
    if etroot == None:
        raise AppError(xmlname+": No root element")
    if etroot.tag != 'posts':
        raise AppError(xmlname+": root is not `posts'")

    for et in etroot:
        if et.tag != 'post':
            continue
        title = et.attrib.get('description')
        if title == None:
            continue
        url = et.attrib.get('href')
        if url == None:
            continue
        # 'tag' is a string of space-separated tags
        tags = et.attrib.get('tag')
        if tags == None:
            continue
        # not sure what to do with hash and meta
        # 'hash' is MD5 digest of URL
        #hash = et.attrib.get('hash')
        #meta = et.attrib.get('meta')
        note = et.attrib.get('extended')
        if note == None:
            note = ""

        #time="2010-12-10T08:04:46Z"
        timestr = et.attrib.get('time')
        if timestr == None:
            # We could create fake dates, but that would be just wrong.
            continue

        try:
            timeval = time.strptime(timestr, "%Y-%m-%dT%H:%M:%SZ")
        except ValueError, e:
            # XXX This may be worth the trouble to diagnose somehow
            # P3
            print e
            timeval = None
        if timeval == None:
            continue

        try:
            timeint = int(time.mktime(timeval))
        except (ValueError, OverflowError), e:
            print e
            continue

        # XXX base.add(timeint*xxxxx, url, tags)


def main(args):
    argc = len(args)
    if argc == 2:
        dirname = args[0]
        xmlname = args[1]
    else:
        Usage()

    try:
        do(dirname, xmlname)
    #except EnvironmentError, e:
    #    die("OS problem: "+str(e))
    except AppError, e:
        print >>sys.stderr, TAG+":", e
        sys.exit(1)

# http://utcc.utoronto.ca/~cks/space/blog/python/ImportableMain
if __name__ == "__main__":
    main(sys.argv[1:])
