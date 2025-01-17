`timescale 1ns/1ps
`default_nettype none

module tb_link;
    reg clk = 0;
    always #5 clk = !clk;
    reg rst, rx_valid, rx_abort, rx_error, tx_ready, tx_idle;
    reg [7:0] rx_data;
    wire rx_ready, tx_valid, response_busy, bid_valid, ask_valid;
    wire [7:0] tx_data;
    wire [31:0] bid, ask, valid_frames, crc_errors, invalid_lengths;
    wire [31:0] incomplete_frames, discarded_bytes, semantic_errors, busy_reads, uart_errors;

    quote_interface dut (.*);
    integer fd, parsed, cycle = 0;
    integer i_rst, i_valid, i_data, i_abort, i_error, i_ready, i_idle;
    integer e_tx_valid, e_tx_data, e_flags, e_busy;
    reg [31:0] e_bid, e_ask, e_frames, e_crc, e_lengths, e_incomplete;
    reg [31:0] e_discarded, e_semantic, e_reads, e_uart;
    reg [1023:0] vectors;

    initial begin
        if (!$value$plusargs("vectors=%s", vectors)) $fatal(1, "missing vector file");
        fd = $fopen(vectors, "r");
        if (fd == 0) $fatal(1, "could not open vectors");
        rst = 1;
        rx_valid = 0;
        rx_data = 0;
        rx_abort = 0;
        rx_error = 0;
        tx_ready = 1;
        tx_idle = 1;
        while (!$feof(fd)) begin
            parsed = $fscanf(fd, "%d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d\n",
                i_rst, i_valid, i_data, i_abort, i_error, i_ready, i_idle,
                e_tx_valid, e_tx_data, e_bid, e_ask, e_flags, e_busy,
                e_frames, e_crc, e_lengths, e_incomplete, e_discarded,
                e_semantic, e_reads, e_uart);
            if (parsed != 21) $fatal(1, "bad vector line at cycle %0d", cycle);
            @(negedge clk);
            rst = i_rst;
            rx_valid = i_valid;
            rx_data = i_data;
            rx_abort = i_abort;
            rx_error = i_error;
            tx_ready = i_ready;
            tx_idle = i_idle;
            @(posedge clk);
            if (tx_valid !== e_tx_valid[0] ||
                (tx_valid && tx_data !== e_tx_data[7:0]))
                $fatal(1, "TX mismatch at cycle %0d: valid=%b data=%h expected=%0d/%h",
                       cycle, tx_valid, tx_data, e_tx_valid, e_tx_data[7:0]);
            if (rx_ready !== !(rst || rx_abort || rx_error))
                $fatal(1, "unexpected RX backpressure at cycle %0d", cycle);
            #1;
            if ({bid_valid, ask_valid, bid, ask} !== {e_flags[0], e_flags[1], e_bid, e_ask})
                $fatal(1, "quote state mismatch at cycle %0d", cycle);
            if (response_busy !== e_busy[0]) $fatal(1, "busy mismatch at cycle %0d", cycle);
            if ({valid_frames, crc_errors, invalid_lengths, incomplete_frames,
                 discarded_bytes, semantic_errors, busy_reads, uart_errors} !==
                {e_frames, e_crc, e_lengths, e_incomplete, e_discarded, e_semantic, e_reads, e_uart})
                $fatal(1, "counter mismatch at cycle %0d", cycle);
            cycle = cycle + 1;
        end
        $fclose(fd);
        $display("PASS differential: %0d cycles", cycle);
        $finish;
    end
endmodule

`default_nettype wire
