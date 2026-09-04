module sync_fifo #(
    parameter int DATA_WIDTH = 8,
    parameter int DEPTH      = 16,
    // PTR_WIDTH = $clog2(DEPTH) + 1 — the extra MSB is used to distinguish
    // "full" from "empty" when the lower bits of wr_ptr and rd_ptr match.
    parameter int PTR_WIDTH  = $clog2(DEPTH) + 1
) (
    input  logic                  clk,
    input  logic                  rst_n,     // active-low, asynchronous
    input  logic                  wr_en,
    input  logic                  rd_en,
    input  logic [DATA_WIDTH-1:0] wr_data,
    output logic [DATA_WIDTH-1:0] rd_data,   // registered, 1-cycle latency
    output logic                  full,
    output logic                  empty,
    output logic [PTR_WIDTH-1:0]  count      // occupancy, 0..DEPTH
);

    // =========================================================================
    // Storage
    // =========================================================================
    logic [DATA_WIDTH-1:0] mem [DEPTH];

    // Pointers: PTR_WIDTH = addr_bits + 1. MSB toggles each wrap, lower bits
    // address memory. This lets us distinguish full from empty even when
    // lower bits match.
    logic [PTR_WIDTH-1:0] wr_ptr;
    logic [PTR_WIDTH-1:0] rd_ptr;

    // Address slice — ONLY the lower bits index memory. R4.
    localparam int ADDR_WIDTH = PTR_WIDTH - 1;

    // Combinational helpers: extract addr portion and MSB of pointers.
    // (Separated from always_comb to avoid iverilog-12 constant-select
    //  limitation inside procedural blocks.)
    logic [ADDR_WIDTH-1:0] wr_addr;
    logic [ADDR_WIDTH-1:0] rd_addr;
    logic                  wr_msb;
    logic                  rd_msb;
    assign wr_addr = wr_ptr[ADDR_WIDTH-1:0];
    assign rd_addr = rd_ptr[ADDR_WIDTH-1:0];
    assign wr_msb  = wr_ptr[PTR_WIDTH-1];
    assign rd_msb  = rd_ptr[PTR_WIDTH-1];

    // =========================================================================
    // Combinational status flags
    // empty: pointers identical (including MSB)
    // full : lower bits match, MSBs differ (one more wrap on write side)
    // =========================================================================
    always_comb begin
        empty = (wr_ptr == rd_ptr);
        full  = (wr_addr == rd_addr) && (wr_msb != rd_msb);
        // Subtraction with one extra bit gives correct occupancy on wrap.
        count = wr_ptr - rd_ptr;
    end

    // =========================================================================
    // Write path — async reset, async assert / sync deassert assumed at SoC
    // =========================================================================
    // Conflict policy (R6): on simultaneous wr_en && rd_en when full, the read
    // happens this cycle (rd_ptr advances, making space), and the write ALSO
    // proceeds because the "full" flag no longer blocks it — we gate on
    // (!full || rd_en) instead of (!full). This preserves full throughput.
    // =========================================================================
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            wr_ptr <= '0;
        end else if (wr_en && (!full || rd_en)) begin
            mem[wr_addr] <= wr_data;
            wr_ptr       <= wr_ptr + 1'b1;
        end
    end

    // =========================================================================
    // Read path — registered rd_data (1-cycle latency). Not FWFT.
    // On simultaneous wr_en && rd_en when empty, the write happens this cycle
    // but rd_data reflects the OLD (undefined) location. The read is gated on
    // !empty, so it simply does not fire — consumer must wait one cycle.
    // =========================================================================
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            rd_ptr  <= '0;
            rd_data <= '0;
        end else if (rd_en && !empty) begin
            rd_data <= mem[rd_addr];
            rd_ptr  <= rd_ptr + 1'b1;
        end
    end

endmodule

/* ═══ VALIDATION ═══
 * ASSUMPTIONS (defaults chosen where spec was silent):
 *   - Reset: asynchronous, active-low, asserts on negedge rst_n.
 *     (SoC is expected to synchronize deassertion — standard practice.)
 *   - Read latency: 1 cycle (registered read). NOT first-word-fall-through.
 *   - Conflict policy on full: if wr_en && rd_en && full, read proceeds AND
 *     write proceeds (net occupancy unchanged, full throughput preserved).
 *   - Conflict policy on empty: if wr_en && rd_en && empty, write proceeds,
 *     read does NOT fire; rd_data retains previous value. Consumer must
 *     wait one cycle for data to become valid.
 *   - Overflow: protected — wr_en is gated on (!full || rd_en).
 *   - Underflow: protected — rd_en is gated on !empty.
 *
 * SELF-CHECK:
 *   [x] R1 reset consistency: sensitivity list declares async; comment says
 *       "active-low, asynchronous" — consistent.
 *   [x] R2 assignment discipline: <= used in all always_ff; = used in always_comb.
 *   [x] R3 no latches: always_comb fully drives empty, full, count in every path.
 *   [x] R4 memory access: mem indexed with [ADDR_WIDTH-1:0] slice only.
 *   [x] R5 counter width: PTR_WIDTH = $clog2(DEPTH)+1, documented above.
 *   [x] R6 conflict resolution: stated explicitly for both full and empty cases.
 *   [x] R7 no lint waivers.
 *   [x] R8 deterministic X handling: wr_ptr, rd_ptr, rd_data all reset to '0.
 *       mem[] is not reset — this is standard (SRAM is not initialized in real
 *       silicon); reads are gated by !empty so no X propagation occurs.
 *
 * KNOWN LIMITATIONS:
 *   - mem[] is not explicitly reset. Reads of empty FIFO return stale data,
 *     but the !empty gate prevents this from propagating. For simulation
 *     cleanliness, add `initial mem = '{default: '0};` if desired.
 *   - count can momentarily equal DEPTH on the cycle after a write fills
 *     the last slot. Downstream logic should treat `full` (not `count==DEPTH`)
 *     as the authoritative "cannot accept more" signal.
 *   - Single clock domain only. Multi-clock (async) FIFO requires Gray-coded
 *     pointers and synchronizers — this is NOT that.
 *
 * SUGGESTED TESTBENCH CASES:
 *   1. Reset behavior: all pointers, rd_data, flags to known state.
 *   2. Fill to full: write DEPTH items, verify full asserts on last write.
 *   3. Drain to empty: read DEPTH items, verify empty asserts after last read.
 *   4. Wrap-around: fill, drain, fill again — verify MSB toggle is correct.
 *   5. Simultaneous R+W when full: verify throughput preserved, data integrity.
 *   6. Simultaneous R+W when empty: verify write proceeds, read does not.
 *   7. Simultaneous R+W mid-depth: verify count unchanged.
 *   8. Back-to-back writes with rd_en held low: verify overflow protection.
 *   9. Back-to-back reads with wr_en held low: verify underflow protection.
 *  10. Parameterization: instantiate with DEPTH=4, DEPTH=64 — verify scaling.
 * ═══════════════════ */
