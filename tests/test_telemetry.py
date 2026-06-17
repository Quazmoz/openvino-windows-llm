from app import telemetry


def test_dir_size_bytes_sums_nested_files(tmp_path):
    (tmp_path / "a.bin").write_bytes(b"x" * 1000)
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "b.bin").write_bytes(b"y" * 2000)
    assert telemetry.dir_size_bytes(tmp_path) == 3000


def test_dir_size_bytes_missing_path_is_zero(tmp_path):
    assert telemetry.dir_size_bytes(tmp_path / "nope") == 0


def test_disk_stats_reports_footprint_and_real_volume(tmp_path):
    (tmp_path / "model.bin").write_bytes(b"z" * (1024 * 1024))  # 1 MiB
    stats = telemetry.disk_stats(tmp_path)
    assert set(stats) == {"models_gb", "total_gb", "free_gb"}
    assert stats["total_gb"] > 0  # real volume size, not just the footprint
    assert stats["free_gb"] >= 0
    assert stats["models_gb"] >= 0


def test_disk_stats_nonexistent_dir_resolves_to_existing_ancestor(tmp_path):
    stats = telemetry.disk_stats(tmp_path / "does" / "not" / "exist")
    assert stats["models_gb"] == 0.0
    assert stats["total_gb"] > 0  # walked up to a real volume


def test_memory_and_cpu_stats_return_dicts():
    assert isinstance(telemetry.memory_stats(), dict)
    assert "percent" in telemetry.cpu_stats()
