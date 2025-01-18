`timescale 1ns/1ps
`default_nettype none

module tb_timeout;
    reg clk_12m = 0;
    always #5 clk_12m = !clk_12m;
    reg uart_rx = 1, button_n = 1;
    wire uart_tx, bid_led_n, ask_led_n;
    quoteextrema_top dut (.*);
    reg [7:0] injected_data;

    task automatic inject(input [7:0] value, input boundary, input error);
        begin
            @(negedge clk_12m);
            injected_data = value;
            force dut.rx_valid = 1;
            force dut.rx_data = injected_data;
            if (boundary) dut.silence = 23999;
            if (error) force dut.rx_error = 1;
            #1;
            if (dut.timeout !== 0) $fatal(1, "byte did not override timeout");
            @(posedge clk_12m);
            #1;
            release dut.rx_valid;
            release dut.rx_data;
            release dut.rx_error;
        end
    endtask

    initial begin
        repeat (32) @(negedge clk_12m);
        inject(8'hA5, 0, 0);
        inject(8'd5, 1, 0);
        if (dut.link.receiver.state !== 2 || dut.link.incomplete_frames !== 0 || dut.silence !== 0)
            $fatal(1, "timeout boundary byte lost");
        repeat (24000) @(posedge clk_12m);
        #1;
        if (dut.link.incomplete_frames !== 1 || dut.link.receiver.state !== 0)
            $fatal(1, "partial frame did not expire after 24000 clocks");
        inject(8'hA5, 0, 0);
        inject(8'd5, 1, 1);
        if (dut.link.incomplete_frames !== 2 || dut.link.uart_errors !== 1 ||
            dut.link.receiver.state !== 0 || !bid_led_n || !ask_led_n)
            $fatal(1, "framing error did not override byte at boundary");
        $display("PASS timeout: boundary byte, expiry, and error priority");
        $finish;
    end
endmodule

`default_nettype wire
