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
import calendar
from xml.etree import ElementTree

# N.B. This includes app-level generics such as AppError. Any better ideas?
import slasti
from slasti import AppError

TAG = "del2sla"

def Usage():
    print >>sys.stderr, "Usage: "+TAG+" target_dir bookmarks.xml"
    sys.exit(2)

# We are not aware of any specification, so it is unclear if tags are split
# by space or whitespace. We assume space, to be locale-independent.
# But this means that we include tabs and foreign whitespace into tags.
def split_tags(tagstr):
    tags = []
    for t in tagstr.split(' '):
        if t != '':
            tags.append(t)
    return tags

def verify_tags(tagstr):
    if "/" in tagstr:
        return 0
    if "\n" in tagstr:
        return 0
    return 1

def verify_attr(attrstr):
    if "\n" in attrstr:
        return 0
    return 1

# XXX The add1 has a big problem with DB consistency in case of errors:
# if any mark problem causes us to abort, user cannot re-run with
# minimal fixes to the set: the database will receive a bunch of dups.
# We need either detect dups or somehow roll back everything we added.

def do(dirname, xmlname):
    base = slasti.tagbase.TagBase(dirname)

    base.open()

    try:
        # Verify XML has UTF-8 encoding perhaps?
        etree = ElementTree.parse(xmlname)
    except IOError as e:
        raise AppError(str(e))
    except ElementTree.ParseError as e:
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
        tagstr = et.attrib.get('tag')
        if tagstr == None:
            continue
        # not sure what to do with hash and meta
        # 'hash' is MD5 digest of URL
        #hash = et.attrib.get('hash')
        #meta = et.attrib.get('meta')
        note = et.attrib.get('extended')
        if note == None:
            note = ""

        if not verify_attr(title):
            raise AppError("Invalid title: `"+title+"'")
        if not verify_attr(url):
            raise AppError("Invalid URL: `"+url+"'")
        if not verify_attr(note):
            raise AppError("Invalid note: `"+note+"'")

        if not verify_tags(tagstr):
            raise AppError("Invalid tags: `"+tagstr+"'")
        tags = split_tags(tagstr)
        if tags == []:
            continue

        #time="2010-12-10T08:04:46Z"
        timestr = et.attrib.get('time')
        if timestr == None:
            # We could create fake dates, but that would be just wrong.
            continue

        try:
            timeval = time.strptime(timestr, "%Y-%m-%dT%H:%M:%SZ")
        except ValueError as e:
            # We bug out on this because this case may be worth diagnosing.
            # The error message has both format and unparsed date string.
            raise AppError(str(e))
        if timeval == None:
            continue

        try:
            timeint = calendar.timegm(timeval)
        except (ValueError, OverflowError) as e:
            # XXX A user supplied Year 1900 or something like that.
            print e
            continue

        base.add1(timeint, title, url, note, tags)

    base.close()

def main(args):
    argc = len(args)
    if argc == 2:
        dirname = args[0]
        xmlname = args[1]
    else:
        Usage()

    try:
        do(dirname, xmlname)
    except AppError as e:
        print >>sys.stderr, TAG+":", e
        sys.exit(1)

# http://utcc.utoronto.ca/~cks/space/blog/python/ImportableMain
if __name__ == "__main__":
    main(sys.argv[1:])
