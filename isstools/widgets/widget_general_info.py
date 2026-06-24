from PyQt5 import uic, QtGui, QtCore
import pkg_resources
import requests
import urllib.request



from isstools.dialogs import UpdateUserDialog
from timeit import default_timer as timer

ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_general_info.ui')


class UIGeneralInfo(*uic.loadUiType(ui_path)):
    def __init__(self,
                 accelerator=None,
                 mono = None,
                 RE = None,
                 db = None,
                 parent_gui = None,
                 *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.setupUi(self)
        # Start QTimer to display current day and time
        self.timer_update_time = QtCore.QTimer(self)
        self.timer_update_time.setInterval(100)
        self.timer_update_time.timeout.connect(self.update_time)
        self.timer_update_time.start()

        # self.timer_update_weather = QtCore.QTimer(self)
        # self.timer_update_weather.singleShot(0, self.update_weather)
        # self.timer_update_weather.setInterval(1000*60*5)
        # self.timer_update_weather.timeout.connect(self.update_weather)
        # self.timer_update_weather.start()


        self.mono = mono
        self.parent_gui = parent_gui

        self.RE = RE
        self.db = db
        if self.RE is not None:
            self.RE.is_aborted = False
            self.timer_update_user_info = QtCore.QTimer()
            self.timer_update_user_info.timeout.connect(self.update_user_info)
            self.timer_update_user_info.start(60*1000)
            self.timer_update_user_info.singleShot(0, self.update_user_info)
            self.push_set_user_info.clicked.connect(self.set_user_info)
        else:
            self.push_update_user.setEnabled(False)


        # Initialize general settings
        self.accelerator = accelerator
        self.accelerator.beam_current.subscribe(self.update_beam_current)
        self.accelerator.status.subscribe(self.update_accelerator_status)

        self.lineEdit_mono_energy.returnPressed.connect(self.update_mono_energy)
        self.lineEdit_mono_energy.setStyleSheet('border: 2px solid green;')

        # self.mono.energy.user_readback.subscribe(self.update_mono_value)

    # def update_weather(self):
    #     # try:
    #     #     current_weather = requests.get(
    #     #         'http://api.openweathermap.org/data/2.5/weather?zip=11973&APPID=a3be6bc4eaf889b154327fadfd9d6532').json()
    #     #     string_current_weather  = current_weather['weather'][0]['main'] + ' in Upton, NY,  it is {0:.0f} °F outside,\
    #     #         humidity is {1:.0f}%'\
    #     #         .format(((current_weather['main']['temp']-273)*1.8+32), current_weather['main']['humidity'])
    #     #     icon_url = 'http://openweathermap.org/img/w/' + current_weather['weather'][0]['icon'] + '.png'
    #     #     image = QtGui.QImage()
    #     #     image.loadFromData(urllib.request.urlopen(icon_url).read())
    #     #     self.label_current_weather_icon.setPixmap(QtGui.QPixmap(image))
    #     # except:
    #     string_current_weather = 'Weather information not available'
    #     self.label_current_weather.setText(string_current_weather)

    # def update_mono_value(self, value, **kwargs):
    #     try:
    #         self.label_mono_value.setText(f"{value:.1f} eV")
    #         self.lineEdit_mono_energy.setText(f"{value:.1f} eV")
    #     except:
    #         pass

    def update_mono_energy(self):
        _read_desired_energy = self.lineEdit_mono_energy.text()
        try:
            _desired_energy = float(_read_desired_energy.split()[0])
            self.lineEdit_mono_energy.setText(f"{_desired_energy:.1f} eV")
            if (_desired_energy) < 4500 or (_desired_energy > 30000):
                self.lineEdit_mono_energy.setStyleSheet('border: 2px solid red;')
                print('Energy value outside the range')
            else:
                self.lineEdit_mono_energy.setStyleSheet('border: 2px solid green;')
                self.mono.energy.user_setpoint.set(_desired_energy).wait()
        except ValueError:
            self.lineEdit_mono_energy.setStyleSheet('border: 2px solid red;')




    def update_time(self):
        self.label_current_time.setText(
            '{0}'.format(QtCore.QDateTime.currentDateTime().toString('dddd, MMMM d, yyyy h:mm:ss ap')))

        _energy = self.mono.energy.user_readback.get()
        try:
            self.label_mono_value.setText(f"{_energy:.1f} eV")
            # self.lineEdit_mono_energy.setText(f"{_energy:.1f} eV")
        except:
            pass

    def update_beam_current(self, **kwargs):
        self.label_beam_current.setText('Beam current: {:.1f} mA'.format(kwargs['value']))

    def update_accelerator_status(self, **kwargs):
        accelerator_status = self.accelerator.status.enum_strs[kwargs['value']]
        # nsls_ii.status.enum_strs = ('Operations',
        #                             'Setup',
        #                             'Accel Studies',
        #                             'Beamline Studies',
        #                             'Failure',
        #                             'Maintenance',
        #                             'Shutdown',
        #                             'Unscheduled Ops',
        #                             'Decay Mode Ops')
        # if kwargs['value'] == 0:
        #     accelerator_status_color = "color: rgb(19,139,67)"
        #     accelerator_status_indicator = "background-color: rgb(95,249,95)"
        # elif kwargs['value'] == 1:
        #     accelerator_status_color = "color: rgb(209,116,42)"
        #     accelerator_status_indicator = "background-color: rgb(246,229,148)"
        # elif kwargs['value'] == 2:
        #     accelerator_status_color = "color: rgb(209,116,42)"
        #     accelerator_status_indicator = "background-color: rgb(209,116,42)"
        # elif kwargs['value'] == 3:
        #     accelerator_status_color = "color: rgb(237,30,30)"
        #     accelerator_status_indicator = "background-color: rgb(237,30,30)"
        # elif kwargs['value'] == 4:
        #     accelerator_status_color = "color: rgb(209,116,42)"
        #     accelerator_status_indicator = "background-color: rgb(200,149,251)"
        # elif kwargs['value'] == 5:
        #     accelerator_status_color = "color: rgb(190,190,190)"
        #     accelerator_status_indicator = "background-color: rgb(190,190,190)"
        # elif kwargs['value'] == 6:
        #     accelerator_status_color = "color: rgb(19,139,67)"
        #     accelerator_status_indicator = "background-color: rgb(0,177,0)"
        # else:
        #     accelerator_status_color = "color: rgb(0,0,0)"
        #     accelerator_status_indicator = "background-color: rgb(0,0,0)"

        self.label_accelerator_status.setText(f"Operating Mode: {accelerator_status}")
        # These stylesheet changing calls break the GUI as they are executed in
        #   a background thread. Need to use proper Signal/Slot approach.
        # self.label_accelerator_status.setStyleSheet(accelerator_status_color)
        # self.label_accelerator_status_indicator.setStyleSheet(accelerator_status_indicator)

    def update_user_info(self):
        # self.label_user_info.setText('PI: {} Proposal: {} SAF: {} '.
        #                              format(self.RE.md['PI'], self.RE.md['PROPOSAL'], self.RE.md['SAF']))

        self.label_user_name.setText(f"{self.RE.md['PI']}") # PI
        self.label_proposal.setText(f"{self.RE.md['PROPOSAL']}") #Proposal
        self.label_saf.setText(f"{self.RE.md['SAF']}") # SAF

        self.cycle = ['', 'Spring', 'Summer', 'Fall']
        cycleNr = self.RE.md.get('cycle', '').split('-')[-1]
        self.label_current_cycle.setText(
            # 'NSLS-II Cycle: {} {}'.format(self.RE.md['year'], self.cycle[self.RE.md['cycle']]))
            'NSLS-II Cycle: {}-{}'.format(self.RE.md['year'], cycleNr))

    def set_user_info(self):
        dlg = UpdateUserDialog.UpdateUserDialog(self.RE.md['year'], self.RE.md['cycle'], self.RE.md['PROPOSAL'],
                                                self.RE.md['SAF'], self.RE.md['PI'], parent=self)
        if dlg.exec_():
            start = timer()
            self.RE.md['year'], self.RE.md['cycle'], self.RE.md['PROPOSAL'], self.RE.md['SAF'], self.RE.md[
                'PI'] = dlg.getValues()
            print('2')
            stop1 = timer()
            self.update_user_info()
            print('3')
            stop2 = timer()
            print(stop1 - start)
            print(stop2 - start)
