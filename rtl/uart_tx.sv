`timescale 1ns/1ps
`default_nettype none

module uart_tx #(
    parameter integer CLKS_PER_BIT = 104
) (
    input  wire       clk,
    input  wire       rst,
    input  wire [7:0] data,
    input  wire       valid,
    output wire      ready,
    output wire      idle,
    output reg       pin_tx
);
    localparam integer WIDTH = $clog2(CLKS_PER_BIT + 1);
    reg active;
    reg [WIDTH-1:0] timer;
    reg [3:0] bit_index;
    reg [9:0] frame;
    assign ready = !rst && !active;
    assign idle = !active;

    always @(posedge clk) begin
        if (rst) begin
            active <= 0;
            timer <= 0;
            bit_index <= 0;
            frame <= 10'h3FF;
            pin_tx <= 1;
        end else if (!active) begin
            pin_tx <= 1;
            if (valid) begin
                frame <= {1'b1, data, 1'b0};
                pin_tx <= 0;
                active <= 1;
                timer <= CLKS_PER_BIT - 1;
                bit_index <= 0;
            end
        end else if (timer != 0) timer <= timer - 1'b1;
        else if (bit_index == 9) begin
            active <= 0;
            pin_tx <= 1;
        end else begin
            bit_index <= bit_index + 1'b1;
            pin_tx <= frame[bit_index + 1'b1];
            timer <= CLKS_PER_BIT - 1;
        end
    end
endmodule

`default_nettype wire
