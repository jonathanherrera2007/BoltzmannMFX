//
// C13/P15 Stage 0 provisional integrated-model binding, terminal-area records,
// and conservative bonded-D transport ledgers.
//
#ifndef BMX_P15_STAGE0_K_H_
#define BMX_P15_STAGE0_K_H_

#include <AMReX_GpuQualifiers.H>
#include <AMReX_Math.H>
#include <AMReX_REAL.H>

#include <cstdint>
#include <cmath>
#include <limits>
#include <string>

class BMXParticleContainer;

namespace BMXP15Stage0
{
  constexpr int schema_version = 1;
  constexpr const char* stage_id = "C13";
  constexpr const char* authority_classification =
      "USER_ADOPTED_PROVISIONAL_PENDING_MENTOR_OVERRIDE";
  constexpr const char* binding_contract_id =
      "UDC-20260802-C13-STAGE0-BINDINGS-V1";
  constexpr const char* binding_contract_sha256 =
      "c726cc575684e078d3c3359ececef28fde91daf5050aec273161b734710875d7";
  constexpr const char* bonded_contract_id =
      "UDC-20260802-C13-BONDED-D-V1";
  constexpr const char* bonded_contract_sha256 =
      "e6022bffb56defa13cb31e7c0ac2097dfd197c9513e2f3e2e3a5ade37feeda44";
  constexpr const char* numerical_contract_id =
      "UDC-20260802-C13-216H-NUMERICAL-V1";
  constexpr const char* numerical_contract_sha256 =
      "c4d8dd50bb9c4b2b945e80410d71c4b822a32b29a325d7bb9ca5a8ec53531182";
  constexpr const char* terminal_contract_id =
      "UDC-20260802-C13-TERMINAL-ZONE-V1";
  constexpr const char* terminal_contract_sha256 =
      "272106fabb9af9221d13c9f3b82fa9a963bea831c0a983747986789452b1bfe6";
  constexpr const char* operator_fit_id =
      "bmx-p15-c13-operator-fit-v1";
  constexpr const char* operator_fit_sha256 =
      "4e391b63796f61cade7381a0a4168c6aa2d607272cd0c009cedef5aec4ad7168";
  constexpr const char* global_order_id = "bmx-p10-global-order-v1";
  constexpr const char* global_order_sha256 =
      "bb63c219a860687d91ce1acf06a667c9208abf026b32f18acfc64884bb696dd6";
  constexpr const char* authority_source_sha256 =
      "cbd1eedddf31b94c8a9d23d7b2d3329f065a007824387c70435d1004fdc6f350";
  constexpr const char* claim_boundary =
      "RG-SW-STAGE0/PROVISIONAL-USER-ADOPTED/NOT-MENTOR-APPROVAL/NOT-CALIBRATED/NOT-PREDICTIVE";

  struct Config
  {
    bool enabled = false;
    amrex::Real bonded_d_diffusivity = 0.0;
    bool cap_fault_injection = false;
    bool qualification_outcomes_enabled = false;
    std::string initial_network_sha256;
    std::string generated_configuration_sha256;
    amrex::Real expected_area_match_multiplier = 0.0;
    amrex::Real expected_initial_full_area = 0.0;
    amrex::Real expected_initial_tip010_area = 0.0;
    std::string independent_review_status = "PENDING";
    std::string independent_review_sha256 = "PENDING";
    std::string reviewed_source_commit = "PENDING";
  };

  struct TerminalAreaRecord
  {
    int particle_id = -1;
    int cpu_id = -1;
    amrex::Real full_area = 0.0;
    amrex::Real tip_005_area = 0.0;
    amrex::Real tip_010_area = 0.0;
    amrex::Real tip_020_area = 0.0;
  };

  struct AreaMatchState
  {
    int bound = 0;
    amrex::Real multiplier = 0.0;
    amrex::Real initial_full_area = 0.0;
    amrex::Real initial_tip010_area = 0.0;
  };

  struct TerminalLedger
  {
    amrex::Real current_full_area = 0.0;
    amrex::Real current_tip_005_area = 0.0;
    amrex::Real current_tip_010_area = 0.0;
    amrex::Real current_tip_020_area = 0.0;
    amrex::Real current_effective_area = 0.0;
    std::uint64_t updates = 0;
    std::uint64_t segments = 0;
    std::uint64_t live_terminal_origins = 0;
  };

  struct BondedLedger
  {
    amrex::Real requested = 0.0;
    amrex::Real accepted = 0.0;
    amrex::Real rejected = 0.0;
    amrex::Real gross_absolute_accepted = 0.0;
    amrex::Real maximum_diagonal_rate = 0.0;
    amrex::Real minimum_donor_scale = 1.0;
    std::uint64_t updates = 0;
    std::uint64_t internal_substeps = 0;
    std::uint64_t virtual_pairs = 0;
    std::uint64_t material_cap_activations = 0;
  };

  struct BondedStep
  {
    amrex::Real requested = 0.0;
    amrex::Real accepted = 0.0;
    amrex::Real rejected = 0.0;
    amrex::Real gross_absolute_accepted = 0.0;
    amrex::Real maximum_diagonal_rate = 0.0;
    amrex::Real minimum_donor_scale = 1.0;
    std::uint64_t internal_substeps = 0;
    std::uint64_t virtual_pairs = 0;
    std::uint64_t material_cap_activations = 0;
  };

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  bool finite (amrex::Real value) noexcept
  {
    return value == value &&
           value <= std::numeric_limits<amrex::Real>::max() &&
           value >= -std::numeric_limits<amrex::Real>::max();
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  amrex::Real smaller (amrex::Real first, amrex::Real second) noexcept
  {
    return first < second ? first : second;
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  amrex::Real larger (amrex::Real first, amrex::Real second) noexcept
  {
    return first > second ? first : second;
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  amrex::Real crossSectionArea (amrex::Real radius) noexcept
  {
    constexpr amrex::Real pi =
        3.141592653589793238462643383279502884;
    return pi * radius * radius;
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  amrex::Real endpointCoordinate (amrex::Real center,
                                  amrex::Real length,
                                  amrex::Real theta,
                                  amrex::Real phi,
                                  int site,
                                  int direction) noexcept
  {
    const amrex::Real sine_theta = ::sin(theta);
    amrex::Real orientation = 0.0;
    if (direction == 0) {
      orientation = sine_theta*::cos(phi);
    } else if (direction == 1) {
      orientation = sine_theta*::sin(phi);
    } else if (direction == 2) {
      orientation = ::cos(theta);
    } else {
      return std::numeric_limits<amrex::Real>::quiet_NaN();
    }
    if (site != 1 && site != 2) {
      return std::numeric_limits<amrex::Real>::quiet_NaN();
    }
    const amrex::Real sign = site == 1 ? -1.0 : 1.0;
    return center + sign*0.5*length*orientation;
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  amrex::Real halfSegmentConductance (amrex::Real diffusivity,
                                      amrex::Real radius,
                                      amrex::Real length) noexcept
  {
    return 2.0 * diffusivity * crossSectionArea(radius) / length;
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  amrex::Real virtualPairConductance (amrex::Real first_half,
                                      amrex::Real second_half,
                                      amrex::Real junction_sum) noexcept
  {
    return first_half * second_half / junction_sum;
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  amrex::Real degreeTwoConductance (amrex::Real diffusivity,
                                    amrex::Real first_radius,
                                    amrex::Real first_length,
                                    amrex::Real second_radius,
                                    amrex::Real second_length) noexcept
  {
    const amrex::Real first_area = crossSectionArea(first_radius);
    const amrex::Real second_area = crossSectionArea(second_radius);
    return diffusivity /
        (first_length / (2.0 * first_area) +
         second_length / (2.0 * second_area));
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  int stableSubsteps (amrex::Real outer_dt,
                      amrex::Real maximum_diagonal_rate) noexcept
  {
    if (!(outer_dt > 0.0) || !(maximum_diagonal_rate > 0.0)) return 1;
    const amrex::Real raw =
        outer_dt * maximum_diagonal_rate / amrex::Real(0.25);
    int result = static_cast<int>(amrex::Math::ceil(raw));
    if (result < 1) result = 1;
    while ((outer_dt / static_cast<amrex::Real>(result)) *
               maximum_diagonal_rate > amrex::Real(0.25)) {
      ++result;
    }
    return result;
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  amrex::Real terminalSnapTolerance (amrex::Real first,
                                     amrex::Real second,
                                     amrex::Real length,
                                     amrex::Real threshold) noexcept
  {
    amrex::Real scale = 1.0;
    // Infinite endpoint distance is the valid representation for a graph
    // component with no live terminal origin.  It must not inflate the local
    // snapping tolerance and erase a finite origin at the other endpoint.
    if (finite(first)) scale = larger(scale, amrex::Math::abs(first));
    if (finite(second)) scale = larger(scale, amrex::Math::abs(second));
    if (finite(length)) scale = larger(scale, amrex::Math::abs(length));
    if (finite(threshold)) {
      scale = larger(scale, amrex::Math::abs(threshold));
    }
    return 64.0 *
           amrex::Real(2.220446049250313080847263336181640625e-16) *
           scale;
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  amrex::Real terminalEligibleLength (amrex::Real distance_site_1,
                                      amrex::Real distance_site_2,
                                      amrex::Real length,
                                      amrex::Real threshold) noexcept
  {
    const amrex::Real tolerance = terminalSnapTolerance(
        distance_site_1, distance_site_2, length, threshold);
    if (finite(distance_site_1) &&
        amrex::Math::abs(distance_site_1 - threshold) <= tolerance) {
      distance_site_1 = threshold;
    }
    if (finite(distance_site_2) &&
        amrex::Math::abs(distance_site_2 - threshold) <= tolerance) {
      distance_site_2 = threshold;
    }
    amrex::Real first = finite(distance_site_1)
                            ? threshold - distance_site_1 : 0.0;
    amrex::Real second = finite(distance_site_2)
                             ? threshold - distance_site_2 : 0.0;
    first = larger(amrex::Real(0.0), smaller(length, first));
    second = larger(amrex::Real(0.0), smaller(length, second));
    return smaller(length, first + second);
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  amrex::Real physicalArea (amrex::Real radius,
                            amrex::Real eligible_length,
                            int eligible_free_caps) noexcept
  {
    constexpr amrex::Real pi =
        3.141592653589793238462643383279502884;
    return 2.0 * pi * radius * eligible_length +
           pi * radius * radius * static_cast<amrex::Real>(eligible_free_caps);
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  bool keyLess (int first_id, int first_cpu,
                int second_id, int second_cpu) noexcept
  {
    return first_id < second_id ||
           (first_id == second_id && first_cpu < second_cpu);
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  const TerminalAreaRecord* findTerminalArea (
      const TerminalAreaRecord* records,
      int count,
      int particle_id,
      int cpu_id) noexcept
  {
    int lower = 0;
    int upper = count;
    while (lower < upper) {
      const int middle = lower + (upper-lower)/2;
      const auto& candidate = records[middle];
      if (keyLess(candidate.particle_id, candidate.cpu_id,
                  particle_id, cpu_id)) {
        lower = middle + 1;
      } else {
        upper = middle;
      }
    }
    if (lower < count && records[lower].particle_id == particle_id &&
        records[lower].cpu_id == cpu_id) {
      return &records[lower];
    }
    return nullptr;
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  amrex::Real terminalEligibleArea (const TerminalAreaRecord* records,
                                    int count,
                                    int particle_id,
                                    int cpu_id,
                                    bool fungal,
                                    int area_mode,
                                    amrex::Real multiplier) noexcept
  {
    if (!fungal) return 0.0;
    const auto* record = findTerminalArea(
        records, count, particle_id, cpu_id);
    if (record == nullptr) return -1.0;
    if (area_mode == 0) return record->full_area;
    if (area_mode == 1) return 0.0;
    if (area_mode == 2) return record->tip_005_area;
    if (area_mode == 3) return record->tip_010_area;
    if (area_mode == 4) return record->tip_020_area;
    if (area_mode == 5) return multiplier*record->tip_010_area;
    return -1.0;
  }

  Config readAndValidateInput ();
  const Config& config ();
  bool enabled ();

  const AreaMatchState& areaMatchState ();
  const TerminalLedger& terminalLedger ();
  const BondedLedger& bondedLedger ();
  void resetRuntimeState ();
  void restoreRuntimeState (const AreaMatchState& area_match,
                            const TerminalLedger& terminal,
                            const BondedLedger& bonded);
  void bindAreaMatch (const AreaMatchState& area_match);
  void recordTerminalSnapshot (amrex::Real full_area,
                               amrex::Real tip_005_area,
                               amrex::Real tip_010_area,
                               amrex::Real tip_020_area,
                               amrex::Real effective_area,
                               std::uint64_t segments,
                               std::uint64_t live_terminal_origins);
  void recordBondedStep (const BondedStep& step);

  void initializeCanonicalBonds (BMXParticleContainer& particles);
  void prepareTerminalAreas (BMXParticleContainer& particles);
  const TerminalAreaRecord* terminalAreaDeviceData ();
  int terminalAreaRecordCount ();
  void applyBondedDTransport (BMXParticleContainer& particles,
                              amrex::Real outer_dt);
}

#endif
