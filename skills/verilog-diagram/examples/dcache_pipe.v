// Direct-mapped D-cache lookup pipeline — test design for arch2drawio (SRAM table + pipeline + feedback).
// S0: pick replay over a new request, index the valid/tag/data arrays (synchronous read)
// S1: tag compare, hit / miss
// S2: respond; a miss waits for the refill, which writes the arrays and replays the request into S0
module dcache_pipe #(parameter SETS = 64) (
    input  wire        clk,
    input  wire        rst,
    input  wire        req_valid,
    input  wire [31:0] req_addr,
    output wire        req_ready,
    input  wire        refill_valid,
    input  wire [31:0] refill_data,
    output wire        miss_valid,
    output wire [31:0] miss_addr,
    output reg         resp_valid,
    output reg  [31:0] resp_data
);
    reg        valid_arr [0:SETS-1];
    reg [19:0] tag_arr   [0:SETS-1];
    reg [31:0] data_arr  [0:SETS-1];

    wire        replay_valid;
    wire [31:0] replay_addr;

    // S0
    wire        s0_valid = replay_valid | req_valid;
    wire [31:0] s0_addr  = replay_valid ? replay_addr : req_addr;
    wire [5:0]  s0_idx   = s0_addr[11:6];
    assign req_ready = ~replay_valid;

    reg        s1_valid;
    reg [31:0] s1_addr;
    reg        s1_v_rd;
    reg [19:0] s1_tag_rd;
    reg [31:0] s1_data_rd;
    always @(posedge clk) begin
        s1_valid   <= rst ? 1'b0 : s0_valid;
        s1_addr    <= s0_addr;
        s1_v_rd    <= valid_arr[s0_idx];
        s1_tag_rd  <= tag_arr[s0_idx];
        s1_data_rd <= data_arr[s0_idx];
    end

    // S1
    wire s1_hit = s1_v_rd & (s1_tag_rd == s1_addr[31:12]);

    reg        s2_valid, s2_hit;
    reg [31:0] s2_addr, s2_data;
    always @(posedge clk) begin
        s2_valid <= rst ? 1'b0 : s1_valid;
        s2_hit   <= s1_hit;
        s2_addr  <= s1_addr;
        s2_data  <= s1_data_rd;
    end

    // S2: miss -> request refill; the refill writes the arrays and replays the request
    assign miss_valid   = s2_valid & ~s2_hit;
    assign miss_addr    = s2_addr;
    assign replay_valid = miss_valid & refill_valid;
    assign replay_addr  = s2_addr;
    always @(posedge clk) begin
        if (replay_valid) begin
            valid_arr[s2_addr[11:6]] <= 1'b1;
            tag_arr[s2_addr[11:6]]   <= s2_addr[31:12];
            data_arr[s2_addr[11:6]]  <= refill_data;
        end
    end

    always @(posedge clk) begin
        resp_valid <= rst ? 1'b0 : (s2_valid & s2_hit);
        resp_data  <= s2_data;
    end
endmodule
