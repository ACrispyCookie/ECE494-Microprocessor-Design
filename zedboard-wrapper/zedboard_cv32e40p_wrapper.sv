`timescale 1ns / 1ps
//////////////////////////////////////////////////////////////////////////////////
// Company: 
// Engineer: 
// 
// Create Date: 05/20/2026 01:06:25 PM
// Design Name: 
// Module Name: zedboard_cv32e40p_wrapper
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


// Minimal FPGA wrapper for CV32E40P on Zedboard.
// Purpose: implementation / timing / utilization experiments.
// This is NOT a complete runnable SoC.

module zedboard_cv32e40p_wrapper #(
    parameter int IMEM_DEPTH = 4096,  // 4096 words = 16 KiB
    parameter int DMEM_DEPTH = 4096,

    parameter string IMEM_INIT_FILE = "program_imem.mem",
    parameter string DMEM_INIT_FILE = ""
)(
    input  logic        clk_i,
    input  logic        rst_btn_i,
    output logic [7:0]  led_o
);

    localparam int IMEM_AW = $clog2(IMEM_DEPTH);
    localparam int DMEM_AW = $clog2(DMEM_DEPTH);

    logic rst_ni;

    // Button not pressed = 0 -> run
    // Button pressed     = 1 -> reset
    assign rst_ni = ~rst_btn_i;

    // ------------------------------------------------------------
    // CV32E40P instruction interface
    // ------------------------------------------------------------

    logic        instr_req;
    logic        instr_gnt;
    logic        instr_rvalid;
    logic [31:0] instr_addr;
    logic [31:0] instr_rdata;

    // ------------------------------------------------------------
    // CV32E40P data interface
    // ------------------------------------------------------------

    logic        data_req;
    logic        data_gnt;
    logic        data_rvalid;
    logic        data_we;
    logic [3:0]  data_be;
    logic [31:0] data_addr;
    logic [31:0] data_wdata;
    logic [31:0] data_rdata;

    // ------------------------------------------------------------
    // Interrupt/debug/status signals
    // ------------------------------------------------------------

    logic        irq_ack;
    logic [4:0]  irq_id;

    logic        debug_havereset;
    logic        debug_running;
    logic        debug_halted;

    logic        core_sleep;

    // ------------------------------------------------------------
    // Memory handshake
    // ------------------------------------------------------------
    // The BRAM is synchronous, so read data is available one cycle
    // after the request. Therefore rvalid is a delayed version of req.

    assign instr_gnt = instr_req;
    assign data_gnt  = data_req;

    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) begin
            instr_rvalid <= 1'b0;
            data_rvalid  <= 1'b0;
        end else begin
            instr_rvalid <= instr_req;
            data_rvalid  <= data_req;
        end
    end

    // ------------------------------------------------------------
    // Address mapping
    // ------------------------------------------------------------
    // CV32E40P addresses are byte addresses.
    // BRAM memories are word-addressed.
    //
    // IMEM:
    //   0x0000_0000 -> word 0
    //
    // DMEM:
    //   We also use low address bits here.
    //   In the linker script, place data/stack in a region such as
    //   0x0001_0000. Because the memory depth is power-of-two, the
    //   lower address bits index the BRAM.
    //
    // For example:
    //   0x0001_0000 -> word 0
    //   0x0001_0004 -> word 1

    logic [IMEM_AW-1:0] imem_word_addr;
    logic [DMEM_AW-1:0] dmem_word_addr;

    assign imem_word_addr = instr_addr[IMEM_AW+1:2];
    assign dmem_word_addr = data_addr [DMEM_AW+1:2];

    // ------------------------------------------------------------
    // Instruction memory
    // ------------------------------------------------------------
    
    imem_bram #(
        .DEPTH     (IMEM_DEPTH),
        .INIT_FILE (IMEM_INIT_FILE)
    ) imem_i (
        .clk     (clk_i),
        .addr_i  (imem_word_addr),
        .req_i   (instr_req),
        .rdata_o (instr_rdata)
    );
    
    // ------------------------------------------------------------
    // Data memory
    // ------------------------------------------------------------
    
    dmem_bram_be #(
        .DEPTH     (DMEM_DEPTH),
        .INIT_FILE (DMEM_INIT_FILE)
    ) dmem_i (
        .clk     (clk_i),
        .addr_i  (dmem_word_addr),
        .req_i   (data_req),
        .we_i    (data_we),
        .be_i    (data_be),
        .wdata_i (data_wdata),
        .rdata_o (data_rdata)
    );

    // ------------------------------------------------------------
    // CV32E40P instance
    // ------------------------------------------------------------

    cv32e40p_top #(
        .COREV_PULP       (0),
        .COREV_CLUSTER    (0),
        .FPU              (0),
        .FPU_ADDMUL_LAT   (0),
        .FPU_OTHERS_LAT   (0),
        .ZFINX            (0),
        .NUM_MHPMCOUNTERS (1)
    ) core_i (
        // Clock and reset
        .clk_i               (clk_i),
        .rst_ni              (rst_ni),

        .pulp_clock_en_i     (1'b1),
        .scan_cg_en_i        (1'b0),

        // Static configuration
        .boot_addr_i         (32'h0000_0000),
        .mtvec_addr_i        (32'h0000_0100),
        .dm_halt_addr_i      (32'h0000_0000),
        .hart_id_i           (32'h0000_0000),
        .dm_exception_addr_i (32'h0000_0000),

        // Instruction memory interface
        .instr_req_o         (instr_req),
        .instr_gnt_i         (instr_gnt),
        .instr_rvalid_i      (instr_rvalid),
        .instr_addr_o        (instr_addr),
        .instr_rdata_i       (instr_rdata),

        // Data memory interface
        .data_req_o          (data_req),
        .data_gnt_i          (data_gnt),
        .data_rvalid_i       (data_rvalid),
        .data_we_o           (data_we),
        .data_be_o           (data_be),
        .data_addr_o         (data_addr),
        .data_wdata_o        (data_wdata),
        .data_rdata_i        (data_rdata),

        // Interrupts disabled
        .irq_i               (32'h0000_0000),
        .irq_ack_o           (irq_ack),
        .irq_id_o            (irq_id),

        // Debug disabled
        .debug_req_i         (1'b0),
        .debug_havereset_o   (debug_havereset),
        .debug_running_o     (debug_running),
        .debug_halted_o      (debug_halted),

        // CPU control
        .fetch_enable_i      (1'b1),
        .core_sleep_o        (core_sleep)
    );

    // ------------------------------------------------------------
    // Observable outputs
    // ------------------------------------------------------------

    assign led_o[0] = core_sleep;
    assign led_o[1] = debug_havereset;
    assign led_o[2] = debug_running;
    assign led_o[3] = debug_halted;
    assign led_o[4] = instr_req;
    assign led_o[5] = data_req;
    assign led_o[6] = irq_ack;
    assign led_o[7] = rst_ni;

endmodule