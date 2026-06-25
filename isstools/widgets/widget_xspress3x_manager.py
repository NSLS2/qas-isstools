import re
import time as ttime
import bluesky.plan_stubs as bps

import numpy as np
import pkg_resources

from PyQt5 import uic,  QtCore
from PyQt5.QtWidgets import QFrame, QSizePolicy
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar)
from matplotlib.figure import Figure
from matplotlib.widgets import Cursor
from PyQt5.Qt import QSplashScreen, QObject
import numpy


from isstools.elements.figure_update import update_figure


ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_xspress3x_manager.ui')


class UIXSXManager(*uic.loadUiType(ui_path)):

    def __init__(self,
                 service_plan_funcs,

                 xsx,
                 RE,
                 *args,
                 **kwargs):

        super().__init__(*args, **kwargs)
        self.setupUi(self)

        self.addCanvas()
        self.service_plan_funcs = service_plan_funcs
        self.RE = RE
        self.xsx = xsx
        self.roi_plots = []

        self.timer_update_time = QtCore.QTimer(self)
        self.timer_update_time.setInterval(1000)
        self.timer_update_time.timeout.connect(self.update_roi_labels)
        self.timer_update_time.start()


        self.push_xs3_acquire.clicked.connect(self.xs3_acquire)
        
        self.colors = ['r', 'k', 'b', 'g', 'm', 'k', 'y']
        self.num_channels = [1, 3, 4, 5, 6, 7, 8]
        self.num_4_channels = [3, 4, 5, 6, 7, 8]
        self.num_rois = [1 ,2, 3, 4]
        self.roi_values = numpy.zeros((8, 4, 2))
        self.acquired = 0


        self.checkbox_ch = 'checkBox_ch{}_show'
        for indx in self.num_channels:
             getattr(self, self.checkbox_ch.format(indx)).stateChanged.connect(self.plot_traces)
        
        self.checkbox_roi = 'checkBox_roi{}_show'
        for indx in self.num_rois:
             getattr(self, self.checkbox_roi.format(indx)).stateChanged.connect(self.update_roi_plot)

        self.lowlim_width = ['min_x', 'size_x']

        self.lo_hi = ['lo','hi']
        self.lo_hi_def = {'lo':'low', 'hi':'high'}
        self.spinbox_roi = 'spinBox_ch{}_roi{}_{}'
        self.label_roi_rbk = 'label_ch{}_roi{}_{}_rbk'

        # Fix ROIs only for 4 element SDD
        # self.checkbox_fix_rois = 'checkBox_ch{}_fix_roi'

        for i in [1 , 2 , 3]:
            getattr(self, f"frame_{i}").setFrameShape(QFrame.HLine)
            getattr(self, f"frame_{i}").setFrameShadow(QFrame.Sunken)
            getattr(self, f"frame_{i}").setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            row = self.gridLayout_4.getItemPosition(self.gridLayout_4.indexOf(getattr(self, f"frame_{i}")))[0]
            self.gridLayout_4.addWidget(getattr(self, f"frame_{i}"), row, 0, 1, self.gridLayout_4.columnCount())


        # for indx in self.num_4_channels:
        #     checkbox_object = getattr(self, f"checkBox_ch{indx}_fix_roi")

            # checkbox_name = self.checkbox_fix_rois.format(indx)
            # checkbox_object = getattr(self, checkbox_name)
            # checkbox_object.stateChanged.connect(self.fix_rois)


        self.update_spinboxes()

        for indx_ch in self.num_channels:
            for indx_roi in self.num_rois:
                for indx_lo_hi in ['lo', 'hi']:
                    getattr(self, f"spinBox_ch{indx_ch}_roi{indx_roi}_{indx_lo_hi}").editingFinished.connect(self.set_roi_value)

    # def fix_rois(self):
    #     sender = QObject()
    #     sender_object = sender.sender().objectName()
    #     indx_ch = sender_object[11]
    #
    #     if sender.sender().isChecked():
    #         for jj in range(2):
    #             # repeat to make sure no values are forced
    #             for indx_roi in range(self.num_rois):
    #                 for indx_lo_hi in range(2):
    #                     spinbox_name_ch1 = self.spinbox_roi.format(1, indx_roi + 1, self.lo_hi[indx_lo_hi])
    #                     spinbox_object_ch1 = getattr(self, spinbox_name_ch1)
    #                     value = spinbox_object_ch1.value()
    #                     spinbox_name = self.spinbox_roi.format(indx_ch, indx_roi + 1, self.lo_hi[indx_lo_hi])
    #                     spinbox_object = getattr(self, spinbox_name)
    #                     spinbox_object.setValue(value)
    #                     spinbox_object.setEnabled(False)
    #     else:
    #         for indx_roi in range(self.num_rois):
    #             for indx_lo_hi in range(2):
    #                 spinbox_name = self.spinbox_roi.format(indx_ch, indx_roi + 1, self.lo_hi[indx_lo_hi])
    #                 spinbox_object = getattr(self, spinbox_name)
    #                 spinbox_object.setEnabled(True)

    def set_roi_value(self):
        print('Setting Roi')
        proceed = False
        sender = QObject()
        sender_object = sender.sender().objectName()

        indx_ch = int(sender_object[10:11])
        indx_roi = int(sender_object[15:16])
        lo_hi = sender_object[17:]
        value = sender.sender().value()
        if lo_hi == 'lo':
            self.set_roi_values_for_ch_roi_limit(indx_ch, indx_roi, 'min_x', value)
        else:
            self.set_roi_values_for_ch_roi_limit(indx_ch, indx_roi, 'size_x', value)
        self.update_roi_labels()



        # signal = self.get_roi_signal(indx_ch, indx_roi, self.lo_hi.index(lo_hi))
        # value = sender.sender().value()
        # #validate  limits
        # if lo_hi == 'lo':
        #     counter_signal = self.get_roi_signal(indx_ch, indx_roi, self.lo_hi.index('hi'))
        #     counter_value = counter_signal.get()*10
        #     if value < counter_value:
        #         proceed = True
        # elif lo_hi == 'hi':
        #     counter_signal = self.get_roi_signal(indx_ch, indx_roi, self.lo_hi.index('lo'))
        #     counter_value = counter_signal.get()*10
        #     if value > counter_value:
        #         proceed = True
        # if proceed:
        #     signal.put(int(value/10))
        #     self.roi_values[int(indx_ch)-1, int(indx_roi)-1, self.lo_hi.index(lo_hi)] = value
        # else:
        #     sender.sender().setValue(counter_value)
        self.update_roi_plot()

    def set_roi_values_for_ch_roi_limit(self, indx_ch, indx_roi, indx_lo_hi, value):
        signal_ch = getattr(self.xsx, f'channel{indx_ch:02}')
        signal_roi = getattr(signal_ch, f'mcaroi{indx_roi:02}')
        getattr(signal_roi, indx_lo_hi).put(value)
        if indx_lo_hi == 'min_x':
            self.roi_values[indx_ch-1, indx_roi-1, 0] = value
        else:
            self.roi_values[indx_ch-1, indx_roi-1, 1] = value

    def get_roi_signal(self, indx_ch, indx_roi, indx_lo_hi):
        signal_ch = getattr(self.xsx, f'channel{indx_ch:02}')
        signal_roi = getattr(signal_ch, f'mcaroi{indx_roi:02}')
        signal = getattr(signal_roi, indx_lo_hi).get()
        return signal


    def update_roi_labels(self):
        for indx_ch in self.num_channels:
            for indx_roi in self.num_rois:
                for indx_lo_hi in ['lo', 'hi']:
                    label_object = getattr(self, f"label_ch{indx_ch}_roi{indx_roi}_{indx_lo_hi}_rbk")
                    if indx_lo_hi == 'lo':
                        value = self.get_roi_signal(indx_ch, indx_roi, 'min_x')
                        numpy_index = 0
                    else:
                        value = self.get_roi_signal(indx_ch, indx_roi, 'size_x')
                        numpy_index = 1
                    label_object.setText(str(value))


        try:
            for ch in self.num_channels:
                for roi in self.num_rois:
                    value = getattr(getattr(self.xsx, f'channel{ch:02}'), f'mcaroi{roi:02}').total_rbv.get()
                    # value = getattr(getattr(getattr(self.xs, 'channel' + str(ch)), 'rois'), 'roi' + f'{roi:02d}').value.get()
                    getattr(self, 'label_ch' + str(ch) + '_roi' + str(roi) + '_value').setText(f"{value:.0f}")

                    if value < 450000:
                        getattr(self, 'label_ch' + str(ch) + '_roi' + str(roi) + '_value').setStyleSheet("background-color: lime")
                    elif value > 450000 and value < 500000:
                        getattr(self, 'label_ch' + str(ch) + '_roi' + str(roi) + '_value').setStyleSheet("background-color: yellow")
                    else:
                        getattr(self, 'label_ch' + str(ch) + '_roi' + str(roi) + '_value').setStyleSheet(
                            "background-color: red")


        except Exception as e :
            print(f'Error in updating ROI : {e}')




    def update_spinboxes(self):

        for indx_ch in self.num_channels:
            for indx_roi in self.num_rois:
                for indx_lo_hi in ['lo', 'hi']:
                    spinbox_object = getattr(self, f"spinBox_ch{indx_ch}_roi{indx_roi}_{indx_lo_hi}")
                    if indx_lo_hi == 'lo':
                        value = self.get_roi_signal(indx_ch, indx_roi, 'min_x')
                        numpy_index = 0
                    else:
                        value = self.get_roi_signal(indx_ch, indx_roi, 'size_x')
                        numpy_index = 1

                    spinbox_object.setValue(value)
                    self.roi_values[indx_ch-1, indx_roi-1, numpy_index] = value
        self.update_roi_plot()

    def update_roi_plot(self):
        for roi_plot in self.roi_plots:
            list(self.figure_xs3_mca.ax.lines).remove(roi_plot[0])
        self.roi_plots = []
        ylims=self.figure_xs3_mca.ax.get_ylim()
        for i, indx_ch in enumerate(self.num_channels):
            show_ch = getattr(self, 'checkBox_ch{}_show'.format(indx_ch)).isChecked()
            for indx_roi in self.num_rois:
                show_roi = getattr(self, 'checkBox_roi{}_show'.format(indx_roi)).isChecked()
                for indx_hi_lo in range(2):
                    if show_ch and show_roi:
                        color = self.colors[i]
                        value = self.roi_values[indx_ch-1,indx_roi-1,indx_hi_lo]
                        if indx_hi_lo == 0:
                            buffer = value
                        else:
                            value = value + buffer
                        h = self.figure_xs3_mca.ax.plot([value, value], [0, ylims[1] * 0.85], color, linestyle='dashed',
                                                    linewidth=0.5)
                        self.roi_plots.append(h)
                        # self.roi_plots.append(h)

        self.canvas_xs3_mca.draw_idle()

    def addCanvas(self):
        self.figure_xs3_mca = Figure()
        self.figure_xs3_mca.set_facecolor(color='#FcF9F6')
        self.canvas_xs3_mca = FigureCanvas(self.figure_xs3_mca)
        self.figure_xs3_mca.ax = self.figure_xs3_mca.add_subplot(111)
        self.toolbar_xs3_mca = NavigationToolbar(self.canvas_xs3_mca, self, coordinates=True)
        self.plot_xs3_mca.addWidget(self.toolbar_xs3_mca)
        self.plot_xs3_mca.addWidget(self.canvas_xs3_mca)
        self.canvas_xs3_mca.draw_idle()
        #self.cursor_xs3_mca = Cursor(self.figure_xia_all_graphs.ax, useblit=True, color='green', linewidth=0.75)
        self.figure_xs3_mca.ax.clear()

    def xs3_acquire(self):
        self.roi_plots = []
        print('Xspress3x acquisition starting...')
        plan = self.service_plan_funcs['xsx_count']
        acq_time = self.spinBox_acq_time.value()
        self.RE(plan(acq_time = acq_time))
        self.acquired = True
        self.plot_traces()
        self.update_roi_plot()
        self.canvas_xs3_mca.draw_idle()

    def plot_traces(self):
        #THis method plot the MCA signal
        update_figure([self.figure_xs3_mca.ax], self.toolbar_xs3_mca, self.canvas_xs3_mca)
        self.roi_plots = []
        if self.acquired:
            for i, indx in enumerate(self.num_channels):
                if getattr(self, f"checkBox_ch{indx}_show").isChecked():
                    mca = getattr(self.xsx, f"channel{indx:02}").mca.array_data.get()
                    # energy = np.array(list(range(len(mca))))*10
                    energy = np.array(list(range(len(mca))))
                    self.figure_xs3_mca.ax.plot(energy,mca,self.colors[i], label = 'Channel {}'.format(indx))
                    self.figure_xs3_mca.ax.legend(loc=1)
        self.update_roi_plot()


