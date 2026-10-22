"""Check the ingestion boundary without requiring a beamline environment."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import pytest


@pytest.fixture
def callbacks(monkeypatch):
    bluesky = ModuleType("bluesky")
    bluesky.callbacks = ModuleType("bluesky.callbacks")
    bluesky.callbacks.CallbackBase = object
    xas = ModuleType("xas")
    xas.process = ModuleType("xas.process")
    xas.process.process_interpolate_locally = Mock()
    xas.process.wait_for_tiled_run = Mock()
    for module in (bluesky, bluesky.callbacks, xas, xas.process):
        monkeypatch.setitem(sys.modules, module.__name__, module)

    path = (
        Path(__file__).resolve().parents[1]
        / "isstools/process_callbacks/callback.py"
    )
    spec = importlib.util.spec_from_file_location("processing_callback", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(params=["ProcessingCallback", "ProcessingCallback_old"])
def callback_case(callbacks, request):
    pending_run = Mock()
    thread = Mock()
    draw = Mock()
    is_current = request.param == "ProcessingCallback"
    key = "qas/migration/scan-uid" if is_current else "scan-uid"
    kwargs = {"thread": thread} if is_current else {}
    callback = getattr(callbacks, request.param)(
        db=Mock(), draw_func_interp=draw, draw_func_binned=Mock(),
        tiled_client={key: pending_run}, **kwargs
    )
    return callback, pending_run, draw


def test_waits_before_validating_and_processing(callbacks, callback_case):
    callback, pending_run, draw = callback_case
    completed_run = Mock()
    order = []

    def finish_ingestion(run):
        assert run is pending_run
        completed_run.validate.assert_not_called()
        callbacks.process_interpolate_locally.assert_not_called()
        order.append("persisted stop")
        return completed_run

    callbacks.wait_for_tiled_run.side_effect = finish_ingestion
    completed_run.validate.side_effect = lambda **kwargs: order.append("validate")
    callbacks.process_interpolate_locally.side_effect = (
        lambda *args, **kwargs: order.append("process")
    )

    callback.stop({"run_start": "scan-uid", "exit_status": "success"})

    assert order == ["persisted stop", "validate", "process"]
    callbacks.wait_for_tiled_run.assert_called_once_with(pending_run)
    callbacks.process_interpolate_locally.assert_called_once_with(
        completed_run, draw_func_interp=draw
    )
    pending_run.validate.assert_not_called()
    pending_run.refresh.assert_not_called()
    completed_run.refresh.assert_not_called()


def test_wait_failure_prevents_processing(callbacks, callback_case):
    callback, pending_run, _ = callback_case
    callbacks.wait_for_tiled_run.side_effect = TimeoutError("ingestion incomplete")

    with pytest.raises(TimeoutError, match="ingestion incomplete"):
        callback.stop({"run_start": "scan-uid", "exit_status": "success"})

    pending_run.validate.assert_not_called()
    callbacks.process_interpolate_locally.assert_not_called()


def test_current_callback_preserves_thread_handoff(callbacks):
    thread = Mock()
    callback = callbacks.ProcessingCallback(
        Mock(), Mock(), Mock(), thread,
        tiled_client={"qas/migration/scan-uid": Mock()},
    )
    doc = {"run_start": "scan-uid", "exit_status": "success"}

    callback.stop(doc)

    assert thread.doc is doc
    thread.start.assert_called_once_with()


def test_validation_failure_prevents_processing(callbacks):
    completed_run = Mock()
    completed_run.validate.side_effect = ValueError("invalid scan")
    callbacks.wait_for_tiled_run.return_value = completed_run
    callback = callbacks.ProcessingCallback(
        Mock(), Mock(), Mock(), Mock(),
        tiled_client={"qas/migration/scan-uid": Mock()},
    )

    with pytest.raises(ValueError, match="invalid scan"):
        callback.stop({"run_start": "scan-uid", "exit_status": "success"})

    completed_run.validate.assert_called_once_with(raise_on_error=True)
    callbacks.process_interpolate_locally.assert_not_called()
