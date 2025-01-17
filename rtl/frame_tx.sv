`timescale 1ns/1ps
`default_nettype none

module frame_tx (
    input  wire         clk,
    input  wire         rst,
    input  wire         start,
    input  wire [95:0]  payload,
    output wire         busy,
    output wire         byte_valid,
    output reg  [7:0]   byte_data,
    input  wire         byte_ready,
    input  wire         uart_idle
);
    localparam [1:0] IDLE = 0, SEND = 1, DRAIN = 2;
    reg [1:0] state;
    reg [95:0] snapshot;
    reg [3:0] index;
    reg [7:0] crc;

    function automatic [7:0] crc_byte(input [7:0] value, input [7:0] data);
        reg [7:0] c;
        integer i;
        begin
            c = value ^ data;
            for (i = 0; i < 8; i = i + 1)
                c = c[7] ? (c << 1) ^ 8'h07 : c << 1;
            crc_byte = c;
        end
    endfunction

    assign busy = state != IDLE;
    assign byte_valid = !rst && state == SEND;
    always @* begin
        if (index == 0) byte_data = 8'hA5;
        else if (index == 1) byte_data = 8'd12;
        else if (index == 14) byte_data = crc;
        else byte_data = snapshot[(index - 2) * 8 +: 8];
    end

    always @(posedge clk) begin
        if (rst) begin
            state <= IDLE;
            snapshot <= 0;
            index <= 0;
            crc <= 0;
        end else begin
            case (state)
                IDLE: if (start) begin
                    snapshot <= payload;
                    index <= 0;
                    crc <= 0;
                    state <= SEND;
                end
                SEND: if (byte_ready) begin
                    if (index >= 1 && index <= 13)
                        crc <= crc_byte(crc, byte_data);
                    if (index == 14) state <= DRAIN;
                    else index <= index + 1'b1;
                end
                DRAIN: if (uart_idle) state <= IDLE;
                default: state <= IDLE;
            endcase
        end
    end
endmodule

`default_nettype wire
