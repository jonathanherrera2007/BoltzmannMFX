# C10 blocker report — D-C10-02

Status: `BLOCKED` at the prospectively frozen P12 grid/time gate.

The L0 and L1 low-D runs agree in final cumulative uptake to 0.0113%, but
the L2 low-D run does not. At L2 the per-step request exceeds the amount in
the one-to-one donor cell before diffusion replenishes it. The frozen shared
donor rule therefore scales the low arm to `0.5969698781537861`, rejects
`9.73557376528791e-13 mol`, and lowers accepted uptake by 39.6% relative to
L1. The L1-to-L2 cumulative-uptake relative difference is
`0.6562069705917112`, above the preregistered `0.02` gate.

No production resolution satisfies the rule that a selected level and every
finer successor must pass. The arms, parameters, grid levels, timesteps, and
acceptance thresholds were not changed after this result.

Resolution requires a newly frozen and independently reviewed numerical
contract. Candidate classes are a timestep refinement that keeps per-step
donor demand resolved as cell volume shrinks, or a separately specified
spatial donor arbitration/deposition rule. The writer does not select either
after seeing outcomes.

Consequences:

- C10 cannot be qualified `PASS`.
- C11/P13, C12/P14, and C13/P15 Stage 0 were not started.
- There is no selected production resolution, so no honest reference-host
  per-run timing or 151-configuration campaign projection exists.
- No cloud instance was launched; external spend is `$0`.
