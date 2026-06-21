import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run-rtl-benchmarks.py"


def load_runner():
    spec = importlib.util.spec_from_file_location("run_rtl_benchmarks", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_resolve_versions_supports_all_and_positional_aliases():
    runner = load_runner()
    assert runner.resolve_versions(["all"]) == [
        "baseline",
        "no_mul_forwarding",
        "no_alu_forwarding",
        "no_alu_mul_forwarding",
    ]
    assert runner.resolve_versions(["1"]) == ["no_mul_forwarding"]
    assert runner.resolve_versions(["2"]) == ["no_alu_forwarding"]
    assert runner.resolve_versions(["3"]) == ["no_alu_mul_forwarding"]
    assert runner.resolve_versions(["baseline", "no-mul-forwarding"]) == ["baseline", "no_mul_forwarding"]


def test_resolve_benchmarks_supports_all_and_preserves_requested_order():
    runner = load_runner()
    assert runner.resolve_benchmarks(["all"]) == runner.DEFAULT_BENCHMARKS
    assert runner.resolve_benchmarks(["mm", "vvadd"]) == ["mm", "vvadd"]


def test_parse_metrics_extracts_cycles_roi_and_status():
    runner = load_runner()
    log = """
    [TB] Reset released at time 95000
    [TB] Benchmark ROI started at cycle 12
    [TB] Benchmark ROI stopped at cycle 99
    [TB] Saw DONE store at cycle 111 time 123000
    [METRIC] total_cycles=111 roi_cycles=87 return_code=0 signature=0x12345678
    [PASS] RTL benchmark completed successfully
    """
    metrics = runner.parse_metrics(log)
    assert metrics.total_cycles == 111
    assert metrics.roi_cycles == 87
    assert metrics.return_code == 0
    assert metrics.signature == "0x12345678"
    assert metrics.status == "PASS"


def test_make_memory_image_word_pads_little_endian_bytes():
    runner = load_runner()
    assert runner.words_from_bytes(b"\x78\x56\x34\x12\xaa") == ["12345678", "000000aa"]
