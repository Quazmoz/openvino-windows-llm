from runtime import device_check


def test_normalize_device_defaults_and_casing():
    assert device_check.normalize_device(None) == "CPU"
    assert device_check.normalize_device("") == "CPU"
    assert device_check.normalize_device("  npu ") == "NPU"
    assert device_check.normalize_device("gpu") == "GPU"


def test_is_device_available_auto_always_true():
    assert device_check.is_device_available("AUTO", [])
    assert device_check.is_device_available("auto", ["CPU"])


def test_is_device_available_matches_plain_and_indexed():
    avail = ["CPU", "GPU.0", "NPU"]
    assert device_check.is_device_available("CPU", avail)
    assert device_check.is_device_available("GPU", avail)  # GPU matches GPU.0
    assert device_check.is_device_available("GPU.1", avail)  # base GPU matches
    assert device_check.is_device_available("NPU", avail)


def test_is_device_available_rejects_absent_device():
    assert not device_check.is_device_available("NPU", ["CPU", "GPU"])


def test_is_device_available_empty_list_allows_only_cpu():
    assert device_check.is_device_available("CPU", [])
    assert not device_check.is_device_available("GPU", [])


def test_probe_functions_return_safe_types_without_openvino():
    # OpenVINO is absent in this environment; the probes must degrade gracefully.
    assert isinstance(device_check.is_openvino_available(), bool)
    assert isinstance(device_check.available_devices(), list)
    assert isinstance(device_check.device_details(), list)
