`timescale 1ns / 1ps

module tb_zedboard_cv32e40p_wrapper;

    logic clk_i;
    logic rst_btn_i;
    logic [7:0] led_o;

    logic saw_expected_store;

    integer fd;
    integer i;
    int timeout;

    // ------------------------------------------------------------
    // Clock generation
    // ------------------------------------------------------------
    // 100 MHz clock: 10 ns period

    initial clk_i = 1'b0;
    always #5 clk_i = ~clk_i;

    // ------------------------------------------------------------
    // DUT
    // ------------------------------------------------------------

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

    // ------------------------------------------------------------
    // Global watchdog
    // ------------------------------------------------------------
    // Prevents the simulation from running forever if the main test
    // sequence gets stuck.

    initial begin
        #20us;
        $display("[FAIL] Global simulation timeout at time %0t", $time);
        $fatal(1);
    end

    // ------------------------------------------------------------
    // Main test sequence
    // ------------------------------------------------------------

    initial begin
        $display("[TB] Testbench started at time %0t", $time);

        saw_expected_store = 1'b0;
        rst_btn_i = 1'b1;   // reset asserted, wrapper converts to rst_ni = 0

        repeat (10) @(posedge clk_i);

        rst_btn_i = 1'b0;   // reset released, wrapper converts to rst_ni = 1
        $display("[TB] Reset released at time %0t", $time);

        // Wait until the CPU performs the expected store.
        //
        // The #1ps after the clock edge is important. Without it, the
        // testbench may sample old values before the DUT's nonblocking
        // assignments have updated signals for this cycle.

        timeout = 500;

        while (!saw_expected_store && timeout > 0) begin
            @(posedge clk_i);
            #1ps;

            if (dut.data_req &&
                dut.data_gnt &&
                dut.data_we &&
                dut.data_be    == 4'hf &&
                dut.data_addr  == 32'h0000_0000 &&
                dut.data_wdata == 32'h0000_0083) begin

                saw_expected_store = 1'b1;

                $display("[INFO] Saw expected store at time %0t", $time);
                $display("[INFO] data_addr  = 0x%08h", dut.data_addr);
                $display("[INFO] data_wdata = 0x%08h", dut.data_wdata);
                $display("[INFO] data_be    = 0x%01h", dut.data_be);
            end

            timeout--;
        end

        if (!saw_expected_store) begin
            $display("[WARN] Did not observe expected store transaction on data bus");
            $display("[WARN] Continuing with direct DMEM content check");
        end

        // Give the DMEM a couple of extra cycles after the store.
        repeat (2) @(posedge clk_i);
        #1ps;

        check_dmem_word0();
        dump_dmem();

        $display("[PASS] Smoke test completed successfully at time %0t", $time);
        $finish;
    end

    // ------------------------------------------------------------
    // Check DMEM[0]
    // ------------------------------------------------------------

    task automatic check_dmem_word0;
        logic [31:0] dmem_word0;
        begin
            dmem_word0 = {
                dut.dmem_i.mem3[0],
                dut.dmem_i.mem2[0],
                dut.dmem_i.mem1[0],
                dut.dmem_i.mem0[0]
            };

            if (dmem_word0 !== 32'h0000_0083) begin
                $display("[FAIL] DMEM[0] = 0x%08h, expected 0x00000083", dmem_word0);
                $fatal(1);
            end else begin
                $display("[PASS] DMEM[0] = 0x%08h", dmem_word0);
            end
        end
    endtask

    // ------------------------------------------------------------
    // Dump first DMEM words to file
    // ------------------------------------------------------------
    //
    // With a relative filename, XSim usually writes this file under:
    //
    // build/vivado/cv32e40p-zedboard-project.sim/sim_1/behav/xsim/
    //
    // You can find it with:
    //   find build -name "dmem_dump.txt"

    task automatic dump_dmem;
        logic [31:0] dmem_word;
        begin
            fd = $fopen("dmem_dump.txt", "w");

            if (fd == 0) begin
                $display("[FAIL] Could not open dmem_dump.txt");
                $fatal(1);
            end

            for (i = 0; i < 16; i = i + 1) begin
                dmem_word = {
                    dut.dmem_i.mem3[i],
                    dut.dmem_i.mem2[i],
                    dut.dmem_i.mem1[i],
                    dut.dmem_i.mem0[i]
                };

                $fwrite(fd, "%04x: %08x\n", i, dmem_word);
            end

            $fclose(fd);

            $display("[INFO] Wrote DMEM dump to dmem_dump.txt");
        end
    endtask

endmodule