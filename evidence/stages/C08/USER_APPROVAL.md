# C08 user-approved P10-U01 contract and integrator authority

- Approval date: `2026-08-01`
- Adopted source: `contracts/USER_APPROVED_DECISION_CONTRACT_20260801.txt`
- Adopted source SHA-256: `283eace4f34e0a3d6961d49db2ab2c75ac6e384a9077a7044313a20f7bd4bc93`
- Machine contract: `contracts/p10/TOPOLOGY_EVENT_CONTRACT_V1.json`

Exact user statement:

> I adopt the attached contract as the binding user-approved decision contract, superseding the pending mentor gate for P10-U01. I authorize the implementation writer as the sole C08 integrator to modify src/des/bmx_calc_txfr.cpp, src/timestepping/bmx_evolve.cpp, src/bmx.H, and src/bmx.cpp only as needed to complete C08. This does not authorize C09 or later work.

Additional exact C08 source-ownership authorization:

> I authorize the implementation writer during C08 only to modify src/des/bmx_pc.H and src/des/bmx_pc.cpp solely to wrap inherited Redistribute and Regrid overloads with the existing preflight guard before delegating to pinned AMReX. This authorizes no wall projection/sliding and no C09+ behavior.

The full adopted source is preserved byte-for-byte. C08 consumes only its P10
topology-transfer decisions. Future P11-P16 decisions present in the source are
preserved for their separately authorized stages and are not implemented here.
