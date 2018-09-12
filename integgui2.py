#! /usr/bin/env python
#
# Eric Jeschke (eric@naoj.org)
#

# Standard library imports
import sys, os
from optparse import OptionParser

from g2base import ssdlog

from Gen2.integgui2.main import main

if __name__ == '__main__':

    usage = "usage: %prog [options]"
    optprs = OptionParser(usage=usage, version=('%%prog'))

    optprs.add_option("--debug", dest="debug", default=False,
                      action="store_true",
                      help="Enter the pdb debugger on main()")
##     optprs.add_option("-c", "--channels", dest="channels", default='g2task',
##                       metavar="LIST",
##                       help="Subscribe to the comma-separated LIST of channels")
    optprs.add_option("--display", dest="display", metavar="HOST:N",
                      help="Use X display on HOST:N")
    optprs.add_option("--fitsdir", dest="fitsdir",
                      metavar="DIR",
                      help="Specify DIR to look for FITS files")
    optprs.add_option("-g", "--geometry", dest="geometry",
                      metavar="GEOM", default="1860x1100+57+0",
                      help="X geometry for initial size and placement")
    optprs.add_option("-i", "--inst", dest="instrument",
                      help="Specify instrument(s) to use for integgui")
    optprs.add_option("-m", "--monitor", dest="monitor", default='monitor',
                      metavar="NAME",
                      help="Subscribe to feeds from monitor service NAME")
    optprs.add_option("--monname", dest="monname", metavar="NAME",
                      help="Use NAME as our monitor subscriber name")
    optprs.add_option("-p", "--path", dest="monpath", default='mon.sktask',
                      metavar="PATH",
                      help="Show values for PATH in monitor")
    optprs.add_option("--monport", dest="monport", type="int", default=10017,
                      help="Register monitor using PORT", metavar="PORT")
    optprs.add_option("--numthreads", dest="numthreads", type="int",
                      default=50,
                      help="Start NUM threads in thread pool", metavar="NUM")
    optprs.add_option("--port", dest="port", type="int", default=12050,
                      help="Register using PORT", metavar="PORT")
    optprs.add_option("--profile", dest="profile", action="store_true",
                      default=False,
                      help="Run the profiler on main()")
    optprs.add_option("--session", dest="session", metavar="NAME",
                      help="Configure from session NAME")
    optprs.add_option("--svcname", dest="svcname", metavar="NAME",
                      default="integgui0",
                      help="Register using NAME as service name")
    optprs.add_option("--taskmgr", dest="taskmgr", metavar="NAME",
                      default='taskmgr0',
                      help="Connect to TaskManager with name NAME")
    ssdlog.addlogopts(optprs)


    (options, args) = optprs.parse_args(sys.argv[1:])

##     if len(args) != 0:
##         optprs.error("incorrect number of arguments")

    if options.display:
        os.environ['DISPLAY'] = options.display

    # Are we debugging this?
    if options.debug:
        import pdb

        pdb.run('main(options, args)')

    # Are we profiling this?
    elif options.profile:
        import profile

        print("%s profile:" % sys.argv[0])
        profile.run('main(options, args)')

    else:
        main(options, args)

#END
