from bluesky.callbacks import CallbackBase
from bluesky_tiled_plugins.clients.bluesky_event_stream import BlueskyEventStream
from bluesky_tiled_plugins.clients.bluesky_run import BlueskyRun
from tiled.utils import OneShotCachedMap
from xas.process import process_interpolate_locally, wait_for_tiled_run


def _processing_client(client):
    """Select plugin clients without changing the profile's shared client.

    Databroker may register clients for the same Tiled specs. Pin dispatch for
    this callback, including clients reconstructed by wait_for_tiled_run, so
    SQL runs expose validate() and their streams use the matching layout.
    """
    # A shallow copy of OneShotCachedMap shares its registrations. Build an
    # independent lazy map so the profile's databroker clients stay intact.
    structure_clients = OneShotCachedMap({
        key: lambda key=key: client.structure_clients[key]
        for key in client.structure_clients
    })
    structure_clients.set("BlueskyRun", lambda: BlueskyRun)
    structure_clients.set("BlueskyEventStream", lambda: BlueskyEventStream)
    return client.new_variation(structure_clients=structure_clients)


class ProcessingCallback(CallbackBase):
    def __init__(self,db,draw_func_interp, draw_func_binned, thread, tiled_client=None):
        self.db = db
        self.draw_func_interp = draw_func_interp
        self.draw_func_binned = draw_func_binned
        self.thread = thread
        self.tiled_client = _processing_client(tiled_client)
        super().__init__()

    def stop(self,doc):
        print('Processing Callback New')
        print('>>>>>> stopped >>>>>>')
        if doc['exit_status'] == 'success':
            self.thread.doc = doc
            self.thread.start()
        else:
            print('Scan Failed')
        uid = doc['run_start']
        # RunEngine Stop can arrive before the buffered TiledWriter finishes.
        # Wait for persisted Stop via WebSocket before validating the scan.
        run = wait_for_tiled_run(self.tiled_client[f"qas/migration/{uid}"])
        print("Validate")
        print(run.validate(raise_on_error=True))
        process_interpolate_locally(
            run,
            draw_func_interp=self.draw_func_interp,
        )


class ProcessingCallback_old(CallbackBase):
    def __init__(self,db,draw_func_interp, draw_func_binned, tiled_client=None):
        self.db = db
        self.draw_func_interp = draw_func_interp
        self.draw_func_binned = draw_func_binned
        self.tiled_client = _processing_client(tiled_client)
        super().__init__()

    def stop(self,doc):
        print('Processing Callback Old')
        print('>>>>>> stopped')
        uid = doc['run_start']
        run = wait_for_tiled_run(self.tiled_client[uid])
        print("Validate")
        print(run.validate())
        process_interpolate_locally(
            run,
            draw_func_interp=self.draw_func_interp,
        )


class PilatusCallback(CallbackBase):
    def __init__(self, db):
        self.db = db
        super().__init__()

    def stop(self, doc):
        print(">>>>>>>>>> Pilatus stopped")
        path = '/nsls2/data/qas-new/legacy/processed/{year}/{cycle}/{PROPOSAL}XRD'.format(**doc)
        file_prefix = '{start[sample_name]}-{start[exposure_time]:.1f}s-{start[scan_id]}-'.format(**doc)
        
