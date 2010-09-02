# 
#[ Eric Jeschke (eric@naoj.org) --
#  Last edit: Wed Sep  1 20:58:18 HST 2010
#]

# remove once we're certified on python 2.6
from __future__ import with_statement

import re
import os
import threading

import view.common as common
import CommandQueue

# SSD/Gen2 imports
import Task
import remoteObjects as ro
import remoteObjects.Monitor as Monitor
import Bunch
from cfg.INS import INSdata
import cfg.g2soss

# Regex used to discover/parse frame info
regex_frame = re.compile(r'^mon\.frame\.(\w+)\.(\w+)$')

# Regex used to discover/parse log info
regex_log = re.compile(r'^mon\.log\.(\w+)$')

# These are the status variables pulled from the status system. "%s" is
# replaced by the 3-letter instrument mnemonic of the currently allocated
# primary instrument in IntegGUI.
#
statvars_t = [(1, 'STATOBS.%s.OBSINFO1'), (2, 'STATOBS.%s.OBSINFO2'),
              (3, 'STATOBS.%s.OBSINFO3'), (4, 'STATOBS.%s.OBSINFO4'),
              (5, 'STATOBS.%s.OBSINFO5'), # 6 is error log string
              (7, 'STATOBS.%s.TIMER_SEC'), (8, 'FITS.%s.PROP-ID'),
              ]


class IntegController(object):
    """
    IMPORTANT NOTE: The GUI thread makes calls into this object, but these
    SHOULD NOT BLOCK or the GUI becomes unresponsive!  ALL CALLS IN should
    create and start a task to do the work (which will be done on another
    thread).
    """
    
    def __init__(self, logger, ev_quit, monitor, view, queues, fits,
                 soundsink, options):

        self.logger = logger
        self.ev_quit = ev_quit
        self.monitor = monitor
        self.gui = view
        self.queue = queues
        self.fits = fits
        # mutex on this instance
        self.lock = threading.RLock()
        self.soundsink = soundsink
        self.options = options

        self.executingP = threading.Event()

        # For task inheritance:
        self.threadPool = monitor.get_threadPool()
        self.tag = 'IntegGUI'
        self.shares = ['logger', 'ev_quit', 'threadPool']

        # Used for looking up instrument codes, etc.
        self.insconfig = INSdata()
        self.insname = 'SUKA'

        self.reset_conn()


    def reset_conn(self):
        self.tm = ro.remoteObjectProxy(self.options.taskmgr)
        self.tm2 = ro.remoteObjectProxy(self.options.taskmgr)
        self.status = ro.remoteObjectProxy('status')
        self.sm = ro.remoteObjectProxy('sessions')
        self.bm = ro.remoteObjectProxy('bootmgr')

        self.transdict = {}

#############
###  GUI interface to the controller
            
    def get_queueLength(self, queueName):
        return len(self.queue[queueName])

    def clearQueue(self, queueName):
        queue = self.queue[queueName]
        queue.flush()

    def prependQueue(self, queueName, cmdObj):
        queue = self.queue[queueName]
        queue.prepend(cmdObj)

    def appendQueue(self, queueName, cmdObjs):
        queue = self.queue[queueName]
        queue.extend(cmdObjs)

    def replaceQueueAndExecute(self, queueName, cmdObjs):
        queue = self.queue[queueName]
        queue.replace(cmdObjs)
        self.resumeQueue(queueName)

    def appendQueueAndExecute(self, queueName, cmdObjs):
        self.appendQueue(queueName, cmdObjs)
        self.resumeQueue(queueName)

    def resumeQueue(self, queueName):
        """This method is called when the GUI has commands for the
        controller.
        """
        queueObj = self.queue[queueName]
        
        try:
            cmdObj = queueObj.get()
            self.logger.debug("cmdObj=%s" % str(cmdObj))
            
        except CommandQueue.QueueEmpty, e:
            # TODO: popup error here?
            #raise e
            self.gui.gui_do(self.gui.popup_error, str(e))

        try:
            cmdObj.init_and_start(self)

        except Exception, e:
            # TODO: popup error here?
            self.gui.gui_do(self.gui.popup_error, str(e))

            
#############

    def tm_kill(self):
        self.playSound(common.sound.tm_kill)
        
        # reset visually all command executors
        self.gui.gui_do(self.gui.reset)

        # ask Boot Manager to restart the Task Manager
        self.bm.restart(self.options.taskmgr)

        # Release all pending transactions
        self.release_all_transactions()


    def tm_cancel(self, queueName):
        #self.tm2.cancel(queueName)
        t = Task.FuncTask(self.tm2.cancel, [queueName], {})
        t.init_and_start(self)

    def tm_pause(self, queueName):
        #self.tm2.pause(queueName)
        t = Task.FuncTask(self.tm2.pause, [queueName], {})
        t.init_and_start(self)

    def tm_resume(self, queueName):
        #self.tm2.resume(queueName)
        t = Task.FuncTask(self.tm2.resume, [queueName], {})
        t.init_and_start(self)

    def tm_restart(self):
        t = Task.FuncTask(self.tm_kill, [], {})
        t.init_and_start(self)

    def set_instrument(self, insname):
        """Called when we notice a change of instrument.
        """
        try:
            inscode = self.insconfig.getCodeByName(insname)
        except KeyError:
            # If no instrument allocated, then just look up a non-existent
            # instrument status messages
            inscode = "NOP"
    
        # Set up default fetch list and dictionary.
        # _statDict_: dictionary whose keys are status variables we need
        # _statvars_: list of (index, key) pairs (index is used by IntegGUI)
        statvars = []
        for (idx_t, key_t) in statvars_t:
            if key_t:
                keyCmn = key_t % "CMN"
                key = key_t % inscode
            statvars.append((idx_t, keyCmn))
            statvars.append((idx_t, key))

        with self.lock:
            self.statvars = statvars
            self.insname = insname
            

    def get_instrument(self):
        return self.insname

    def get_alloc_instrument(self):
        insname = self.status.fetchOne('FITS.SBR.MAINOBCP')
        return insname
    
    def config_alloc_instrument(self):
        insname = self.get_alloc_instrument()
        self.set_instrument(insname)

    def config_from_session(self, sessionName):
        self.sessionName = sessionName

        try:
            info = self.sm.getSessionInfo(self.sessionName)

            self._session_config(info)

        except ro.remoteObjectError, e:
            self.logger.error("Error getting session info for session '%s': %s" % (
                    self.sessionName, str(e)))


    def load_frames(self, framelist):
        # TODO: this should maybe be in IntegView

        for frameid in framelist:
            fitspath = self.insconfig.getFileByFrameId(frameid)
            self.gui.load_fits(fitspath)


    def _session_config(self, info):
        self.logger.debug("info=%s" % str(info))

        # Get propid info
        propid = info.get('propid', 'xxxxx')
        observers = info.get('observers', 'N/A')
        inst = info.get('mainInst', 'N/A')
        self.gui.update_obsinfo({'PROP-ID':
                                                      ('%s - %s - %s' % (propid,
                                                                         inst,
                                                                         observers))
                                 })
        
        self.set_instrument(inst)

        # Get allocs
        allocs = info.get('allocs', [])
        allocs_lst = []
    
        for name in self.insconfig.getNames(active=True):
            if name in allocs:
                allocs_lst.append(name)
        
        # Load up appropriate launchers
        #self.gui.close_launchers()

        launchers = []
        for name in ['TELESCOPE']:
            launchers.extend(self.gui.get_launcher_paths(name))

        for name in allocs_lst:
            launchers.extend(self.gui.get_launcher_paths(name))

        self.logger.debug("launchers=%s" % launchers)
        for filepath in launchers:
            self.gui.load_launcher(filepath)

        # Load up appropriate log files
        #self.gui.close_logs()

        logs = []
        names = set(allocs)
        # Some names of interest that won't show up in the allocations
        names.update(['qdas_stdout', 'integgui2', 'VGW_stdout'])
        # Remove some that aren't particularly useful
        for name in ['frames', 'bootmgr', 'monitor']:
            names.remove(name)
        names = list(names)
        names.sort()

        for name in names:
            filepath = self.gui.get_log_path(name)
            if os.path.exists(filepath):
                logs.append(filepath)

        logs.sort()

        for filepath in logs:
            self.gui.load_log(filepath)

                      
    def get_transaction(self, path):
        with self.lock:
            # Will return KeyError if path does not reference a
            # valid transaction
            # TODO: should this dictionary be made persistent so
            # that we can restart integgui and pick up outstanding
            # transactions?
            return self.transdict[path]

    def put_transaction(self, tm_tag, cmdObj):
        with self.lock:
            self.transdict[tm_tag] = cmdObj
            cmdObj.tasktag = tm_tag
            cmdObj.ev_trans = threading.Event()

            # Graphically signal execution in some way
            cmdObj.page.mark_status(cmdObj, 'executing')


    def wait_transaction(self, cmdObj):
        """Wait for transaction to be finished."""
        cmdObj.ev_trans.wait()

    def release_transaction(self, cmdObj):
        """Signal that transaction is finished."""
        cmdObj.ev_trans.set()

    def release_all_transactions(self):
        with self.lock:
            cmdObjs = self.transdict.values()
        for cmdObj in cmdObjs:
            self.release_transaction(cmdObj)
        self.executingP.clear()

    def del_transaction(self, cmdObj):
        with self.lock:
            try:
                del self.transdict[cmdObj.path]
            except:
                pass
       
    def getvals(self, path):
        return self.monitor.getitems_suffixOnly(path)

    def update_integgui(self, statusDict):
        d = {}
        for (idx, key) in self.statvars:
            val = statusDict.get(key, '##')
            if not val.startswith('##'):
                slot = key.split('.')[-1]
                d[slot] = str(val)

        self.gui.update_obsinfo(d)


    # this one is called if new data becomes available about tasks
    def arr_taskinfo(self, payload, name, channels):
        self.logger.debug("received values '%s'" % str(payload))

        try:
            bnch = Monitor.unpack_payload(payload)

        except Monitor.MonitorError:
            self.logger.error("malformed packet '%s': %s" % (
                str(payload), str(e)))
            return

        vals = bnch.value

        if vals.has_key('ast_id'):
            # SkMonitorPage update on some AB command
            self.gui.process_ast(vals['ast_id'], vals)

        # possible SkMonitorPage update on some DD command
        self.gui.process_task(bnch.path, vals)
        
        if vals.has_key('task_code'):
            # possible update on some integgui command finishing
            try:
                # Did we initiate this command?
                tmtrans = self.get_transaction(bnch.path)

                self.release_transaction(tmtrans)
            except KeyError:
                # No
                return

            res = vals['task_code']
            # Interpret task results:
            #   task_code == 0 --> OK   task_code != 0 --> ERROR
            if res == 0:
##                 self.gui.gui_do(self.gui.feedback_ok,
##                                 tmtrans.queueName, tmtrans, res)
                pass
            else:
                # If there was a problem, let the gui know about it
##                 self.gui.gui_do(self.gui.feedback_error,
##                                 tmtrans.queueName, tmtrans, str(res))
                pass

            self.del_transaction(tmtrans)

    # this one is called if new data becomes available for integgui
    def arr_obsinfo(self, payload, name, channels):
        self.logger.debug("received values '%s'" % str(payload))

        try:
            bnch = Monitor.unpack_payload(payload)

        except Monitor.MonitorError:
            self.logger.error("malformed packet '%s': %s" % (
                str(payload), str(e)))
            return

        vals = bnch.value
        if vals.has_key('obsinfo'):
            statusDict = bnch.value['obsinfo']
            self.update_integgui(statusDict)

        elif vals.has_key('ready'):
            self.playSound(common.sound.tm_ready)
            
        
    # this one is called if new log data becomes available
    def arr_loginfo(self, payload, name, channels):
        #self.logger.debug("received values '%s'" % str(payload))
        try:
            bnch = Monitor.unpack_payload(payload)

        except Monitor.MonitorError:
            self.logger.error("malformed packet '%s': %s" % (
                str(payload), str(e)))
            return

        # Find out the log for this information by examining the path
        match = regex_log.match(bnch.path)
        if match:
            logname = match.group(1)
            self.gui.update_loginfo(logname, bnch.value)
            
        
    # this one is called if new data becomes available about frames
    def arr_fitsinfo(self, payload, name, channels):
        self.logger.debug("received values '%s'" % str(payload))

        try:
            bnch = Monitor.unpack_payload(payload)

        except Monitor.MonitorError:
            self.logger.error("malformed packet '%s': %s" % (
                str(payload), str(e)))
            return

        # Find out the source of this information by examining the path
        match = regex_frame.match(bnch.path)
        if match:
            (frameid, subsys) = match.groups()

            try:
                # See if there is method to handle this information
                # in the 'fits' object
                method = getattr(self.fits, '%s_hdlr' % subsys)

            except AttributeError:
                self.logger.debug("No handler for '%s' subsystem" % subsys)
                return

            try:
                # Get all the saved items under this path to report to
                # the handler
                vals = self.monitor.getitems_suffixOnly(bnch.path)
                
                method(frameid, vals)
                return

            except Exception, e:
                self.logger.error("Error processing '%s': %s" % (
                    str(bnch.path), str(e)))
            return

        # Skip things that don't match the expected paths
        self.logger.error("No match for path '%s'" % bnch.path)
        return

                
    # this one is called if new data becomes available about the session
    def arr_sessinfo(self, payload, name, channels):
        self.logger.debug("received values '%s'" % str(payload))

        try:
            bnch = Monitor.unpack_payload(payload)

        except Monitor.MonitorError:
            self.logger.error("malformed packet '%s': %s" % (
                str(payload), str(e)))
            return

        if bnch.path == ('mon.session.%s' % self.sessionName):
            
            info = bnch.value
            #self._session_config(info)
                

    def audible_warn(self, cmd_str, vals):
        """Called when we get a failed command and should/could issue an audible
        error.  cmd_str, if not None, is the device dependent command that caused
        the error.
        """
        self.logger.debug("Audible warning: %s" % cmd_str)
        if not cmd_str:
            return

        if not self.audible_errors:
            return

        cmd_str = cmd_str.lower().strip()
        match = re.match(r'^exec\s+(\w+)\s+.*', cmd_str)
        if not match:
            subsys = 'general'
        else:
            subsys = match.group(1)

        #soundfile = 'g2_err_%s.au' % subsys
        soundfile = 'E_ERR%s.au' % subsys.upper()
        self.playSound(soundfile)


    def playSound(self, soundfile):
        soundpath = os.path.join(cfg.g2soss.producthome,
                                 'file/Sounds', soundfile)
        if os.path.exists(soundpath):
##             # TODO: use Python soundsink module to do this instead of
##             # spawning a process
##             cmd = "OSST_audioplay %s" % (soundpath)
##             self.logger.debug(cmd)
##             res = os.system(cmd)
            self.soundsink.playFile(soundpath)
            
        else:
            self.logger.error("No such audio file: %s" % soundpath)
        
#END
