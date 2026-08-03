//
//     Copyright (c) 2013 Battelle Memorial Institute
//     Licensed under modified BSD License. A copy of this license can be found
//     in the LICENSE file in the top level directory of this distribution.
//
#ifndef BMX_PC_PHOSPHORUS_H_
#define BMX_PC_PHOSPHORUS_H_

#include <AMReX.H>
#include <AMReX_GpuContainers.H>
#include <AMReX_REAL.H>

#include <bmx_chem.H>

#include <cstdint>
#include <limits>
#include <string>
#include <vector>

class BMXParticleContainer;

namespace BMXPhosphorus
{
  constexpr int state_count = 3;
  constexpr int concentration_block_count = 2;

  enum State : int
  {
    D = 0,
    E = 1,
    F = 2
  };

  constexpr int particle_component[state_count] = {
      BMXChemLayout::P_D,
      BMXChemLayout::P_E,
      BMXChemLayout::P_F
  };

  enum class AmountStatus : int
  {
    ok = 0,
    invalid_volume = 1,
    nonfinite = 2,
    conservation_failure = 3,
    negative_amount = 4
  };

  enum class TopologyDisposition : int
  {
    permit = 0,
    abort_update = 1
  };

  enum class TopologyReason : int
  {
    split_parent_replaced = 0,
    fusion_predecessor_replaced = 1,
    unmapped_particle_deletion = 2,
    out_of_domain_particle = 3,
    bond_endpoint_remapped = 4,
    zero_state_bond_pruned = 5,
    orphan_bond_no_successor = 6,
    orphan_bond_pending_material = 7,
    simultaneous_disjoint_batch = 8,
    simultaneous_topology_conflict = 9
  };

  struct TopologyDecision
  {
    TopologyDisposition disposition = TopologyDisposition::abort_update;
    TopologyReason reason = TopologyReason::unmapped_particle_deletion;
  };

  // Minimal immutable identity for one proposed topology event. The second
  // participant is {-1,-1} for a one-owner split and is the fusing tip for an
  // interior-fusion split. Stable BMX (id,cpu) identities are used instead of
  // tile indices so the global conflict decision is MPI-decomposition neutral.
  struct TopologyEventParticipants
  {
    int event_type = 0;
    int first_id = -1;
    int first_cpu = -1;
    int second_id = -1;
    int second_cpu = -1;
  };

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  constexpr const char* topologyReasonCode (TopologyReason reason) noexcept
  {
    switch (reason) {
      case TopologyReason::split_parent_replaced:
        return "P10_SPLIT_PARENT_REPLACED";
      case TopologyReason::fusion_predecessor_replaced:
        return "P10_FUSION_PREDECESSOR_REPLACED";
      case TopologyReason::unmapped_particle_deletion:
        return "P10_ABORT_UNMAPPED_PARTICLE_DELETION";
      case TopologyReason::out_of_domain_particle:
        return "P10_ABORT_OUT_OF_DOMAIN_PARTICLE";
      case TopologyReason::bond_endpoint_remapped:
        return "P10_BOND_ENDPOINT_REMAPPED";
      case TopologyReason::zero_state_bond_pruned:
        return "P10_ZERO_STATE_BOND_PRUNED";
      case TopologyReason::orphan_bond_no_successor:
        return "P10_ABORT_ORPHAN_BOND_NO_SUCCESSOR";
      case TopologyReason::orphan_bond_pending_material:
        return "P10_ABORT_ORPHAN_BOND_PENDING_MATERIAL";
      case TopologyReason::simultaneous_disjoint_batch:
        return "P10_SIMULTANEOUS_DISJOINT_BATCH";
      default:
        return "P10_ABORT_SIMULTANEOUS_TOPOLOGY_CONFLICT";
    }
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  constexpr TopologyDecision classifyOrphanBond (
      bool has_unique_live_successor,
      bool has_pending_material) noexcept
  {
    if (has_pending_material) {
      return {TopologyDisposition::abort_update,
              TopologyReason::orphan_bond_pending_material};
    }
    if (!has_unique_live_successor) {
      return {TopologyDisposition::abort_update,
              TopologyReason::orphan_bond_no_successor};
    }
    return {TopologyDisposition::permit,
            TopologyReason::bond_endpoint_remapped};
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  constexpr TopologyDecision classifySimultaneousBatch (
      int maximum_event_membership) noexcept
  {
    return maximum_event_membership > 1
        ? TopologyDecision{TopologyDisposition::abort_update,
                           TopologyReason::simultaneous_topology_conflict}
        : TopologyDecision{TopologyDisposition::permit,
                           TopologyReason::simultaneous_disjoint_batch};
  }

  // The committed and working blocks store concentration-like values owned by
  // the particle volume. The third block stores signed, extensive transfer
  // amounts deposited to the mesh. Keeping those representations distinct is
  // essential: multiplying the transfer block by volume would change units.
  struct ParticleAmounts
  {
    amrex::Real concentration_amount[concentration_block_count][state_count]{};
    amrex::Real transfer_amount[state_count]{};
  };

  struct ParticleTotals
  {
    amrex::Real d = 0.0;
    amrex::Real e = 0.0;
    amrex::Real f = 0.0;

    AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
    amrex::Real total () const noexcept { return d + e + f; }
  };

  // Persistent cumulative fields required by checkpoint schema v2. These are
  // deliberately amounts, never concentrations. The adopted v1 topology
  // contract requires every other-exit field and count to remain exactly zero.
  struct CumulativeLedger
  {
    bool reference_bound = false;
    amrex::Real reference_total_p = 0.0;
    amrex::Real structural_p = 0.0;
    amrex::Real exported_p = 0.0;
    ParticleTotals other_exits{};
    std::uint64_t other_exit_events = 0;
  };

  struct GlobalLedgerSnapshot
  {
    ParticleTotals mesh{};
    ParticleTotals internal{};
    amrex::Real accounted_total_p = 0.0;
    amrex::Real residual = 0.0;
    amrex::Real tolerance = 0.0;
  };

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  amrex::Real accountedTotal (const ParticleTotals& mesh,
                              const ParticleTotals& internal,
                              const CumulativeLedger& cumulative) noexcept
  {
    return mesh.d + mesh.f +
           internal.d + internal.e + internal.f +
           cumulative.structural_p + cumulative.exported_p +
           cumulative.other_exits.d + cumulative.other_exits.e +
           cumulative.other_exits.f;
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  bool otherExitLedgerIsZero (const CumulativeLedger& cumulative) noexcept
  {
    return cumulative.other_exits.d == 0.0 &&
           cumulative.other_exits.e == 0.0 &&
           cumulative.other_exits.f == 0.0 &&
           cumulative.other_exit_events == 0;
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  bool finite (amrex::Real value) noexcept
  {
    constexpr amrex::Real limit = std::numeric_limits<amrex::Real>::max();
    return value == value && value <= limit && value >= -limit;
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  amrex::Real concentrationToAmount (amrex::Real concentration,
                                     amrex::Real owning_volume) noexcept
  {
    return concentration * owning_volume;
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  amrex::Real amountToConcentration (amrex::Real amount,
                                     amrex::Real owning_volume) noexcept
  {
    return amount / owning_volume;
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  amrex::Real localTolerance (amrex::Real s_l1) noexcept
  {
    return 64.0 * std::numeric_limits<amrex::Real>::epsilon() * s_l1;
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  amrex::Real integratedTolerance (amrex::Real s_l1) noexcept
  {
    const amrex::Real scaled = 1.0e-10 * s_l1;
    return scaled > 1.0e-28 ? scaled : 1.0e-28;
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  bool negativeAboveIntegratedTolerance (amrex::Real amount,
                                         amrex::Real s_l1) noexcept
  {
    return amount < 0.0 &&
           amrex::Math::abs(amount) >
               integratedTolerance(s_l1);
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  AmountStatus captureParticleAmounts (const amrex::Real* particle,
                                       ParticleAmounts& amounts) noexcept
  {
    const amrex::Real volume = particle[realIdx::vol];
    if (!finite(volume) || volume <= 0.0) return AmountStatus::invalid_volume;

    const amrex::Real* values = &particle[realIdx::first_data];
    for (int state = 0; state < state_count; ++state) {
      const int component = particle_component[state];
      for (int block = 0; block < concentration_block_count; ++block) {
        const amrex::Real value =
            values[block * NUM_PARTICLE_CHEM_COMPONENTS + component];
        if (!finite(value)) return AmountStatus::nonfinite;
        const amrex::Real amount = concentrationToAmount(value, volume);
        if (!finite(amount)) return AmountStatus::nonfinite;
        // The committed block is physical inventory and cannot be negative.
        // The working block remains signed because it is an in-flight buffer.
        if (block == 0 && amount < 0.0) {
          return AmountStatus::negative_amount;
        }
        amounts.concentration_amount[block][state] = amount;
      }
      const amrex::Real transfer =
          values[2 * NUM_PARTICLE_CHEM_COMPONENTS + component];
      if (!finite(transfer)) return AmountStatus::nonfinite;
      amounts.transfer_amount[state] = transfer;
    }
    return AmountStatus::ok;
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  AmountStatus writePartition (const ParticleAmounts& source,
                               amrex::Real* const* particles,
                               int particle_count) noexcept
  {
    if (particle_count <= 0) return AmountStatus::invalid_volume;
    for (int state = 0; state < state_count; ++state) {
      for (int block = 0; block < concentration_block_count; ++block) {
        const amrex::Real amount =
            source.concentration_amount[block][state];
        if (!finite(amount)) return AmountStatus::nonfinite;
        if (block == 0 && amount < 0.0) {
          return AmountStatus::negative_amount;
        }
      }
      if (!finite(source.transfer_amount[state])) {
        return AmountStatus::nonfinite;
      }
    }

    amrex::Real total_volume = 0.0;
    for (int i = 0; i < particle_count; ++i) {
      const amrex::Real volume = particles[i][realIdx::vol];
      if (!finite(volume) || volume <= 0.0) return AmountStatus::invalid_volume;
      total_volume += volume;
      if (!finite(total_volume)) return AmountStatus::invalid_volume;
    }
    if (!finite(total_volume) || total_volume <= 0.0) {
      return AmountStatus::invalid_volume;
    }

    for (int state = 0; state < state_count; ++state) {
      const int component = particle_component[state];
      for (int block = 0; block < concentration_block_count; ++block) {
        const amrex::Real concentration = amountToConcentration(
            source.concentration_amount[block][state], total_volume);
        if (!finite(concentration)) return AmountStatus::nonfinite;
        for (int i = 0; i < particle_count; ++i) {
          amrex::Real* values = &particles[i][realIdx::first_data];
          values[block * NUM_PARTICLE_CHEM_COMPONENTS + component] = concentration;
        }
      }
      for (int i = 0; i < particle_count; ++i) {
        amrex::Real* values = &particles[i][realIdx::first_data];
        const amrex::Real partitioned_transfer =
            source.transfer_amount[state] *
            particles[i][realIdx::vol] / total_volume;
        if (!finite(partitioned_transfer)) return AmountStatus::nonfinite;
        values[2 * NUM_PARTICLE_CHEM_COMPONENTS + component] =
            partitioned_transfer;
      }
    }

    // Enforce the frozen local algebraic contract at the write boundary.  The
    // source term is included in S_L1 because the residual is child_sum-source.
    for (int state = 0; state < state_count; ++state) {
      const int component = particle_component[state];
      for (int block = 0; block < concentration_block_count; ++block) {
        amrex::Real sum = 0.0;
        amrex::Real s_l1 =
            amrex::Math::abs(source.concentration_amount[block][state]);
        for (int i = 0; i < particle_count; ++i) {
          const amrex::Real* values = &particles[i][realIdx::first_data];
          const amrex::Real amount =
              concentrationToAmount(
                  values[block * NUM_PARTICLE_CHEM_COMPONENTS + component],
                  particles[i][realIdx::vol]);
          if (!finite(amount)) return AmountStatus::nonfinite;
          sum += amount;
          s_l1 += amrex::Math::abs(amount);
        }
        if (!finite(sum) ||
            amrex::Math::abs(
                sum - source.concentration_amount[block][state]) >
                localTolerance(s_l1)) {
          return AmountStatus::conservation_failure;
        }
      }

      amrex::Real transfer_sum = 0.0;
      amrex::Real transfer_l1 =
          amrex::Math::abs(source.transfer_amount[state]);
      for (int i = 0; i < particle_count; ++i) {
        const amrex::Real* values = &particles[i][realIdx::first_data];
        const amrex::Real amount =
            values[2 * NUM_PARTICLE_CHEM_COMPONENTS + component];
        transfer_sum += amount;
        transfer_l1 += amrex::Math::abs(amount);
      }
      if (!finite(transfer_sum) ||
          amrex::Math::abs(transfer_sum - source.transfer_amount[state]) >
              localTolerance(transfer_l1)) {
        return AmountStatus::conservation_failure;
      }
    }
    return AmountStatus::ok;
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  AmountStatus partitionTwo (const ParticleAmounts& source,
                             amrex::Real* first,
                             amrex::Real* second) noexcept
  {
    amrex::Real* particles[2] = {first, second};
    return writePartition(source, particles, 2);
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  AmountStatus partitionThree (const ParticleAmounts& source,
                               amrex::Real* first,
                               amrex::Real* second,
                               amrex::Real* third) noexcept
  {
    amrex::Real* particles[3] = {first, second, third};
    return writePartition(source, particles, 3);
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  AmountStatus mergeTwo (const ParticleAmounts& first,
                         const ParticleAmounts& second,
                         amrex::Real* destination) noexcept
  {
    const amrex::Real volume = destination[realIdx::vol];
    if (!finite(volume) || volume <= 0.0) return AmountStatus::invalid_volume;
    amrex::Real* values = &destination[realIdx::first_data];
    for (int state = 0; state < state_count; ++state) {
      const int component = particle_component[state];
      for (int block = 0; block < concentration_block_count; ++block) {
        const amrex::Real first_amount =
            first.concentration_amount[block][state];
        const amrex::Real second_amount =
            second.concentration_amount[block][state];
        if (!finite(first_amount) || !finite(second_amount)) {
          return AmountStatus::nonfinite;
        }
        if (block == 0 && (first_amount < 0.0 || second_amount < 0.0)) {
          return AmountStatus::negative_amount;
        }
        const amrex::Real amount = first_amount + second_amount;
        if (!finite(amount)) return AmountStatus::nonfinite;
        const amrex::Real concentration =
            amountToConcentration(amount, volume);
        if (!finite(concentration)) return AmountStatus::nonfinite;
        values[block * NUM_PARTICLE_CHEM_COMPONENTS + component] = concentration;
        const amrex::Real written_amount =
            concentrationToAmount(concentration, volume);
        const amrex::Real s_l1 =
            amrex::Math::abs(amount) + amrex::Math::abs(written_amount);
        if (!finite(written_amount) ||
            amrex::Math::abs(written_amount - amount) > localTolerance(s_l1)) {
          return AmountStatus::conservation_failure;
        }
      }
      const amrex::Real first_transfer = first.transfer_amount[state];
      const amrex::Real second_transfer = second.transfer_amount[state];
      if (!finite(first_transfer) || !finite(second_transfer)) {
        return AmountStatus::nonfinite;
      }
      const amrex::Real transfer = first_transfer + second_transfer;
      if (!finite(transfer)) return AmountStatus::nonfinite;
      values[2 * NUM_PARTICLE_CHEM_COMPONENTS + component] = transfer;
    }
    return AmountStatus::ok;
  }

  ParticleTotals computeInternalAmounts (const BMXParticleContainer& particles);
  ParticleTotals computeTransferAmounts (const BMXParticleContainer& particles);
  void requireAuditBuffersEmpty (const BMXParticleContainer& particles,
                                 const char* boundary);
  void requireCheckpointParticlesSafe (
      BMXParticleContainer& particles,
      const std::string& checkpoint_directory,
      const std::string& particle_name);
  void requireRedistributionSafe (const BMXParticleContainer& particles);
  void requireDisjointTopologyBatch (
      const BMXParticleContainer& particles,
      const std::vector<TopologyEventParticipants>& local_events);
  void validateBondTopology (BMXParticleContainer& particles);
  void requireIntegratedConservation (const ParticleTotals& before,
                                      const ParticleTotals& after,
                                      const char* operation);

  const CumulativeLedger& cumulativeLedger () noexcept;
  void resetCumulativeLedger () noexcept;
  void creditStructuralP (amrex::Real amount);
  void creditExportedP (amrex::Real amount);
  void bindReferenceTotal (const ParticleTotals& mesh,
                           const ParticleTotals& internal);
  GlobalLedgerSnapshot evaluateGlobalLedger (const ParticleTotals& mesh,
                                             const ParticleTotals& internal,
                                             bool require_bound);
  void restoreCumulativeLedger (const CumulativeLedger& ledger);
}

#endif
