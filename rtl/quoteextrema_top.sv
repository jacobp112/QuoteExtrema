`timescale 1ns/1ps
`default_nettype none

module quoteextrema_top #(
    parameter integer CLKS_PER_BIT = 104,
    parameter integer TIMEOUT_CYCLES = 24000
) (
    input  wire clk_12m,
    input  wire uart_rx,
    output wire uart_tx,
    input  wire button_n,
    output wire bid_led_n,
    output wire ask_led_n
);
    (* async_reg = "true" *) reg button_meta = 1;
    (* async_reg = "true" *) reg button_sync = 1;
    reg [4:0] startup = 0;
    wire rst = !startup[4] || !button_sync;
    wire [7:0] rx_data, tx_data;
    wire rx_valid, rx_error, tx_valid, tx_ready, tx_idle;
    wire bid_valid, ask_valid;
    localparam integer TIMER_WIDTH = $clog2(TIMEOUT_CYCLES + 1);
    reg [TIMER_WIDTH-1:0] silence;
    wire timeout = !rx_valid && silence == TIMEOUT_CYCLES - 1;

    always @(posedge clk_12m) begin
        button_meta <= button_n;
        button_sync <= button_meta;
        if (!startup[4]) startup <= startup + 1'b1;
        if (rst || rx_valid || rx_error || timeout) silence <= 0;
        else silence <= silence + 1'b1;
    end
    uart_rx #(.CLKS_PER_BIT(CLKS_PER_BIT)) input_uart (
        .clk(clk_12m), .rst(rst), .pin_rx(uart_rx),
        .data(rx_data), .valid(rx_valid), .error(rx_error)
    );
    uart_tx #(.CLKS_PER_BIT(CLKS_PER_BIT)) output_uart (
        .clk(clk_12m), .rst(rst), .data(tx_data), .valid(tx_valid),
        .ready(tx_ready), .idle(tx_idle), .pin_tx(uart_tx)
    );
    quote_interface link (
        .clk(clk_12m), .rst(rst), .rx_data(rx_data), .rx_valid(rx_valid),
        .rx_abort(timeout), .rx_error(rx_error), .rx_ready(),
        .tx_data(tx_data), .tx_valid(tx_valid), .tx_ready(tx_ready), .tx_idle(tx_idle),
        .response_busy(), .bid_valid(bid_valid), .bid(),
        .ask_valid(ask_valid), .ask(), .valid_frames(), .crc_errors(),
        .invalid_lengths(), .incomplete_frames(), .discarded_bytes(),
        .semantic_errors(), .busy_reads(), .uart_errors()
    );
    assign bid_led_n = !bid_valid;
    assign ask_led_n = !ask_valid;
endmodule

`default_nettype wire
