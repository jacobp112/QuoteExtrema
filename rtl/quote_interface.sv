`timescale 1ns/1ps
`default_nettype none

module quote_interface (
    input  wire        clk,
    input  wire        rst,
    input  wire [7:0]  rx_data,
    input  wire        rx_valid,
    input  wire        rx_abort,
    input  wire        rx_error,
    output wire        rx_ready,
    output wire [7:0]  tx_data,
    output wire        tx_valid,
    input  wire        tx_ready,
    input  wire        tx_idle,
    output wire        response_busy,
    output wire        bid_valid,
    output wire [31:0] bid,
    output wire        ask_valid,
    output wire [31:0] ask,
    output wire [31:0] valid_frames,
    output wire [31:0] crc_errors,
    output wire [31:0] invalid_lengths,
    output wire [31:0] incomplete_frames,
    output wire [31:0] discarded_bytes,
    output reg  [31:0] semantic_errors,
    output reg  [31:0] busy_reads,
    output reg  [31:0] uart_errors
);
    wire [127:0] payload;
    wire [4:0] length;
    wire message_valid;
    wire [7:0] kind = payload[7:0];
    wire quote = message_valid && length == 5 && (kind == 1 || kind == 2);
    wire clear = message_valid && length == 1 && kind == 4;
    wire read_request = message_valid && length == 3 && kind == 3;
    wire read_accept = read_request && !response_busy;
    wire [7:0] flags = {6'd0, ask_valid, bid_valid};
    wire [95:0] response = {ask, bid, flags, payload[23:8], 8'h83};

    function automatic [31:0] saturate(input [31:0] value);
        saturate = (&value) ? value : value + 32'd1;
    endfunction

    framelatch receiver (
        .clk(clk), .rst(rst), .in_data(rx_data), .in_valid(rx_valid),
        .in_ready(rx_ready), .in_abort(rx_abort || rx_error),
        .out_payload(payload), .out_length(length), .out_valid(message_valid),
        .out_ready(!rst), .valid_frames(valid_frames), .crc_errors(crc_errors),
        .invalid_lengths(invalid_lengths), .incomplete_frames(incomplete_frames),
        .discarded_bytes(discarded_bytes)
    );
    quote_core core (
        .clk(clk), .rst(rst), .clear(clear), .quote_valid(quote),
        .quote_ask(kind == 2), .quote_price(payload[39:8]),
        .bid_valid(bid_valid), .bid(bid), .ask_valid(ask_valid), .ask(ask)
    );
    frame_tx serializer (
        .clk(clk), .rst(rst), .start(read_accept), .payload(response),
        .busy(response_busy), .byte_valid(tx_valid), .byte_data(tx_data),
        .byte_ready(tx_ready), .uart_idle(tx_idle)
    );
    always @(posedge clk) begin
        if (rst) begin
            semantic_errors <= 0;
            busy_reads <= 0;
            uart_errors <= 0;
        end else begin
            if (message_valid && !(quote || clear || read_request))
                semantic_errors <= saturate(semantic_errors);
            if (read_request && response_busy)
                busy_reads <= saturate(busy_reads);
            if (rx_error) uart_errors <= saturate(uart_errors);
        end
    end
endmodule

`default_nettype wire
