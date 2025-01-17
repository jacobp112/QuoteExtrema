`timescale 1ns/1ps
`default_nettype none

module uart_rx #(
    parameter integer CLKS_PER_BIT = 104
) (
    input  wire       clk,
    input  wire       rst,
    input  wire       pin_rx,
    output reg  [7:0] data,
    output reg        valid,
    output reg        error
);
    localparam integer WIDTH = $clog2(CLKS_PER_BIT + 1);
    localparam [2:0] IDLE = 0, START = 1, DATA = 2, STOP = 3, RECOVER = 4;
    (* async_reg = "true" *) reg rx_meta = 1;
    (* async_reg = "true" *) reg rx_sync = 1;
    reg [2:0] state;
    reg [WIDTH-1:0] timer;
    reg [2:0] bit_index;
    reg [7:0] shift;

    // Synchronizers keep sampling during reset, including a held break.
    always @(posedge clk) begin
        rx_meta <= pin_rx;
        rx_sync <= rx_meta;
    end
    always @(posedge clk) begin
        if (rst) begin
            state <= IDLE;
            timer <= 0;
            bit_index <= 0;
            shift <= 0;
            data <= 0;
            valid <= 0;
            error <= 0;
        end else begin
            valid <= 0;
            error <= 0;
            case (state)
                IDLE: if (!rx_sync) begin
                    timer <= CLKS_PER_BIT / 2 - 1;
                    state <= START;
                end
                START: if (timer != 0) timer <= timer - 1'b1;
                else if (rx_sync) state <= IDLE;
                else begin
                    timer <= CLKS_PER_BIT - 1;
                    bit_index <= 0;
                    state <= DATA;
                end
                DATA: if (timer != 0) timer <= timer - 1'b1;
                else begin
                    shift[bit_index] <= rx_sync;
                    timer <= CLKS_PER_BIT - 1;
                    if (bit_index == 7) state <= STOP;
                    else bit_index <= bit_index + 1'b1;
                end
                STOP: if (timer != 0) timer <= timer - 1'b1;
                else if (rx_sync) begin
                    data <= shift;
                    valid <= 1;
                    state <= IDLE;
                end else begin
                    error <= 1;
                    state <= RECOVER;
                end
                RECOVER: if (rx_sync) state <= IDLE;
                default: state <= IDLE;
            endcase
        end
    end
endmodule

`default_nettype wire
