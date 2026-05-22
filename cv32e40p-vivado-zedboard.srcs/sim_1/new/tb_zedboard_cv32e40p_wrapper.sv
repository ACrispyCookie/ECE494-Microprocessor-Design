`timescale 1ns / 1ps
//////////////////////////////////////////////////////////////////////////////////
// Company: 
// Engineer: 
// 
// Create Date: 05/20/2026 05:07:49 PM
// Design Name: 
// Module Name: tb_zedboard_cv32e40p_wrapper
// Project Name: 
// Target Devices: 
// Tool Versions: 
// Description: 
// 
// Dependencies: 
// 
// Revision:
// Revision 0.01 - File Created
// Additional Comments:
// 
//////////////////////////////////////////////////////////////////////////////////


`timescale 1ns / 1ps

module tb_zedboard_cv32e40p_wrapper;

    logic clk_i;
    logic rst_btn_i;
    logic [7:0] led_o;

    // 100 MHz clock: 10 ns period
    initial clk_i = 1'b0;
    always #5 clk_i = ~clk_i;

    zedboard_cv32e40p_wrapper #(
        .IMEM_DEPTH      (4096),
        .DMEM_DEPTH      (4096),
        .IMEM_INIT_FILE  ("program_imem.mem"),
        .DMEM_INIT_FILE  ("")
    ) dut (
        .clk_i     (clk_i),
        .rst_btn_i (rst_btn_i),
        .led_o     (led_o)
    );

    initial begin
        // rst_btn_i is active-high button input.
        // In wrapper: rst_ni = ~rst_btn_i.
        rst_btn_i = 1'b1;   // reset asserted

        repeat (10) @(posedge clk_i);

        rst_btn_i = 1'b0;   // release reset

        // Let the core run.
        repeat (200) @(posedge clk_i);

        // Check DMEM word 0.
        // This assumes dmem_bram_be has byte arrays named mem0..mem3.
        if ({
            dut.dmem_i.mem3[0],
            dut.dmem_i.mem2[0],
            dut.dmem_i.mem1[0],
            dut.dmem_i.mem0[0]
        } === 32'h1234_5678) begin
            $display("[PASS] DMEM[0] = 0x%08h", {
                dut.dmem_i.mem3[0],
                dut.dmem_i.mem2[0],
                dut.dmem_i.mem1[0],
                dut.dmem_i.mem0[0]
            });
        end else begin
            $display("[FAIL] DMEM[0] = 0x%08h, expected 0x12345678", {
                dut.dmem_i.mem3[0],
                dut.dmem_i.mem2[0],
                dut.dmem_i.mem1[0],
                dut.dmem_i.mem0[0]
            });
            $fatal;
        end

        $finish;
    end

endmodule
