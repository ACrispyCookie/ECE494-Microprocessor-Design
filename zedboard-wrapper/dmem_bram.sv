`timescale 1ns / 1ps
//////////////////////////////////////////////////////////////////////////////////
// Company: 
// Engineer: 
// 
// Create Date: 05/20/2026 04:31:59 PM
// Design Name: 
// Module Name: imem_bram
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

module dmem_bram_be #(
    parameter int DEPTH = 4096,
    parameter string INIT_FILE = ""
)(
    input  logic clk,

    input  logic [$clog2(DEPTH)-1:0] addr_i,
    input  logic                     req_i,
    input  logic                     we_i,
    input  logic [3:0]               be_i,
    input  logic [31:0]              wdata_i,
    output logic [31:0]              rdata_o
);

    (* ram_style = "block" *) logic [7:0] mem0 [0:DEPTH-1];
    (* ram_style = "block" *) logic [7:0] mem1 [0:DEPTH-1];
    (* ram_style = "block" *) logic [7:0] mem2 [0:DEPTH-1];
    (* ram_style = "block" *) logic [7:0] mem3 [0:DEPTH-1];

    // Optional initialization.
    // For DMEM you can leave INIT_FILE empty at first.
    initial begin : init_mem
        integer i;
        logic [31:0] tmp [0:DEPTH-1];

        for (i = 0; i < DEPTH; i = i + 1) begin
            mem0[i] = 8'h00;
            mem1[i] = 8'h00;
            mem2[i] = 8'h00;
            mem3[i] = 8'h00;
            tmp[i]  = 32'h0000_0000;
        end

        if (INIT_FILE != "") begin
            $readmemh(INIT_FILE, tmp);

            for (i = 0; i < DEPTH; i = i + 1) begin
                mem0[i] = tmp[i][7:0];
                mem1[i] = tmp[i][15:8];
                mem2[i] = tmp[i][23:16];
                mem3[i] = tmp[i][31:24];
            end
        end
    end

    always_ff @(posedge clk) begin
        if (req_i) begin
            // Read-first behavior.
            // On stores, CV32E40P does not need meaningful rdata.
            rdata_o <= {
                mem3[addr_i],
                mem2[addr_i],
                mem1[addr_i],
                mem0[addr_i]
            };

            if (we_i) begin
                if (be_i[0]) mem0[addr_i] <= wdata_i[7:0];
                if (be_i[1]) mem1[addr_i] <= wdata_i[15:8];
                if (be_i[2]) mem2[addr_i] <= wdata_i[23:16];
                if (be_i[3]) mem3[addr_i] <= wdata_i[31:24];
            end
        end
    end

endmodule