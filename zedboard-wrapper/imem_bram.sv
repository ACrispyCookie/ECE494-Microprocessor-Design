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


module imem_bram #(
    parameter int DEPTH = 4096,
    parameter string INIT_FILE = ""
)(
    input  logic clk,

    input  logic [$clog2(DEPTH)-1:0] addr_i,
    input  logic                     req_i,
    output logic [31:0]              rdata_o
);

    (* ram_style = "block" *) logic [31:0] mem [0:DEPTH-1];

    initial begin
        if (INIT_FILE != "") begin
            $readmemh(INIT_FILE, mem);
        end
    end

    always_ff @(posedge clk) begin
        if (req_i) begin
            rdata_o <= mem[addr_i];
        end
    end

endmodule

