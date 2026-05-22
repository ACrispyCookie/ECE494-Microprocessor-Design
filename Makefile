all:
	vivado -source cv32e40p-zedboard-project.tcl

clean:
	rm -rf build/ .Xil *.log *.jou *.str
