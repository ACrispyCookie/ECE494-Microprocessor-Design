`timescale 1ns / 1ps

module tb_cv32e40p_rtl;
    localparam int IMEM_DEPTH = 4096;
    localparam int DMEM_DEPTH = 4096;
    localparam int REG_COUNT = 32;
    localparam int DEFAULT_DUMP_WORDS = 4096;
    localparam int DEFAULT_DMEM_CHECK_WORDS = 4096;
    localparam int DEFAULT_TIMEOUT_CYCLES = 2000;
    localparam logic [31:0] DONE_ADDR = 32'h0001_fffc;
    localparam logic [31:0] DONE_MAGIC = 32'h5555_aaaa;

    logic clk_i;
    logic rst_btn_i;
    logic [7:0] led_o;

    integer dump_fd;
    integer reg_dump_fd;
    integer dump_words;
    integer dmem_check_words;
    integer timeout_cycles;
    integer cycles_left;
    integer i;
    integer errors;
    integer plusarg_dummy;
    string dump_file;
    string regfile_dump_file;
    string expected_dmem_file;
    string expected_regfile_file;
    logic saw_done;
    logic [31:0] expected_dmem [0:DMEM_DEPTH-1];
    logic [31:0] expected_regfile [0:REG_COUNT-1];

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
        regfile_dump_file = "regfile_dump.mem";
        expected_dmem_file = "expected_dmem.mem";
        expected_regfile_file = "expected_regfile.mem";
        dump_words = DEFAULT_DUMP_WORDS;
        dmem_check_words = DEFAULT_DMEM_CHECK_WORDS;
        timeout_cycles = DEFAULT_TIMEOUT_CYCLES;

        plusarg_dummy = $value$plusargs("dump_file=%s", dump_file);
        plusarg_dummy = $value$plusargs("regfile_dump_file=%s", regfile_dump_file);
        plusarg_dummy = $value$plusargs("expected_dmem_file=%s", expected_dmem_file);
        plusarg_dummy = $value$plusargs("expected_regfile_file=%s", expected_regfile_file);
        plusarg_dummy = $value$plusargs("dump_words=%d", dump_words);
        plusarg_dummy = $value$plusargs("dmem_check_words=%d", dmem_check_words);
        plusarg_dummy = $value$plusargs("timeout_cycles=%d", timeout_cycles);

        if (dump_words > DMEM_DEPTH) dump_words = DMEM_DEPTH;
        if (dmem_check_words > DMEM_DEPTH) dmem_check_words = DMEM_DEPTH;

        $readmemh(expected_dmem_file, expected_dmem);
        $readmemh(expected_regfile_file, expected_regfile);

        $display("[TB] CV32E40P RTL testbench started");
        $display("[TB] dump_file=%s regfile_dump_file=%s", dump_file, regfile_dump_file);
        $display("[TB] expected_dmem_file=%s expected_regfile_file=%s", expected_dmem_file, expected_regfile_file);
        $display("[TB] dump_words=%0d dmem_check_words=%0d timeout_cycles=%0d", dump_words, dmem_check_words, timeout_cycles);

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
            dump_regfile();
            $fatal(1);
        end

        repeat (5) @(posedge clk_i);
        #1ps;
        dump_dmem();
        dump_regfile();
        errors = 0;
        compare_dmem();
        compare_regfile();

        if (errors != 0) begin
            $display("[FAIL] RTL final-state comparison failed with %0d mismatches", errors);
            $fatal(1);
        end

        $display("[PASS] RTL simulation completed and matched expected DMEM/regfile dumps");
        $finish;
    end

    function automatic logic [31:0] dmem_word(input integer idx);
        begin
            dmem_word = {
                dut.dmem_i.mem3[idx],
                dut.dmem_i.mem2[idx],
                dut.dmem_i.mem1[idx],
                dut.dmem_i.mem0[idx]
            };
        end
    endfunction

    function automatic logic [31:0] regfile_word(input integer idx);
        begin
            // sv2v flattens the original unpacked regfile array into a packed
            // vector: mem[reg_index * 32 +: 32].
            regfile_word = dut.core_i.core_i.id_stage_i.register_file_i.mem[idx * 32 +: 32];
        end
    endfunction

    task automatic dump_dmem;
        begin
            dump_fd = $fopen(dump_file, "w");
            if (dump_fd == 0) begin
                $display("[FAIL] Could not open DMEM dump file: %s", dump_file);
                $fatal(1);
            end

            for (i = 0; i < dump_words; i = i + 1) begin
                $fwrite(dump_fd, "%08x\n", dmem_word(i));
            end

            $fclose(dump_fd);
            $display("[TB] Wrote %0d DMEM words to %s", dump_words, dump_file);
        end
    endtask

    task automatic dump_regfile;
        begin
            reg_dump_fd = $fopen(regfile_dump_file, "w");
            if (reg_dump_fd == 0) begin
                $display("[FAIL] Could not open regfile dump file: %s", regfile_dump_file);
                $fatal(1);
            end

            for (i = 0; i < REG_COUNT; i = i + 1) begin
                $fwrite(reg_dump_fd, "%08x\n", regfile_word(i));
            end

            $fclose(reg_dump_fd);
            $display("[TB] Wrote %0d regfile words to %s", REG_COUNT, regfile_dump_file);
        end
    endtask

    task automatic compare_dmem;
        logic [31:0] actual;
        begin
            for (i = 0; i < dmem_check_words; i = i + 1) begin
                actual = dmem_word(i);
                if (actual !== expected_dmem[i]) begin
                    $display("[FAIL] DMEM[%0d] actual=0x%08x expected=0x%08x", i, actual, expected_dmem[i]);
                    errors = errors + 1;
                end
            end
        end
    endtask

    task automatic compare_regfile;
        logic [31:0] actual;
        begin
            for (i = 0; i < REG_COUNT; i = i + 1) begin
                actual = regfile_word(i);
                if (actual !== expected_regfile[i]) begin
                    $display("[FAIL] REG x%0d actual=0x%08x expected=0x%08x", i, actual, expected_regfile[i]);
                    errors = errors + 1;
                end
            end
        end
    endtask
endmodule
