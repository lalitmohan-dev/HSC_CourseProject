# DSE Framework — Decision Log

## Architecture Decisions

### D1: Generalized IR over Binary Mapping (v2.1 §1, §4)
- **Decision**: Use a generalized system-synthesis model (α, β, τ) instead of binary SW/HW labels
- **Rationale**: The spec explicitly requires one evaluator with the CPU/FPGA toggle as a preset
- **Status**: Adopted

### D2: Buses as Scheduled Resources (v2.1 §2, §4.6)
- **Decision**: Bus transfers occupy bus resources and are serialized (max_parallel=1 default)
- **Rationale**: User's latest formulation supersedes older no-contention assumption
- **Status**: Adopted

### D3: DMA-style Transfers (v2.1 §4.6 R4)
- **Decision**: Bus transfers do not block the source/destination compute resource
- **Rationale**: Golden test depends on this (V6 on SB while RISC runs V3)
- **Status**: Adopted

### D4: Deterministic Routing, Not Searched (v2.1 §4.3 R1)
- **Decision**: Routes are deterministic shortest-hop with stable ID tie-break; not a search variable in v1
- **Rationale**: Simplifies search space; one route per allocation+binding
- **Status**: Adopted

### D5: Fixed Priority Policy, Not Searched (v2.1 §6.3 R2)
- **Decision**: One fixed default priority policy for all strategies; not searched in v1
- **Rationale**: Reduces search dimensions; manual override for fixtures/evaluate
- **Status**: Adopted

### D6: Allocation Derived from Binding (v2.1 §4.4 R16)
- **Decision**: α = mandatory ∪ bound resources ∪ route buses; unused optional resources are dropped
- **Rationale**: Prevents duplicate candidates; search only proposes bindings
- **Status**: Adopted

### D7: Abstract Time Units Supported (v2.1 §5.4 R3)
- **Decision**: If meta.time_unit ≠ "ms", power/energy/throughput are unavailable
- **Rationale**: Golden test uses ticks, not ms
- **Status**: Adopted

### D8: Null Power = Unknown, Zero = Explicit (v2.1 §5.3 R8)
- **Decision**: Nullable power fields; null marks energy/power as unavailable
- **Rationale**: Prevents silent zero substitution
- **Status**: Adopted

## Implementation Choices

### I1: Project Structure
- All code under `dse/` directory
- Backend at `dse/backend/`, frontend at `dse/frontend/`
- Shared docs at `docs/`

### I2: Backend Package Layout
- Following the spec §11 structure: ir/, core/, search/, persistence/, reporting/
- Pure Python evaluator/scheduler with no FastAPI imports
