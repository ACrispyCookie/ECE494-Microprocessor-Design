`timescale 1ns / 1ps

module tb_cv32e40p_rtl;
    localparam int IMEM_DEPTH = 4096;
    localparam int DMEM_DEPTH = 4096;
    localparam int DEFAULT_DUMP_WORDS = 64;
    localparam int DEFAULT_TIMEOUT_CYCLES = 2000;
    localparam logic [31:0] DONE_ADDR = 32'h0001_fffc;
    localparam logic [31:0] DONE_MAGIC = 32'h5555_aaaa;

    logic clk_i;
    logic rst_btn_i;
    logic [7:0] led_o;

    integer dump_fd;
    integer dump_words;
    integer timeout_cycles;
    integer cycles_left;
    integer i;
    integer plusarg_dummy;
    string dump_file;
    logic saw_done;

    initial clk_i = 1'b0;
    always #5 clk_i = ~clk_i;

    zedboard_cv32e40p_wrapper #(
        .IMEM_DEPTH     (IMEM_DEPTH),
        .DMEM_DEPTH     (DMEM_DEPTH),
        .IMEM_INIT_FILE ("program_imem.mem"),
        .DMEM_INIT_FILE ("")
    ) dut (
        .clk_i     (clk_i),
        .rst_btn_i (rst_btn_i),
        .led_o     (led_o)
    );

    initial begin
        dump_file = "dmem_dump.mem";
        dump_words = DEFAULT_DUMP_WORDS;
        timeout_cycles = DEFAULT_TIMEOUT_CYCLES;

        plusarg_dummy = $value$plusargs("dump_file=%s", dump_file);
        plusarg_dummy = $value$plusargs("dump_words=%d", dump_words);
        plusarg_dummy = $value$plusargs("timeout_cycles=%d", timeout_cycles);

        $display("[TB] CV32E40P RTL testbench started");
        $display("[TB] dump_file=%s dump_words=%0d timeout_cycles=%0d", dump_file, dump_words, timeout_cycles);

        saw_done = 1'b0;
        rst_btn_i = 1'b1;
        repeat (10) @(posedge clk_i);
        rst_btn_i = 1'b0;
        $display("[TB] Reset released at time %0t", $time);

        cycles_left = timeout_cycles;
        while (!saw_done && cycles_left > 0) begin
            @(posedge clk_i);
            #1ps;

            if (dut.data_req && dut.data_gnt && dut.data_we &&
                dut.data_be == 4'hf && dut.data_addr == DONE_ADDR &&
                dut.data_wdata == DONE_MAGIC) begin
                saw_done = 1'b1;
                $display("[TB] Saw DONE store at time %0t", $time);
            end

            cycles_left = cycles_left - 1;
        end

        if (!saw_done) begin
            $display("[FAIL] Timeout waiting for DONE store to 0x%08h = 0x%08h", DONE_ADDR, DONE_MAGIC);
            dump_dmem();
            $fatal(1);
        end

        repeat (5) @(posedge clk_i);
        #1ps;
        dump_dmem();
        $display("[PASS] RTL simulation completed");
        $finish;
    end

    task automatic dump_dmem;
        logic [31:0] dmem_word;
        begin
            dump_fd = $fopen(dump_file, "w");
            if (dump_fd == 0) begin
                $display("[FAIL] Could not open DMEM dump file: %s", dump_file);
                $fatal(1);
            end

            for (i = 0; i < dump_words; i = i + 1) begin
                dmem_word = {
                    dut.dmem_i.mem3[i],
                    dut.dmem_i.mem2[i],
                    dut.dmem_i.mem1[i],
                    dut.dmem_i.mem0[i]
                };
                $fwrite(dump_fd, "%08x\n", dmem_word);
            end

            $fclose(dump_fd);
            $display("[TB] Wrote %0d DMEM words to %s", dump_words, dump_file);
        end
    endtask
endmodule
