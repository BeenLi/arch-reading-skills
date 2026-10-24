// 4-stage load pipeline (S0 agen / S1 tlb+tag / S2 hit+data / S3 writeback) with a
// replay path S2 -> S0 and a kill S2 -> S1 — layout test modeled on a LoadUnit diagram.
module load_pipe (
    input  wire        clk,
    input  wire        rst,
    input  wire        iq_valid,
    input  wire [31:0] iq_base,
    input  wire [31:0] iq_offset,
    output wire        iq_ready,
    input  wire [19:0] tlb_ppn,
    input  wire        tlb_hit,
    input  wire [19:0] tag_rdata,
    input  wire [31:0] data_rdata,
    output wire        mshr_req_valid,
    output wire [31:0] mshr_req_paddr,
    output reg         wb_valid,
    output reg  [31:0] wb_data,
    output reg         wb_exception
);
    wire        replay_valid;
    wire [31:0] replay_vaddr;
    wire        s1_kill;
    // S0: pick replay over a new request, generate the virtual address
    wire        s0_valid    = replay_valid | iq_valid;
    wire [31:0] s0_vaddr    = replay_valid ? replay_vaddr : (iq_base + iq_offset);
    wire        s0_misalign = |s0_vaddr[1:0];
    assign iq_ready = ~replay_valid;
    reg s1_valid, s1_misalign; reg [31:0] s1_vaddr;
    always @(posedge clk) begin
        s1_valid <= rst ? 1'b0 : s0_valid;
        s1_vaddr <= s0_vaddr;
        s1_misalign <= s0_misalign;
    end
    // S1: TLB translate + tag compare
    wire [31:0] s1_paddr   = {tlb_ppn, s1_vaddr[11:0]};
    wire        s1_tag_hit = (tag_rdata == tlb_ppn) & tlb_hit;
    reg s2_valid, s2_hit, s2_tlb_miss, s2_misalign; reg [31:0] s2_paddr, s2_vaddr;
    always @(posedge clk) begin
        s2_valid <= rst ? 1'b0 : (s1_valid & ~s1_kill);
        s2_paddr <= s1_paddr;  s2_vaddr <= s1_vaddr;
        s2_hit <= s1_tag_hit;  s2_tlb_miss <= ~tlb_hit;  s2_misalign <= s1_misalign;
    end
    // S2: replay on TLB miss (kills the younger op in S1), MSHR on cache miss, byte select
    assign replay_valid   = s2_valid & s2_tlb_miss;
    assign replay_vaddr   = s2_vaddr;
    assign s1_kill        = replay_valid;
    assign mshr_req_valid = s2_valid & ~s2_hit & ~s2_tlb_miss;
    assign mshr_req_paddr = s2_paddr;
    wire [7:0]  s2_byte = data_rdata >> {s2_paddr[1:0], 3'b000};
    // S3: writeback
    always @(posedge clk) begin
        wb_valid     <= rst ? 1'b0 : (s2_valid & s2_hit & ~s2_tlb_miss);
        wb_data      <= {24'b0, s2_byte};
        wb_exception <= s2_valid & s2_misalign;
    end
endmodule
