`timescale 1ns/1ps
`default_nettype none

module quote_core (
    input  wire        clk,
    input  wire        rst,
    input  wire        clear,
    input  wire        quote_valid,
    input  wire        quote_ask,
    input  wire [31:0] quote_price,
    output reg         bid_valid,
    output reg  [31:0] bid,
    output reg         ask_valid,
    output reg  [31:0] ask
);
    always @(posedge clk) begin
        if (rst || clear) begin
            bid_valid <= 0;
            bid <= 0;
            ask_valid <= 0;
            ask <= 0;
        end else if (quote_valid) begin
            if (quote_ask) begin
                if (!ask_valid || quote_price < ask)
                    ask <= quote_price;
                ask_valid <= 1;
            end else begin
                if (!bid_valid || quote_price > bid)
                    bid <= quote_price;
                bid_valid <= 1;
            end
        end
    end

`ifndef SYNTHESIS
    // Compare pre-edge state against the previous edge's accepted action.
    reg seen = 0;
    reg previous_reset, previous_quote, previous_ask;
    reg previous_bid_valid, previous_ask_valid;
    reg [31:0] previous_bid, previous_ask_price;
    always @(posedge clk) begin
        if (seen) begin
            if (previous_reset) begin
                assert ({bid_valid, ask_valid, bid, ask} == 66'd0)
                    else $fatal(1, "quote reset did not clear state");
            end else if (!previous_quote) begin
                assert ({bid_valid, ask_valid, bid, ask} ==
                        {previous_bid_valid, previous_ask_valid,
                         previous_bid, previous_ask_price})
                    else $fatal(1, "state changed without an accepted quote");
            end else if (previous_ask) begin
                assert ({bid_valid, bid} == {previous_bid_valid, previous_bid})
                    else $fatal(1, "ask changed bid state");
                assert (ask_valid && (!previous_ask_valid || ask <= previous_ask_price))
                    else $fatal(1, "ask lost validity or increased");
            end else begin
                assert ({ask_valid, ask} == {previous_ask_valid, previous_ask_price})
                    else $fatal(1, "bid changed ask state");
                assert (bid_valid && (!previous_bid_valid || bid >= previous_bid))
                    else $fatal(1, "bid lost validity or decreased");
            end
        end
        seen <= 1;
        previous_reset <= rst || clear;
        previous_quote <= quote_valid;
        previous_ask <= quote_ask;
        previous_bid_valid <= bid_valid;
        previous_ask_valid <= ask_valid;
        previous_bid <= bid;
        previous_ask_price <= ask;
    end
`endif
endmodule

`default_nettype wire
