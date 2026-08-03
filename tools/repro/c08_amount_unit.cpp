#include <bmx_pc_phosphorus.H>

#include <algorithm>
#include <array>
#include <cassert>
#include <cmath>
#include <iostream>
#include <limits>

namespace
{
  using Real = amrex::Real;
  using Particle = std::array<Real, MAX_CHEM_REAL_VAR>;

  bool close (Real lhs, Real rhs)
  {
    const Real scale = std::max(std::abs(lhs), std::abs(rhs));
    return std::abs(lhs-rhs) <= BMXPhosphorus::localTolerance(scale);
  }

  void set_state (Particle& particle, Real volume,
                  const Real committed[3], const Real working[3],
                  const Real transfer[3])
  {
    particle.fill(0.0);
    particle[realIdx::vol] = volume;
    Real* values = &particle[realIdx::first_data];
    for (int state = 0; state < BMXPhosphorus::state_count; ++state) {
      const int component = BMXPhosphorus::particle_component[state];
      values[component] = committed[state];
      values[NUM_PARTICLE_CHEM_COMPONENTS + component] = working[state];
      values[2*NUM_PARTICLE_CHEM_COMPONENTS + component] = transfer[state];
    }
  }

  void check_partition (const BMXPhosphorus::ParticleAmounts& before,
                        Particle* particles, int count)
  {
    for (int state = 0; state < BMXPhosphorus::state_count; ++state) {
      Real committed = 0.0;
      Real working = 0.0;
      Real transfer = 0.0;
      const int component = BMXPhosphorus::particle_component[state];
      for (int i = 0; i < count; ++i) {
        const Real volume = particles[i][realIdx::vol];
        const Real* values = &particles[i][realIdx::first_data];
        committed += values[component] * volume;
        working += values[NUM_PARTICLE_CHEM_COMPONENTS + component] * volume;
        transfer += values[2*NUM_PARTICLE_CHEM_COMPONENTS + component];
      }
      assert(close(committed, before.concentration_amount[0][state]));
      assert(close(working, before.concentration_amount[1][state]));
      assert(close(transfer, before.transfer_amount[state]));
    }
  }
}

int main ()
{
  const Real committed[3] = {2.0, 3.0, 5.0};
  const Real working[3] = {-0.2, 0.3, -0.5};
  const Real transfer[3] = {-7.0, 11.0, 13.0};

  Particle parent{};
  set_state(parent, 10.0, committed, working, transfer);
  parent[realIdx::first_data + BMXChemLayout::A] = 123.0;

  BMXPhosphorus::ParticleAmounts before;
  assert(BMXPhosphorus::captureParticleAmounts(parent.data(), before) ==
         BMXPhosphorus::AmountStatus::ok);

  Particle grown = parent;
  grown[realIdx::vol] = 25.0;
  Real* grown_owner[1] = {grown.data()};
  assert(BMXPhosphorus::writePartition(before, grown_owner, 1) ==
         BMXPhosphorus::AmountStatus::ok);
  check_partition(before, &grown, 1);

  Particle two[2]{};
  two[0][realIdx::vol] = 4.0;
  two[1][realIdx::vol] = 6.0;
  two[0][realIdx::first_data + BMXChemLayout::A] = 41.0;
  two[1][realIdx::first_data + BMXChemLayout::A] = 61.0;
  assert(BMXPhosphorus::partitionTwo(before, two[0].data(), two[1].data()) ==
         BMXPhosphorus::AmountStatus::ok);
  check_partition(before, two, 2);
  assert(two[0][realIdx::first_data + BMXChemLayout::A] == 41.0);
  assert(two[1][realIdx::first_data + BMXChemLayout::A] == 61.0);

  Particle three[3]{};
  three[0][realIdx::vol] = 2.0;
  three[1][realIdx::vol] = 3.0;
  three[2][realIdx::vol] = 5.0;
  assert(BMXPhosphorus::partitionThree(
             before, three[0].data(), three[1].data(), three[2].data()) ==
         BMXPhosphorus::AmountStatus::ok);
  check_partition(before, three, 3);

  Particle first{};
  Particle second{};
  const Real committed_first[3] = {1.0, 2.0, 3.0};
  const Real committed_second[3] = {4.0, 5.0, 6.0};
  const Real working_first[3] = {0.1, -0.2, 0.3};
  const Real working_second[3] = {-0.4, 0.5, -0.6};
  const Real transfer_first[3] = {7.0, -8.0, 9.0};
  const Real transfer_second[3] = {-1.0, 2.0, -3.0};
  set_state(first, 4.0, committed_first, working_first, transfer_first);
  set_state(second, 6.0, committed_second, working_second, transfer_second);
  BMXPhosphorus::ParticleAmounts first_amounts;
  BMXPhosphorus::ParticleAmounts second_amounts;
  assert(BMXPhosphorus::captureParticleAmounts(first.data(), first_amounts) ==
         BMXPhosphorus::AmountStatus::ok);
  assert(BMXPhosphorus::captureParticleAmounts(second.data(), second_amounts) ==
         BMXPhosphorus::AmountStatus::ok);

  Particle merged{};
  merged[realIdx::vol] = 10.0;
  assert(BMXPhosphorus::mergeTwo(first_amounts, second_amounts, merged.data()) ==
         BMXPhosphorus::AmountStatus::ok);
  BMXPhosphorus::ParticleAmounts merged_amounts;
  assert(BMXPhosphorus::captureParticleAmounts(merged.data(), merged_amounts) ==
         BMXPhosphorus::AmountStatus::ok);
  for (int block = 0; block < BMXPhosphorus::concentration_block_count; ++block) {
    for (int state = 0; state < BMXPhosphorus::state_count; ++state) {
      assert(close(merged_amounts.concentration_amount[block][state],
                   first_amounts.concentration_amount[block][state] +
                   second_amounts.concentration_amount[block][state]));
    }
  }
  for (int state = 0; state < BMXPhosphorus::state_count; ++state) {
    assert(close(merged_amounts.transfer_amount[state],
                 first_amounts.transfer_amount[state] +
                 second_amounts.transfer_amount[state]));
  }

  Particle invalid{};
  invalid[realIdx::vol] = 0.0;
  BMXPhosphorus::ParticleAmounts unused;
  assert(BMXPhosphorus::captureParticleAmounts(invalid.data(), unused) ==
         BMXPhosphorus::AmountStatus::invalid_volume);
  invalid[realIdx::vol] = 1.0;
  invalid[realIdx::first_data + BMXChemLayout::P_D] =
      std::numeric_limits<Real>::infinity();
  assert(BMXPhosphorus::captureParticleAmounts(invalid.data(), unused) ==
         BMXPhosphorus::AmountStatus::nonfinite);
  invalid[realIdx::first_data + BMXChemLayout::P_D] = -1.0;
  assert(BMXPhosphorus::captureParticleAmounts(invalid.data(), unused) ==
         BMXPhosphorus::AmountStatus::negative_amount);
  invalid[realIdx::first_data + BMXChemLayout::P_D] =
      std::numeric_limits<Real>::max();
  invalid[realIdx::vol] = 2.0;
  assert(BMXPhosphorus::captureParticleAmounts(invalid.data(), unused) ==
         BMXPhosphorus::AmountStatus::nonfinite);

  assert(BMXPhosphorus::localTolerance(2.0) ==
         128.0 * std::numeric_limits<Real>::epsilon());
  assert(BMXPhosphorus::integratedTolerance(0.0) == 1.0e-28);
  assert(BMXPhosphorus::integratedTolerance(2.0) == 2.0e-10);
  assert(!BMXPhosphorus::negativeAboveIntegratedTolerance(-1.0e-29, 0.0));
  assert(BMXPhosphorus::negativeAboveIntegratedTolerance(-2.0e-28, 0.0));
  assert(!BMXPhosphorus::negativeAboveIntegratedTolerance(2.0e-28, 0.0));
  // The scale term must be reachable: at S_L1=1e-6 the tolerance is 1e-16,
  // so ordinary noise below that scale is not misclassified as a hard error.
  assert(!BMXPhosphorus::negativeAboveIntegratedTolerance(-2.0e-22, 1.0e-6));
  assert(BMXPhosphorus::negativeAboveIntegratedTolerance(-2.0e-16, 1.0e-6));

  BMXPhosphorus::ParticleTotals mesh{1.0, 0.0, 2.0};
  BMXPhosphorus::ParticleTotals internal{3.0, 5.0, 7.0};
  BMXPhosphorus::CumulativeLedger ledger;
  ledger.structural_p = 11.0;
  ledger.exported_p = 13.0;
  assert(BMXPhosphorus::otherExitLedgerIsZero(ledger));
  assert(BMXPhosphorus::accountedTotal(mesh, internal, ledger) == 42.0);
  ledger.other_exits.d = 1.0;
  assert(!BMXPhosphorus::otherExitLedgerIsZero(ledger));

  const auto orphan_ok = BMXPhosphorus::classifyOrphanBond(true, false);
  assert(orphan_ok.disposition == BMXPhosphorus::TopologyDisposition::permit);
  assert(std::string(BMXPhosphorus::topologyReasonCode(orphan_ok.reason)) ==
         "P10_BOND_ENDPOINT_REMAPPED");
  const auto orphan_missing = BMXPhosphorus::classifyOrphanBond(false, false);
  assert(orphan_missing.disposition ==
         BMXPhosphorus::TopologyDisposition::abort_update);
  assert(std::string(BMXPhosphorus::topologyReasonCode(
             orphan_missing.reason)) == "P10_ABORT_ORPHAN_BOND_NO_SUCCESSOR");
  const auto orphan_material = BMXPhosphorus::classifyOrphanBond(false, true);
  assert(std::string(BMXPhosphorus::topologyReasonCode(
             orphan_material.reason)) ==
         "P10_ABORT_ORPHAN_BOND_PENDING_MATERIAL");
  const auto disjoint = BMXPhosphorus::classifySimultaneousBatch(1);
  const auto conflict = BMXPhosphorus::classifySimultaneousBatch(2);
  assert(disjoint.disposition == BMXPhosphorus::TopologyDisposition::permit);
  assert(conflict.disposition ==
         BMXPhosphorus::TopologyDisposition::abort_update);
  assert(std::string(BMXPhosphorus::topologyReasonCode(conflict.reason)) ==
         "P10_ABORT_SIMULTANEOUS_TOPOLOGY_CONFLICT");

  std::cout << "C08 amount unit PASS\n";
  return 0;
}
