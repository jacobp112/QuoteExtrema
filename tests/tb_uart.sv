`timescale 1ns/1ps
`default_nettype none

module tb_uart;
    localparam real CLOCK_NS = 1000000000.0 / 12000000.0;
    reg clk_12m = 0;
    always #(CLOCK_NS / 2.0) clk_12m = !clk_12m;
    reg uart_rx = 1;
    reg button_n = 1;
    wire uart_tx, bid_led_n, ask_led_n;
    quoteextrema_top dut (.*);

    real host_bit_ns = 1000000000.0 / 115200.0;
    reg [7:0] expected [0:4095];
    integer expected_count, received = 0;
    integer fd, parsed, op, value, cycles;
    reg [1023:0] actions_path, expected_path;
    reg [7:0] received_byte;
    integer bit_number;

    task automatic send_byte(input [7:0] value);
        integer bit_index;
        begin
            uart_rx = 0;
            #(host_bit_ns);
            for (bit_index = 0; bit_index < 8; bit_index = bit_index + 1) begin
                uart_rx = value[bit_index];
                #(host_bit_ns);
            end
            uart_rx = 1;
            #(host_bit_ns);
        end
    endtask

    // Independent host-side waveform decoder observes only the TX pin.
    initial begin
        if (!$value$plusargs("expected=%s", expected_path) ||
            !$value$plusargs("count=%d", expected_count))
            $fatal(1, "missing expected UART response");
        $readmemh(expected_path, expected, 0, expected_count - 1);
        forever begin
            @(negedge uart_tx);
            #(host_bit_ns / 2.0);
            if (uart_tx !== 0) $fatal(1, "TX start bit not held");
            for (bit_number = 0; bit_number < 8; bit_number = bit_number + 1) begin
                #(host_bit_ns);
                received_byte[bit_number] = uart_tx;
            end
            #(host_bit_ns);
            if (uart_tx !== 1) $fatal(1, "TX stop bit not high");
            if (received >= expected_count || received_byte !== expected[received])
                $fatal(1, "UART response mismatch at byte %0d: received %h expected %h",
                       received, received_byte, expected[received]);
            received = received + 1;
        end
    end

    initial begin
        if (!$value$plusargs("actions=%s", actions_path)) $fatal(1, "missing UART actions");
        fd = $fopen(actions_path, "r");
        if (fd == 0) $fatal(1, "could not open UART actions");
        repeat (32) @(negedge clk_12m);
        while (!$feof(fd)) begin
            parsed = $fscanf(fd, "%d %d\n", op, value);
            if (parsed != 2) $fatal(1, "malformed UART action");
            case (op)
                0: send_byte(value[7:0]);
                1: repeat (value) @(negedge clk_12m);
                2: begin
                    button_n = 0;
                    repeat (value) @(negedge clk_12m);
                    button_n = 1;
                    repeat (8) @(negedge clk_12m);
                end
                default: $fatal(1, "unknown UART action");
            endcase
        end
        $fclose(fd);
        cycles = 0;
        while (received < expected_count && cycles < 50000) begin
            @(negedge clk_12m);
            cycles = cycles + 1;
        end
        if (received != expected_count) $fatal(1, "UART response timeout");
        repeat (2000) @(negedge clk_12m);
        $display("PASS UART: %0d bytes matched at nominal host baud", received);
        $finish;
    end
endmodule

`default_nettype wire
