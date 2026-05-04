import re
import sys

import numpy as np
import pkg_resources
import math

from PyQt5 import uic, QtGui, QtCore

from PyQt5.QtCore import QThread, QSettings

from isstools.widgets import (widget_general_info, widget_trajectory_manager, widget_processing, widget_batch,
                              widget_run, widget_beamline_setup, widget_run_diff, widget_sdd_manager, widget_beamline_status,
                              widget_user_motors, widget_xspress3x_manager)

from isstools.elements import EmittingStream
from isstools.elements.batch_motion import SamplePositioner
from isstools.process_callbacks.callback import ProcessingCallback
from xas.process import process_interpolate_bin
import time
ui_path = pkg_resources.resource_filename('isstools', 'ui/XLive.ui')

def auto_redraw_factory(fnc):
    def stale_callback(fig, stale):
        if fnc is not None:
            fnc(fig, stale)
        if stale and fig.canvas:
            fig.canvas.draw_idle()

    return stale_callback


class XliveGui(*uic.loadUiType(ui_path)):
    progress_sig = QtCore.pyqtSignal()

    def __init__(self,
                 plan_funcs=[],
                 diff_plans=[],
                 service_plan_funcs={},
                 prep_traj_plan= None,
                 RE=None,
                 db=None,
                 apb=None,
                 apb_c = None,
                 accelerator=None,
                 mono=None,
                 sdd = None,
                 xspress3x=None,
                 pe1 = None,
                 shutters_dict={},
                 det_dict={},
                 motors_dict={},
                 user_motors_dict ={},
                 aux_plan_funcs={},
                 general_scan_func = None,
                 sample_stage= None,
                 wps = None,
                 mfc = None,
                 window_title="XLive @QAS/07-BM NSLS-II",
                 *args, **kwargs):
        '''

            Parameters
            ----------

            plan_funcs : list, optional
                functions that run plans (call RE(plan()) etc)
            prep_traj_plan : generator or None, optional
                a plan that prepares the trajectories
            RE : bluesky.RunEngine, optional
                a RunEngine instance
            db : databroker.Broker, optional
                the database to save acquired data to
            accelerator : 
            mono : ophyd.Device, optional
                the monochromator.
                and has been kept from the legacy ISS code
            shutters_dict : dict, optional
                dictionary of available shutters
            det_dict : dict, optional
                dictionary of detectors
            motors_dict : dict, optional
                dictionary of motors
            general_scan_func : generator or None, optional
            receiving address: string, optinal
                the address for where to subscribe the Kafka Consumer to
        '''
        self.window_title = window_title

        if 'write_html_log' in kwargs:
            self.html_log_func = kwargs['write_html_log']
            del kwargs['write_html_log']
        else:
            self.html_log_func = None

        if 'ic_amplifiers' in kwargs:
            self.ic_amplifiers = kwargs['ic_amplifiers']
            del kwargs['ic_amplifiers']
        else:
            self.ic_amplifiers = None

        if 'auto_tune_elements' in kwargs:
            self.auto_tune_dict = kwargs['auto_tune_elements']
            del kwargs['auto_tune_elements']
        else:
            self.auto_tune_dict = None

        if 'prepare_bl' in kwargs:
            self.prepare_bl_list = kwargs['prepare_bl']
            self.prepare_bl_plan = kwargs['prepare_bl'][0]
            del kwargs['prepare_bl']
        else:
            self.prepare_bl_list = []
            self.prepare_bl_plan = None

        if 'set_gains_offsets' in kwargs:
            self.set_gains_offsets_scan = kwargs['set_gains_offsets']
            del kwargs['set_gains_offsets']
        else:
            self.set_gains_offsets_scan = None

        if 'sample_stages' in kwargs:
            self.sample_stages = kwargs['sample_stages']
            del kwargs['sample_stages']
        else:
            self.sample_stages = []

        if 'processing_sender' in kwargs:
            self.sender = kwargs['processing_sender']
            del kwargs['processing_sender']
        else:
            self.sender = None


        super().__init__(*args, **kwargs)
        self.setupUi(self)

        self.det_dict = det_dict
        self.plan_funcs = plan_funcs

        self.prep_traj_plan = prep_traj_plan

        self.motors_dict = motors_dict
        self.user_motors_dict = user_motors_dict

        self.shutters_dict = shutters_dict

        self.diff_plans = diff_plans
        self.hutch = 'b'

        self.RE = RE
        self.db = db
        self.wps = wps
        self.mfc = mfc
        self.pe1 = pe1


        self.processing_thread = ProcessingThread(self)


        if self.RE is not None:
            self.RE.is_aborted = False
            self.timer = QtCore.QTimer()
            self.timer.timeout.connect(self.update_re_state)
            self.timer.start(1000)
        else:
            self.tabWidget.removeTab(
                [self.tabWidget.tabText(index) for index in range(self.tabWidget.count())].index('Run'))
            self.tabWidget.removeTab(
                [self.tabWidget.tabText(index) for index in range(self.tabWidget.count())].index('Run Batch'))
            self.push_re_abort.setEnabled(False)
            self.run_check_gains.setEnabled(False)

        self.mono = mono
        if self.mono is None:
            self.tabWidget.removeTab([self.tabWidget.tabText(index)
                                      for index in range(self.tabWidget.count())].index('Trajectory setup'))
            self.tabWidget.removeTab([self.tabWidget.tabText(index)
                                      for index in range(self.tabWidget.count())].index('Run'))
            self.tabWidget.removeTab([self.tabWidget.tabText(index)
                                      for index in range(self.tabWidget.count())].index('Run Batch'))
        else:
            self.mono.trajectory_progress.subscribe(self.update_progress)
            self.progress_sig.connect(self.update_progressbar)
            self.progressBar.setValue(0)

        # Activating ZeroMQ Receiving Socket
        self.settings = QSettings(self.window_title, 'XLive')

        stage_park_x = self.settings.value('stage_park_x', defaultValue=0, type=float)
        stage_park_y = self.settings.value('stage_park_y', defaultValue=0, type=float)
        sample_park_x = self.settings.value('sample_park_x', defaultValue=0, type=float)
        sample_park_y = self.settings.value('sample_park_y', defaultValue=0, type=float)
        self.sample_positioner = SamplePositioner(self.RE,
                                                  sample_stage,
                                                  stage_park_x,
                                                  stage_park_y,
                                                  delta_first_holder_x=sample_park_x - stage_park_x,
                                                  delta_first_holder_y=sample_park_y - stage_park_y)

        self.run_mode = 'run'

        # Looking for analog pizzaboxes:
        regex = re.compile(r'pba\d{1}.*')
        matches = [det for det in self.det_dict if re.match(regex, det)]
        self.adc_list = [self.det_dict[x]['obj'] for x in self.det_dict if x in matches]

        # Looking for encoder pizzaboxes:
        regex = re.compile(r'pb\d{1}_enc.*')
        matches = [det for det in self.det_dict if re.match(regex, det)]
        self.enc_list = [self.det_dict[x]['obj'] for x in self.det_dict if x in matches]

        # Looking for xias:
        regex = re.compile(r'xia\d{1}')
        matches = [det for det in self.det_dict if re.match(regex, det)]
        self.xia = None
        # self.xia_list = [self.det_dict[x]['obj'] for x in self.det_dict if x in matches]
        # if len(self.xia_list):
        #     self.xia = self.xia_list[0]
        #     self.widget_sdd_manager = widget_sdd_manager.UISDDManager(self.xia_list)
        #     self.layout_sdd_manager.addWidget(self.widget_sdd_manager)
        # else:
        #     self.tabWidget.removeTab([self.tabWidget.tabText(index) for index in
        #                               range(self.tabWidget.count())].index('Silicon Drift Detector setup'))
        #     self.xia = None

        self.widget_general_info = widget_general_info.UIGeneralInfo(accelerator, mono, RE, db, parent_gui=self)
        self.layout_general_info.addWidget(self.widget_general_info)

        if self.mono is not None:
            self.widget_trajectory_manager = widget_trajectory_manager.UITrajectoryManager(mono, self.run_prep_traj)
            self.layout_trajectory_manager.addWidget(self.widget_trajectory_manager)

        self.widget_processing = widget_processing.UIProcessing(mono,
                                                                db,
                                                                parent_gui = self
                                                                )
        self.layout_processing.addWidget(self.widget_processing)

        if self.RE is not None:
            self.widget_run = widget_run.UIRun(RE,
                                               self.plan_funcs,
                                               db, 
                                               shutters_dict, 
                                               self.adc_list, 
                                               self.enc_list,
                                               self.xia, 
                                               self.html_log_func, 
                                               self)

            self.layout_run.addWidget(self.widget_run)


            self.widget_batch_mode = widget_batch.UIBatch(
                plan_funcs,
                service_plan_funcs,
                mono,
                RE,
                sample_stage,
                self,
                motors_dict,
                self.sample_positioner
            )
            self.layout_batch.addWidget(self.widget_batch_mode)


            # self.widget_trajectory_manager.trajectoriesChanged.connect(self.widget_batch_mode.update_batch_traj)

            self.widget_beamline_setup = widget_beamline_setup.UIBeamlineSetup(RE,
                                                                               db,
                                                                               det_dict,
                                                                               plan_funcs,
                                                                               service_plan_funcs,
                                                                               aux_plan_funcs,
                                                                               motors_dict,
                                                                               general_scan_func,
                                                                               shutters_dict,
                                                                               parent_gui=self)
            self.layout_beamline_setup.addWidget(self.widget_beamline_setup)

            self.widget_run_diff = widget_run_diff.UIRunDiff(RE,
                                                             db,
                                                             self.pe1,
                                                             self.diff_plans,
                                                             parent_gui = self,
                                                             mono=mono)
            self.layout_run_diff.addWidget(self.widget_run_diff)

            if sdd is not None:
                self.widget_sdd_manager = widget_sdd_manager.UISDDManager(service_plan_funcs,
                                                                          sdd,
                                                                          RE)


                self.layout_xspress3_setup.addWidget(self.widget_sdd_manager)

            if xspress3x is not None:
                self.widget_xspress3x_manager = widget_xspress3x_manager.UIXSXManager(service_plan_funcs, xspress3x, RE)
                self.layout_sdd_manager.addWidget(self.widget_xspress3x_manager)

            self.widget_beamline_status = widget_beamline_status.UIBeamlineStatus(
                                                                        shutters=self.shutters_dict,
                                                                        apb=apb,
                                                                        apb_c=apb_c,
                                                                        mono=mono,
                                                                        mfc=self.mfc,
                                                                        parent_gui=self)

   
            self.layout_beamline_status.addWidget(self.widget_beamline_status)

        self.filepaths = []
        pc = ProcessingCallback(db=self.db,
                                draw_func_interp=self.widget_run.draw_interpolated_data,
                                draw_func_binned=self.widget_processing.new_bin_df_arrived,
                                thread=self.processing_thread)

        # pc = ProcessingCallback(db=self.db,
        #                         draw_func_interp=self.widget_run.draw_interpolated_data,
        #                         draw_func_binned=self.widget_processing.new_bin_df_arrived) # old processing callback without threading



        self.token = self.RE.subscribe(pc, 'stop')

        self.push_re_abort.clicked.connect(self.re_abort)



        # Redirect terminal output to GUI
        self.emitstream_out = EmittingStream.EmittingStream(self.textEdit_terminal)
        self.emitstream_err = EmittingStream.EmittingStream(self.textEdit_terminal)

        sys.stdout = self.emitstream_out
        sys.stderr = self.emitstream_err
        self.setWindowTitle(window_title)

        self.widget_user_motors = widget_user_motors.UIUserMotors(RE,
                                                                  motors_dict=self.motors_dict,
                                                                  apb=apb,
                                                                  wps=self.wps,
                                                                  mfc=self.mfc,
                                                                  service_plan_funcs=service_plan_funcs,
                                                                  parent_gui=self)
        self.layout_user_motor_tab.addWidget(self.widget_user_motors)

    def update_progress(self, pvname=None, value=None, char_value=None, **kwargs):
        self.progress_sig.emit()
        self.progressValue = value

    def update_progressbar(self):
        value = np.round(self.progressValue)
        if not math.isnan(value):
            self.progressBar.setValue(int(value))

    def __del__(self):
        # Restore sys.stdout
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__

    def run_prep_traj(self):
        self.RE(self.prep_traj_plan())

    def plans_diff(self):
        self.RE(self.plans_diff())

    def re_abort(self):
        if self.RE.state != 'idle':
            self.RE.abort()
            self.RE.is_aborted = True

    def update_re_state(self):
        palette = self.label_11.palette()
        if (self.RE.state == 'idle'):
            palette.setColor(self.label_11.foregroundRole(), QtGui.QColor(193, 140, 15))
        elif (self.RE.state == 'running'):
            palette.setColor(self.label_11.foregroundRole(), QtGui.QColor(0, 165, 0))
        elif (self.RE.state == 'paused'):
            palette.setColor(self.label_11.foregroundRole(), QtGui.QColor(255, 0, 0))
        elif (self.RE.state == 'abort'):
            palette.setColor(self.label_11.foregroundRole(), QtGui.QColor(255, 0, 0))
        self.label_11.setPalette(palette)
        self.label_11.setText(self.RE.state)


class ProcessingThread(QThread):
    def __init__(self, gui, processing_ioc_uid=None):
        QThread.__init__(self)
        self.gui = gui
        self.doc = None
        self.processing_ioc_uid = processing_ioc_uid
        self.soft_mode = True

    def run(self):
        attempt = 0
        while self.doc:
            try:
                attempt += 1
                uid = self.doc['run_start']
                print(f' File received {uid}')
                process_interpolate_bin(self.doc,
                                        self.gui.db,
                                        self.gui.widget_run.draw_interpolated_data,
                                        self.gui.widget_processing.new_bin_df_arrived)

                    # process_interpolate_bin(self.doc, self.gui.db, self.gui.widget_run.draw_interpolated_data, None, self.gui.cloud_dispatcher, print_func=self.print)
                self.doc = None
            except Exception as e:
                if self.soft_mode:
                    print(f'Exception: {e}')
                    print(f'>>>>>> #{attempt} Attempt to process data ({time.ctime()}) ')
                    time.sleep(3)
                else:
                    raise e
            if attempt == 5:
                break


# class ReceivingThread(QThread):
#     received_interp_data = QtCore.pyqtSignal(object)
#     received_bin_data = QtCore.pyqtSignal(object)
#     received_req_interp_data = QtCore.pyqtSignal(object)
#     def __init__(self, gui):
#         QThread.__init__(self)
#         self.setParent(gui)
#
#     def run(self):
#         consumer = self.parent().consumer
#         for message in consumer:
#             # bruno concatenates and extra message at beginning of this packet
#             # we need to take it off
#             message = message.value[len(self.parent().hostname_filter):]
#             data = pickle.loads(message)
#
#             if 'data' in data['processing_ret']:
#                 #data['processing_ret']['data'] = pd.read_msgpack(data['processing_ret']['data'])
#                 data['processing_ret']['data'] = data['processing_ret']['data'].decode()
#
#             if data['type'] == 'spectroscopy':
#                 if data['processing_ret']['type'] == 'interpolate':
#                     self.received_interp_data.emit(data)
#                 if data['processing_ret']['type'] == 'bin':
#                     self.received_bin_data.emit(data)
#                 if data['processing_ret']['type'] == 'request_interpolated_data':
#                     self.received_req_interp_data.emit(data)
