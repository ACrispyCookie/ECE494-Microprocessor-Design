## Clock
set_property PACKAGE_PIN Y9 [get_ports clk_i]
set_property IOSTANDARD LVCMOS33 [get_ports clk_i]
create_clock -period 10.000 -name clk_i [get_ports clk_i]

## Reset using SW0
## rst_ni is active-low:
##   SW0 = 0 -> reset
##   SW0 = 1 -> run
set_property PACKAGE_PIN F22 [get_ports rst_ni]
set_property IOSTANDARD LVCMOS33 [get_ports rst_ni]

## User LEDs LD0-LD7
set_property PACKAGE_PIN T22 [get_ports {led_o[0]}]
set_property PACKAGE_PIN T21 [get_ports {led_o[1]}]
set_property PACKAGE_PIN U22 [get_ports {led_o[2]}]
set_property PACKAGE_PIN U21 [get_ports {led_o[3]}]
set_property PACKAGE_PIN V22 [get_ports {led_o[4]}]
set_property PACKAGE_PIN W22 [get_ports {led_o[5]}]
set_property PACKAGE_PIN U19 [get_ports {led_o[6]}]
set_property PACKAGE_PIN U14 [get_ports {led_o[7]}]

set_property IOSTANDARD LVCMOS33 [get_ports {led_o[*]}]
