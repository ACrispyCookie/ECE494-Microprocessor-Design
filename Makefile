VIVADO ?= vivado
EXPERIMENT ?= baseline
RTL_TEST_ARGS ?=
RTL_BENCH_ARGS ?=

CORE_DIR_baseline := cv32e40p_baseline
CORE_DIR_no-mul-forwarding := cv32e40p_no_mul_forwarding
CORE_DIR_no-alu-forwarding := cv32e40p_no_alu_forwarding
CORE_DIR_no-alu-mul-forwarding := cv32e40p_no_alu_mul_forwarding
CORE_DIR ?= $(CORE_DIR_$(EXPERIMENT))
BUILD_DIR ?= build/vivado-$(EXPERIMENT)
PROJECT_NAME ?= cv32e40p-zedboard-project
CLOCK_PERIOD_baseline := 15.000
CLOCK_PERIOD_no-mul-forwarding := 14.000
CLOCK_PERIOD_no-alu-forwarding := 15.000
CLOCK_PERIOD_no-alu-mul-forwarding := 15.000
CLOCK_PERIOD ?= $(CLOCK_PERIOD_$(EXPERIMENT))

.PHONY: all init-core-submodules baseline no-mul-forwarding no-alu-forwarding no-alu-mul-forwarding rtl-tests rtl-tests-baseline rtl-tests-no-mul-forwarding rtl-tests-no-alu-forwarding rtl-tests-no-alu-mul-forwarding rtl-benchmarks rtl-benchmarks-baseline rtl-benchmarks-no-mul-forwarding rtl-benchmarks-no-alu-forwarding rtl-benchmarks-no-alu-mul-forwarding reports utilization-reports utilization-plots timing-reports timing-plots clean

all: init-core-submodules
	$(VIVADO) -mode batch -source cv32e40p-zedboard-project.tcl -tclargs --experiment $(EXPERIMENT) --core_dir $(CORE_DIR) --build_dir $(BUILD_DIR) --project_name $(PROJECT_NAME) --clock_period $(CLOCK_PERIOD)

init-core-submodules:
	@if [ -z "$(CORE_DIR)" ]; then \
		echo "ERROR: Unknown EXPERIMENT=$(EXPERIMENT); CORE_DIR is empty" >&2; \
		exit 1; \
	fi
	@if [ ! -e "$(CORE_DIR)/.git" ]; then \
		echo "Initializing submodule $(CORE_DIR)..."; \
		git submodule update --init --recursive -- "$(CORE_DIR)"; \
	else \
		echo "Initializing nested submodules under $(CORE_DIR)..."; \
		git -C "$(CORE_DIR)" submodule update --init --recursive; \
	fi

baseline:
	$(MAKE) EXPERIMENT=baseline all

no-mul-forwarding:
	$(MAKE) EXPERIMENT=no-mul-forwarding all

no-alu-forwarding:
	$(MAKE) EXPERIMENT=no-alu-forwarding all

no-alu-mul-forwarding:
	$(MAKE) EXPERIMENT=no-alu-mul-forwarding all

rtl-tests:
	python3 scripts/run-rtl-tests.py $(RTL_TEST_ARGS)

rtl-tests-baseline:
	python3 scripts/run-rtl-tests.py --version baseline $(RTL_TEST_ARGS)

rtl-tests-no-mul-forwarding:
	python3 scripts/run-rtl-tests.py --version no_mul_forwarding $(RTL_TEST_ARGS)

rtl-tests-no-alu-forwarding:
	python3 scripts/run-rtl-tests.py --version no_alu_forwarding $(RTL_TEST_ARGS)

rtl-tests-no-alu-mul-forwarding:
	python3 scripts/run-rtl-tests.py --version no_alu_mul_forwarding $(RTL_TEST_ARGS)

rtl-benchmarks:
	python3 scripts/run-rtl-benchmarks.py $(RTL_BENCH_ARGS)

rtl-benchmarks-baseline:
	python3 scripts/run-rtl-benchmarks.py --version baseline $(RTL_BENCH_ARGS)

rtl-benchmarks-no-mul-forwarding:
	python3 scripts/run-rtl-benchmarks.py --version no_mul_forwarding $(RTL_BENCH_ARGS)

rtl-benchmarks-no-alu-forwarding:
	python3 scripts/run-rtl-benchmarks.py --version no_alu_forwarding $(RTL_BENCH_ARGS)

rtl-benchmarks-no-alu-mul-forwarding:
	python3 scripts/run-rtl-benchmarks.py --version no_alu_mul_forwarding $(RTL_BENCH_ARGS)

reports:
	./report.sh --comparison --report all --create-projects --yes --stage post-implementation

utilization-reports:
	./report.sh --comparison --report utilization --yes

utilization-plots:
	python3 scripts/plot-utilization.py

timing-reports:
	./report.sh --comparison --report timing --yes

timing-plots:
	python3 scripts/plot-timing.py

clean:
	rm -rf build/ .Xil *.log *.jou *.str
