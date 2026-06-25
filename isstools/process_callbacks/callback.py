from bluesky.callbacks import CallbackBase
from xas.process import process_interpolate_bin_with_tiled



class ProcessingCallback(CallbackBase):
    def __init__(self,db,draw_func_interp, draw_func_binned, thread):
        self.db = db
        self.draw_func_interp = draw_func_interp
        self.draw_func_binned = draw_func_binned
        self.thread = thread
        super().__init__()

    def stop(self,doc):
        print('>>>>>> stopped >>>>>>')
        if doc['exit_status'] == 'success':
            self.thread.doc = doc
            self.thread.start()
        else:
            print('Scan Failed')


class ProcessingCallback_old(CallbackBase):
    def __init__(self,db,draw_func_interp, draw_func_binned, tiled_client=None):
        self.db = db
        self.draw_func_interp = draw_func_interp
        self.draw_func_binned = draw_func_binned
        self.tiled_client=tiled_client
        super().__init__()

    def stop(self,doc):
        print('>>>>>> stopped')
        uid = doc['run_start']
        # client = from_uri("https://tiled.nsls2.bnl.gov", remember_me=False, username=None)[f"qas/migration/{uid}"]
        process_interpolate_bin_with_tiled(self.tiled_client[uid], draw_func_interp=self.draw_func_interp)


class PilatusCallback(CallbackBase):
    def __init__(self, db):
        self.db = db
        super().__init__()

    def stop(self, doc):
        print(">>>>>>>>>> Pilatus stopped")
        path = '/nsls2/data/qas-new/legacy/processed/{year}/{cycle}/{PROPOSAL}XRD'.format(**doc)
        file_prefix = '{start[sample_name]}-{start[exposure_time]:.1f}s-{start[scan_id]}-'.format(**doc)
        



