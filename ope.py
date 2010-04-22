#!/usr/bin/env python
#
# ope.py -- helper code for processing legacy OPE (observation) files
#
#[ Eric Jeschke (eric@naoj.org) --
#  Last edit: Tue Apr 20 23:02:32 HST 2010
#]
#
# remove once we're certified on python 2.6
from __future__ import with_statement

import re, sys, os
import pprint
import Bunch

class OPEerror(Exception):
    pass

# OPE file regex
pattern1 = re.compile(r'^.*\<HEADER\>(.*)\</HEADER\>\s*'
'\<PARAMETER_LIST\>(.*)\</PARAMETER_LIST\>\s*'
'\<COMMAND\>\s*(.+)\s*\</COMMAND\>\s*$',
re.MULTILINE | re.DOTALL | re.IGNORECASE)

# CD file regex
pattern2 = re.compile(r'^\s*\<COMMAND\>\s*(.+)\s*\</COMMAND\>\s*$',
                      re.MULTILINE | re.DOTALL)

# PRM includes regex
pattern3 = re.compile(r'^\*LOAD\s*"(.+)"\s*$', re.IGNORECASE)


def toupper(s):
    """Function to convert a string to upper case, preserving
    case inside quotes.
    """
    # TODO: this is not sufficient!
    return s.upper()


def locate_prm(filename):
    """Function to locate a filename within a directory tree.
    """

    # TODO: this is not sufficient!
    return os.path.join(os.environ['HOME'], 'Procedure',
                        'COMMON', filename)


def prepend_prm(lines, filename):

    filepath = locate_prm(filename)

    try:
        with open(filepath, 'r') as in_f:
            buf = in_f.read()

        # Prepend the lines to the current set of lines
        # TODO: there has got to be a more efficient way
        # to do this
        newlines = buf.split('\n')
        newlines.reverse()
        for line in newlines:
            lines.insert(0, line)

    except IOError, e:
        raise OPEerror(str(e))

        
def substitute_params(plist, cmdstr):

    # Build substitution dictionary from the PARAMETER_LIST section

    lines = plist.split('\n')
    substDict = Bunch.caselessDict()
    while len(lines) > 0:
        line = lines.pop(0)
        line = line.strip()
        match = pattern3.match(line)
        if match:
            prepend_prm(lines, match.group(1))
            continue

        # convert to uc
        line = toupper(line)
        
        if line.startswith('#') or line.startswith('*') or (len(line) == 0):
            continue

        elif '=' in line:
            idx = line.find('=')
            var = line[0:idx].strip()
            val = line[idx+1:].strip()
            substDict[var] = val

    #pprint.pprint(substDict)

    cmdstr = toupper(cmdstr)

    # Now substitute into the command line wherever we see any of these
    # varrefs
    for (key, val) in substDict.items():
        varref = '$%s' % key
        if varref in cmdstr:
            cmdstr = cmdstr.replace(varref, val)

    # Final sanity check
    # TODO: parse this with the OPE parser
    i = cmdstr.find('$')
    if i > 0:
        raise OPEerror("Not all variable references were converted: %s" % (
            cmdstr[i:]))
    
    return cmdstr

    
## def params_to_envstr(plist):

##     res = []
##     for line in plist.split('\n'):
##         line = line.strip()
##         if line.startswith('#') or line.startswith('*') or (len(line) == 0):
##             continue

##         elif '=' in line:
##             idx = line.find('=')
##             var = line[0:idx].strip()
##             val = line[idx+1:].strip()
##             res.append('%s=%s' % (var, val))

##         else:
##             # What!?
##             pass

##     return ' '.join(res)


def getCmd(opebuf, cmdstr):
    
    try:
        match = pattern1.match(opebuf)
        if match:
            header = match.group(1).strip()
            plist = match.group(2).strip()
            cmds = match.group(3)
        else:
            match = pattern2.match(contents)
            if not match:
                raise OPEerror("String contents do not match expected format")

            header = ""
            plist = ""
            cmds = match.group(1)

        cmdstr = cmdstr.strip()

        #print "PLIST", plist
        #print "CMDSTR", cmdstr
        
        # Substitute parameters into command list
        #print "SUBST <== (%s) : %s" % (str(plist), cmdstr)
        cmdstr = substitute_params(plist, cmdstr)
        #print "SUBST ==> %s" % (cmdstr)
        #envstr = params_to_envstr(plist)
        #envstr = ''
        
        #return (cmdstr, envstr)
        return cmdstr

    except Exception, e:
        raise OPEerror("Can't extract command: %s" % str(e))


def main(options, args):
    in_f = open(options.opefile, 'r')
    opebuf = in_f.read()
    in_f.close()

    print getCmd(opebuf, options.cmdstr)

    
if __name__ == '__main__':

    # Parse command line options
    from optparse import OptionParser

    optprs = OptionParser(version=('%prog'))
    optprs.add_option("--cmd", dest="cmdstr", metavar="CMDSTR",
                      help="The CMDSTR to convert")
    optprs.add_option("--debug", dest="debug", default=False, action="store_true",
                      help="Enter the pdb debugger on main()")
    optprs.add_option("--ope", dest="opefile", metavar="FILE",
                      help="Specify OPE file to use")
    optprs.add_option("--profile", dest="profile", action="store_true",
                      default=False,
                      help="Run the profiler on main()")

    (options, args) = optprs.parse_args(sys.argv[1:])

    # Are we debugging this?
    if options.debug:
        import pdb

        pdb.run('main(options, args)')

    # Are we profiling this?
    elif options.profile:
        import profile

        print "%s profile:" % sys.argv[0]
        profile.run('main(options, args)')

    else:
        main(options, args)

# END
