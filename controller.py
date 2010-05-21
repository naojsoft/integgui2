# 
#[ Eric Jeschke (eric@naoj.org) --
#  Last edit: Thu May 20 14:20:05 HST 2010
#]

# remove once we're certified on python 2.6
from __future__ import with_statement

import os
import threading
import Queue

# SSD/Gen2 imports
import Task
import remoteObjects as ro
import Monitor
import Bunch
from cfg.INS import INSdata

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
    
    def __init__(self, logger, ev_quit, monitor, view, options):

        self.logger = logger
        self.ev_quit = ev_quit
        self.monitor = monitor
        self.gui = view
        self.lock = threading.RLock()
        self.options = options

        # command queues
        self.queue = Bunch.Bunch(executer=Queue.Queue(),
                                 launcher=Queue.Queue())

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

    def start_executors(self):
        t1 = Task.FuncTask(self.execute_loop, ['executer'], {})
        t2 = Task.FuncTask(self.execute_loop, ['launcher'], {})
        t1.init_and_start(self)
        t2.init_and_start(self)
       
    def execute_loop(self, queueName):
        
        self.logger.info("Starting executor for '%s'..." % queueName)
        queue = self.queue[queueName]

        while not self.ev_quit.isSet():
            try:
                bnch = None
                # Try to get a command from our queue
                bnch = queue.get(block=True, timeout=0.01)

                cmdstr = bnch.cmdstr

                # Try to execute the command in the TaskManager
                self.logger.debug("Invoking to task manager (%s): '%s'" % (
                        queueName, cmdstr))
                res = self.tm.execTask(queueName, cmdstr, '')
                if res != ro.OK:
                    raise Exception("Command failed with res=%d" % res)

                self.gui.command_feedback_ok(queueName, bnch, res)

            except Queue.Empty:
                # No command ready...busy wait
                self.ev_quit.wait(0.01)

            except Exception, e:
                # If there was a problem, let the gui know about it
                self.gui.command_feedback_error(queueName, bnch, e)

        self.logger.info("Executor for '%s' shutting down..." % queueName)


    def tm_exec(self, queueName, bnch):
        # Submit 
        queue = self.queue[queueName]
        queue.put(bnch)
        
    def tm_cancel(self, queueName):
        self.tm2.cancel(queueName)

    def tm_pause(self, queueName):
        self.tm2.pause(queueName)

    def tm_resume(self, queueName):
        self.tm2.resume(queueName)

    def tm_restart(self):
        self.bm.restart(self.options.taskmgr)

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
        for name in allocs:
            filepath = self.gui.get_log_path(name)
            if os.path.exists(filepath):
                logs.append(filepath)

        logs.sort()

        for filepath in logs:
            self.gui.load_log(filepath)

                      
        
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

        try:
            ast_id = bnch.value['ast_id']
            return self.gui.process_ast(ast_id, bnch.value)

        except KeyError:
            return self.gui.process_task(bnch.path, bnch.value)
        
    # this one is called if new data becomes available for integgui
    def arr_obsinfo(self, payload, name, channels):
        self.logger.debug("received values '%s'" % str(payload))

        try:
            bnch = Monitor.unpack_payload(payload)

        except Monitor.MonitorError:
            self.logger.error("malformed packet '%s': %s" % (
                str(payload), str(e)))
            return

        try:
            statusDict = bnch.value['obsinfo']

            self.update_integgui(statusDict)

        except KeyError:
            pass
        
    # this one is called if new data becomes available about frames
    def arr_fitsinfo(self, payload, name, channels):
        self.logger.debug("received values '%s'" % str(payload))

        try:
            bnch = Monitor.unpack_payload(payload)

        except Monitor.MonitorError:
            self.logger.error("malformed packet '%s': %s" % (
                str(payload), str(e)))
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
                

#END
