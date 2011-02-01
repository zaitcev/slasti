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
from xml.etree import ElementTree

TAG = "del2sla"

#def process(...):
#    ......

def Usage():
    print >>sys.stderr, "Usage: "+TAG+" target_dir bookmarks.xml"
    sys.exit(1)

def main(args):
    argc = len(args)
    if argc == 2:
        dirname = args[0]
        xmlname = args[1]
    else:
        Usage()

    #try:
    #    process(...)
    #except EnvironmentError, e:
    #    die("OS problem: "+str(e))
    #except MyError, e:
    #    die(str(e))
    print "moo"

# http://utcc.utoronto.ca/~cks/space/blog/python/ImportableMain
if __name__ == "__main__":
    main(sys.argv[1:])
