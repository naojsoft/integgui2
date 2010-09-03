#
# CommandObject.py -- command object and queue object definitions
#
#[ Eric Jeschke (eric@naoj.org) --
#  Last edit: Thu Sep  2 19:51:57 HST 2010
#]

# remove once we're certified on python 2.6
from __future__ import with_statement

import threading

import Task

class CommandObject(Task.Task):

    # static class vars
    lock = threading.RLock()
    cmdcount = 0

    @classmethod
    def get_tag(cls, format):
        """Class method to bump a count and return unique tags.  _format_
        should be a string containing an integer format instance '%d'.
        """
        with cls.lock:
            tag = format % cls.cmdcount
            cls.cmdcount += 1
            return tag


    def __init__(self, format, queueName, logger):
        """Constructor.  Takes a format string (should contain '%d') and
        a queue name.  Normally this class should be subclassed to provide
        proper behavior for executing a command.
        """
        super(CommandObject, self).__init__()

        self.guitag = CommandObject.get_tag(format)
        self.queueName = queueName
        self.logger = logger
        

    def get_preview(self):
        """This is called to get a preview of the command string that
        should be executed.
        """
        raise Exception("Please subclass this method!")

    def mark_status(self, txttag):
        """This is called when our command changes status.  _txttag_ should
        be 'normal', 'scheduled', 'executing', 'done' or 'error'.
        """
        pass


        
