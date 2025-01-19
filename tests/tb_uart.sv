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
    integer baud_ppm = 0, phase_ps = 0, reset_epoch = 0, start_epoch;
    always @(negedge button_n) reset_epoch = reset_epoch + 1;
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

    task automatic bad_stop(input [7:0] value);
        integer bit_index;
        begin
            uart_rx = 0;
            #(host_bit_ns);
            for (bit_index = 0; bit_index < 8; bit_index = bit_index + 1) begin
                uart_rx = value[bit_index];
                #(host_bit_ns);
            end
            uart_rx = 0;
            #(host_bit_ns);
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
            start_epoch = reset_epoch;
            #(host_bit_ns / 2.0);
            if (start_epoch == reset_epoch && uart_tx !== 0) $fatal(1, "TX start bit not held");
            for (bit_number = 0; bit_number < 8; bit_number = bit_number + 1) begin
                #(host_bit_ns);
                received_byte[bit_number] = uart_tx;
            end
            #(host_bit_ns);
            if (start_epoch == reset_epoch) begin
                if (uart_tx !== 1) $fatal(1, "TX stop bit not high");
                if (received >= expected_count || received_byte !== expected[received])
                    $fatal(1, "UART response mismatch at byte %0d: received %h expected %h",
                           received, received_byte, expected[received]);
                received = received + 1;
            end
        end
    end

    initial begin
        if (!$value$plusargs("actions=%s", actions_path)) $fatal(1, "missing UART actions");
        fd = $fopen(actions_path, "r");
        if (fd == 0) $fatal(1, "could not open UART actions");
        repeat (32) @(negedge clk_12m);
        if ($value$plusargs("baud_ppm=%d", baud_ppm)) begin end
        if ($value$plusargs("phase_ps=%d", phase_ps)) begin end
        host_bit_ns = (1000000000.0 / 115200.0) / (1.0 + baud_ppm / 1000000.0);
        #(phase_ps / 1000.0);
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
                3: begin
                    uart_rx = 0;
                    #(value * CLOCK_NS);
                    uart_rx = 1;
                    #(2.0 * host_bit_ns);
                end
                4: bad_stop(value[7:0]);
                5: begin
                    uart_rx = 0;
                    #(value * CLOCK_NS);
                    uart_rx = 1;
                    #(2.0 * host_bit_ns);
                end
                8: begin
`ifndef GATE_LEVEL
                    if (dut.link.uart_errors !== value[31:0])
                        $fatal(1, "UART error counter mismatch");
`endif
                end
                9: begin
`ifndef GATE_LEVEL
                    if (dut.link.incomplete_frames !== value[31:0])
                        $fatal(1, "incomplete counter mismatch");
`endif
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
        $display("PASS UART: %0d bytes matched, host baud offset %0d ppm", received, baud_ppm);
        $finish;
    end
endmodule

`default_nettype wire
