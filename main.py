#
# Eric Jeschke (eric@naoj.org)
#

# Standard library imports
import sys, os
import threading

# Special library imports
import gi
gi.require_version('Gtk', '3.0')

from ginga.misc import Bunch, ModuleManager, Datasrc, Settings
import ginga.toolkit as ginga_toolkit
ginga_toolkit.use('gtk3')

# SSD/Gen2 imports
from g2base.remoteObjects import remoteObjects as ro
from g2base.remoteObjects import Monitor
from g2base import ssdlog

import g2client.soundsink as SoundSink

import cfg.g2soss as g2soss

# Local integgui2 imports
import Gen2.integgui2
from Gen2.integgui2 import fits
from Gen2.integgui2 import controller as igctrl
from Gen2.integgui2.view import IntegView as igview
from Gen2.integgui2.view import common
from Gen2.integgui2 import CommandQueue

# our ginga toolkit layout
default_layout = ['seq', {},
                   ['vbox', dict(name='top', width=2000, height=1100),
                    dict(row=['hbox', dict(name='menu')], stretch=0),
                    dict(row=['vpanel', {},
                              ['hpanel', dict(name='ulh', height=400),
                               ['vbox', dict(name='ul', width=1000)],
                               # ['vbox', dict(name='um', width=0)],
                               ['vbox', dict(name='ur', width=1000)],
                               ],
                              ['hpanel', dict(name='llh', height=600),
                               ['vbox', dict(name='ll', width=600)],
                               ['vbox', dict(name='lm', width=500)],
                               ['vbox', dict(name='lr', width=600)],
                               ],
                              ], stretch=1),
                    dict(row=['hbox', dict(name='status')], stretch=0),
                    ]]

# TODO: this will eventually hold plugins for different kinds of pages
plugins = [
    ]


def main(options, args):

    global controller, gui

    # Create top level logger.
    logger = ssdlog.make_logger('integgui2', options)

    # Initialize remote objects subsystem.
    try:
        ro.init()

    except ro.remoteObjectError as e:
        logger.error("Error initializing remote objects subsystem: %s" % \
                     str(e))
        sys.exit(1)

    ev_quit = threading.Event()

    # TEMP: integgui needs to find its plugins
    integgui_home = os.path.split(sys.modules['Gen2.integgui2'].__file__)[0]
    child_dir = os.path.join(integgui_home, 'view', 'pages')
    sys.path.insert(0, child_dir)

    # make a name for our monitor
    if options.monname:
        myMonName = options.monname
    else:
        myMonName = 'integgui2-%s-%d.mon' % (
            ro.get_myhost(short=True), options.monport)

    # monitor channels we are interested in
    sub_channels = []
    pub_channels = ['g2task']

    # Create a local monitor
    mymon = Monitor.Minimon(myMonName, logger, numthreads=options.numthreads)

    threadPool = mymon.get_threadPool()

    mm = ModuleManager.ModuleManager(logger)

    basedir = os.path.join(g2soss.confhome, 'integgui2')
    prefs = Settings.Preferences(basefolder=basedir,
                                 logger=logger)
    # command queues
    queues = Bunch.Bunch(default=CommandQueue.CommandQueue('default',
                                                            logger), )
    if options.logmon:
        logtype = 'monlog'
    else:
        logtype = 'normal'

    # Create view
    gui = igview.IntegView(logger, prefs, ev_quit, queues,
                           logtype=logtype)
    # Build desired layout
    gui.build_toplevel(default_layout)

    # Load built in plugins
    for spec in plugins:
        gui.add_plugin(spec)

    # start any plugins that have start=True
    gui.update_pending()

    # Create network callable object for notifications
    notify_obj = fits.HSC_IntegGUINotify(gui, options.fitsdir)
    notify_obj.update_framelist()

    # For playing sounds
    soundsink = SoundSink.SoundSource(monitor=mymon, logger=logger,
                                      channels=['sound'])
    pub_channels.append('sound')

    # Create controller
    controller = igctrl.IntegController(logger, ev_quit, mymon,
                                        gui, queues, notify_obj,
                                        soundsink, options,
                                        logtype=logtype)

    common.set_view(gui)
    common.set_controller(controller)

    # Configure for currently allocated instrument
    if options.instrument:
        insname = options.instrument
        controller.set_instrument(insname)
    else:
        try:
            insname = controller.get_alloc_instrument()
            controller.set_instrument(insname)
        except Exception as e:
            # TODO: error popup?
            pass

    if options.geometry:
        gui.setPos(options.geometry)
    #gui.logupdate()

    # Subscribe our callback functions to the local monitor
    # Task info
    # TODO: g2task should not be fixed
    taskch = [options.taskmgr, 'g2task']
    mymon.subscribe_cb(controller.arr_taskinfo, taskch)
    sub_channels.extend(taskch)

    # Obsinfo
    ig_ch = options.taskmgr + '-ig'
    mymon.subscribe_cb(controller.arr_obsinfo, [ig_ch])
    sub_channels.append(ig_ch)

    # Log info
    mymon.subscribe_cb(controller.arr_loginfo, ['logs'])
    #sub_channels.append('logs')

    # Fits info
    mymon.subscribe_cb(controller.arr_fitsinfo, ['frames'])
    sub_channels.append('frames')

    # Session info
    mymon.subscribe_cb(controller.arr_sessinfo, ['sessions'])
    sub_channels.append('sessions')

    # Configure from session, if requested
    if options.session:
        try:
            controller.config_from_session(options.session)
        except Exception as e:
            logger.error("Failed to initialize from session '%s': %s" % (
                options.session, str(e)))

    # Start up a remote object server for certain services provided by
    # integgui2
    svc = ro.remoteObjectServer(svcname=options.svcname,
                                obj=controller, logger=logger,
                                method_list=['get_ope_paths',
                                             'obs_play_sound_file',
                                             'obs_timer',
                                             'obs_confirmation',
                                             'obs_userinput',
                                             'obs_combobox',
                                             'obs_fileselection',
                                             'obs_copyfilestotsc',
                                             'load_page',
                                             'sound_check'],
                                port=options.port,
                                ev_quit=ev_quit,
                                usethread=True, threadPool=threadPool)

    # Load any files specified on the command line
    for opefile in args:
        gui.load_ope(opefile)

    server_started = False
    ro_server_started = False
    try:
        # Startup monitor threadpool
        mymon.start(wait=True)
        # start_server is necessary if we are subscribing, but not if only
        # publishing
        mymon.start_server(wait=True, port=options.monport)
        server_started = True

        # subscribe our monitor to the central monitor hub
        if sub_channels:
            mymon.subscribe_remote(options.monitor, sub_channels, {})
        # publish to central monitor hub
        if pub_channels:
            mymon.publish_to(options.monitor, pub_channels, {})

        if options.logmon:
            mymon.subscribe_remote(options.logmon, ['logs'], {})
            #mymon.subscribe(options.logmon, ['logs'], {})
            mymon.logmon(logger, options.logmon, ['logs'])

        svc.ro_start(wait=True)
        ro_server_started = True

        try:
            gui.mainloop(timeout=0.001)

        except KeyboardInterrupt:
            logger.error("Received keyboard interrupt!")

    finally:
        if ro_server_started:
            svc.ro_stop(wait=True)
        if server_started:
            mymon.stop_server(wait=True)
        mymon.stop(wait=True)

    logger.info("exiting Gen2 integgui2...")
    #gui.quit()
    sys.exit(0)
