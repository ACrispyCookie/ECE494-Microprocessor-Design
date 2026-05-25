VIVADO ?= vivado
EXPERIMENT ?= baseline

CORE_DIR_baseline := cv32e40p_baseline
CORE_DIR_no-mul-forwarding := cv32e40p_no_mul_forwarding
CORE_DIR ?= $(CORE_DIR_$(EXPERIMENT))
BUILD_DIR ?= build/vivado-$(EXPERIMENT)
PROJECT_NAME ?= cv32e40p-zedboard-project

.PHONY: all baseline no-mul-forwarding reports utilization-reports utilization-plots timing-reports timing-plots clean

all:
	$(VIVADO) -mode batch -source cv32e40p-zedboard-project.tcl -tclargs --experiment $(EXPERIMENT) --core_dir $(CORE_DIR) --build_dir $(BUILD_DIR) --project_name $(PROJECT_NAME)

baseline:
	$(MAKE) EXPERIMENT=baseline all

no-mul-forwarding:
	$(MAKE) EXPERIMENT=no-mul-forwarding all

reports:
	./report.sh --comparison --report all --yes

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
