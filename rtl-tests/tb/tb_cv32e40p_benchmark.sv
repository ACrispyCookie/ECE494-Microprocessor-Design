`timescale 1ns / 1ps

module tb_cv32e40p_benchmark;
    localparam int IMEM_DEPTH = 32768;
    localparam int DMEM_DEPTH = 32768;
    localparam int DEFAULT_TIMEOUT_CYCLES = 2000000;
    localparam logic [31:0] RESULT_ADDR = 32'h0001_0000;
    localparam logic [31:0] SIGNATURE_ADDR = 32'h0001_0004;
    localparam logic [31:0] BENCH_START_ADDR = 32'h0001_fff0;
    localparam logic [31:0] BENCH_STOP_ADDR = 32'h0001_fff4;
    localparam logic [31:0] DONE_ADDR = 32'h0001_fffc;
    localparam logic [31:0] DONE_MAGIC = 32'h5555_aaaa;

    logic clk_i;
    logic rst_btn_i;
    logic [7:0] led_o;

    integer timeout_cycles;
    integer cycles_left;
    integer cycle_count;
    integer roi_start_cycle;
    integer roi_stop_cycle;
    integer roi_cycles;
    integer return_code;
    integer errors;
    integer plusarg_dummy;
    logic saw_done;
    logic saw_roi_start;
    logic saw_roi_stop;
    logic [31:0] signature;

    initial clk_i = 1'b0;
    always #5 clk_i = ~clk_i;

    zedboard_cv32e40p_wrapper #(
        .IMEM_DEPTH     (IMEM_DEPTH),
        .DMEM_DEPTH     (DMEM_DEPTH),
        .IMEM_INIT_FILE ("program_imem.mem"),
        .DMEM_INIT_FILE ("program_dmem.mem")
    ) dut (
        .clk_i     (clk_i),
        .rst_btn_i (rst_btn_i),
        .led_o     (led_o)
    );

    initial begin
        timeout_cycles = DEFAULT_TIMEOUT_CYCLES;
        plusarg_dummy = $value$plusargs("timeout_cycles=%d", timeout_cycles);

        $display("[TB] CV32E40P benchmark testbench started");
        $display("[TB] IMEM_DEPTH=%0d DMEM_DEPTH=%0d timeout_cycles=%0d", IMEM_DEPTH, DMEM_DEPTH, timeout_cycles);

        saw_done = 1'b0;
        saw_roi_start = 1'b0;
        saw_roi_stop = 1'b0;
        cycle_count = 0;
        roi_start_cycle = -1;
        roi_stop_cycle = -1;
        roi_cycles = -1;
        return_code = -1;
        signature = 32'h0000_0000;
        errors = 0;

        rst_btn_i = 1'b1;
        repeat (10) @(posedge clk_i);
        rst_btn_i = 1'b0;
        $display("[TB] Reset released at time %0t", $time);

        cycles_left = timeout_cycles;
        while (!saw_done && cycles_left > 0) begin
            @(posedge clk_i);
            #1ps;
            cycle_count = cycle_count + 1;

            if (dut.data_req && dut.data_gnt && dut.data_we && dut.data_be == 4'hf) begin
                if (dut.data_addr == BENCH_START_ADDR) begin
                    saw_roi_start = 1'b1;
                    roi_start_cycle = cycle_count;
                    $display("[TB] Benchmark ROI started at cycle %0d", roi_start_cycle);
                end else if (dut.data_addr == BENCH_STOP_ADDR) begin
                    saw_roi_stop = 1'b1;
                    roi_stop_cycle = cycle_count;
                    $display("[TB] Benchmark ROI stopped at cycle %0d", roi_stop_cycle);
                end else if (dut.data_addr == RESULT_ADDR) begin
                    return_code = dut.data_wdata;
                    $display("[TB] Return code store: %0d", return_code);
                end else if (dut.data_addr == SIGNATURE_ADDR) begin
                    signature = dut.data_wdata;
                    $display("[TB] Signature store: 0x%08x", signature);
                end else if (dut.data_addr == DONE_ADDR && dut.data_wdata == DONE_MAGIC) begin
                    saw_done = 1'b1;
                    $display("[TB] Saw DONE store at cycle %0d time %0t", cycle_count, $time);
                end
            end

            cycles_left = cycles_left - 1;
        end

        if (!saw_done) begin
            $display("[FAIL] Timeout waiting for DONE store to 0x%08h = 0x%08h", DONE_ADDR, DONE_MAGIC);
            $fatal(1);
        end

        if (!saw_roi_start) begin
            $display("[FAIL] Benchmark did not write BENCH_START_ADDR");
            errors = errors + 1;
        end
        if (!saw_roi_stop) begin
            $display("[FAIL] Benchmark did not write BENCH_STOP_ADDR");
            errors = errors + 1;
        end
        if (return_code != 0) begin
            $display("[FAIL] Benchmark returned nonzero code: %0d", return_code);
            errors = errors + 1;
        end

        if (saw_roi_start && saw_roi_stop) begin
            roi_cycles = roi_stop_cycle - roi_start_cycle;
        end

        $display("[METRIC] total_cycles=%0d roi_cycles=%0d return_code=%0d signature=0x%08x", cycle_count, roi_cycles, return_code, signature);

        if (errors != 0) begin
            $display("[FAIL] RTL benchmark failed with %0d errors", errors);
            $fatal(1);
        end

        $display("[PASS] RTL benchmark completed successfully");
        $finish;
    end
endmodule
