// Weighted round-robin arbiter (single stage + state registers) — layout test modeled on
// the "masked / unmasked fixed priority + weight counters + pointer" reference diagram.
module wrr_arbiter #(parameter N = 4, parameter W = 4) (
    input  wire           clk,
    input  wire           rst_n,
    input  wire [N-1:0]   req,
    input  wire [N*W-1:0] weight,
    output wire [N-1:0]   grant
);
    reg  [N-1:0] ptr;                                   // priority mask (thermometer)
    wire [N-1:0] req_masked   = req & ptr;
    wire [N-1:0] mask_grant   = req_masked & ~(req_masked - 1'b1);   // fixed priority, masked
    wire [N-1:0] unmask_grant = req & ~(req - 1'b1);                 // fixed priority, unmasked
    wire         no_masked    = ~(|req_masked);
    assign grant = no_masked ? unmask_grant : mask_grant;

    wire [N-1:0] mask_hpri_reqs   = ~((mask_grant - 1'b1) | mask_grant);
    wire [N-1:0] unmask_hpri_reqs = ~((unmask_grant - 1'b1) | unmask_grant);

    wire [N-1:0] cnt_over;
    genvar i;
    generate for (i = 0; i < N; i = i + 1) begin : g_cnt
        reg [W-1:0] wt_cnt;                             // per-request weight counter
        always @(posedge clk or negedge rst_n)
            if (!rst_n)        wt_cnt <= weight[i*W +: W];
            else if (grant[i]) wt_cnt <= (wt_cnt == 0) ? weight[i*W +: W] : wt_cnt - 1'b1;
        assign cnt_over[i] = grant[i] & (wt_cnt < 1);
    end endgenerate
    wire gnt_cnt_over = |cnt_over;

    always @(posedge clk or negedge rst_n)
        if (!rst_n)            ptr <= {N{1'b1}};
        else if (~|req)        ptr <= {N{1'b1}};
        else if (gnt_cnt_over) ptr <= no_masked ? unmask_hpri_reqs : mask_hpri_reqs;
endmodule
