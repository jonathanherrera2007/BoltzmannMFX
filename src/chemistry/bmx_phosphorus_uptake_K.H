//
// C10/P12 inward-only phosphorus uptake transaction.
//
#ifndef BMX_PHOSPHORUS_UPTAKE_K_H_
#define BMX_PHOSPHORUS_UPTAKE_K_H_

#include <AMReX_REAL.H>
#include <AMReX_GpuQualifiers.H>
#include <AMReX_Math.H>

#include <cstdint>
#include <limits>
#include <string>

namespace BMXPhosphorusUptake
{
  constexpr int schema_version = 2;
  constexpr const char* contract_id =
      "UDC-20260801-P12-UPTAKE-ONLY-V1";
  constexpr const char* contract_sha256 =
      "2094aed3c8ef21a257d2c597352793384d01a1efc3d72936d5c5108d308f8804";
  constexpr const char* numerical_contract_id =
      "USER-DIRECTED-20260801-P12-NUMERICAL-V2";
  constexpr const char* numerical_contract_sha256 =
      "43d64a8f4ec6c8c00379fc3d9605441cb900479fcdd8db9e78e6fc1edd28f81f";
  constexpr const char* authority_source_sha256 =
      "34e8414c09e6528fc86399ceb4902cb5fc6907d9562fcf7a78cb3a8e4e333066";
  constexpr const char* stage_id = "C10";
  constexpr const char* network_sha256 =
      "1f2294613b8a608b068d60269ff8eb29990210d3a1bc6d8142d4f840aa292702";
  constexpr const char* claim_boundary =
      "UPTAKE-ONLY/QUALITATIVE-DEPLETION/NOT-COMPLETE-PHOSPHORUS-BIOLOGY/NOT-CALIBRATED/NOT-PREDICTIVE";

  enum class AreaMode : int
  {
    full_exposed_surface = 0,
    zero = 1,
    tip_005 = 2,
    tip_010 = 3,
    tip_020 = 4,
    tip_010_area_matched = 5
  };

  struct Config
  {
    bool enabled = false;
    bool integrated_p15 = false;
    std::string bound_contract_id;
    std::string bound_contract_sha256;
    std::string bound_numerical_contract_id;
    std::string bound_numerical_contract_sha256;
    std::string bound_stage_id;
    std::string bound_network_sha256;
    amrex::Real j_max = 0.0;
    amrex::Real k_m = 0.0;
    AreaMode area_mode = AreaMode::full_exposed_surface;
    amrex::Real area_multiplier = 1.0;
    amrex::Real mesh_d_diffusivity = 0.0;
    amrex::Real solver_rtol = 0.0;
    amrex::Real solver_atol = 0.0;
  };

  struct CumulativeLedger
  {
    amrex::Real requested = 0.0;
    amrex::Real accepted = 0.0;
    amrex::Real rejected = 0.0;
    amrex::Real area_time = 0.0;
    amrex::Real minimum_donor_scale = 1.0;
    amrex::Real maximum_donor_eta = 0.0;
    std::uint64_t updates = 0;
    std::uint64_t positive_request_updates = 0;
    std::uint64_t zero_inventory_positive_request_updates = 0;
  };

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  bool finite (amrex::Real value) noexcept
  {
    return value == value &&
           value <= std::numeric_limits<amrex::Real>::max() &&
           value >= -std::numeric_limits<amrex::Real>::max();
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  amrex::Real surfaceFlux (amrex::Real mesh_d,
                           amrex::Real j_max,
                           amrex::Real k_m) noexcept
  {
    const amrex::Real donor = mesh_d > 0.0 ? mesh_d : 0.0;
    if (!(j_max > 0.0) || !(k_m > 0.0) || !(donor > 0.0)) return 0.0;
    return j_max * donor / (k_m + donor);
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  amrex::Real requestedAmount (amrex::Real mesh_d,
                               amrex::Real eligible_area,
                               amrex::Real dt,
                               amrex::Real j_max,
                               amrex::Real k_m) noexcept
  {
    if (!(eligible_area > 0.0) || !(dt > 0.0)) return 0.0;
    return eligible_area * surfaceFlux(mesh_d, j_max, k_m) * dt;
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  amrex::Real donorScale (amrex::Real available,
                          amrex::Real request_sum) noexcept
  {
    if (!(request_sum > 0.0)) return 0.0;
    const amrex::Real nonnegative = available > 0.0 ? available : 0.0;
    const amrex::Real ratio = nonnegative / request_sum;
    return ratio < 1.0 ? ratio : 1.0;
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  amrex::Real donorDemandRatio (amrex::Real available,
                                amrex::Real request_sum) noexcept
  {
    if (!(request_sum > 0.0) || !(available > 0.0)) return 0.0;
    return request_sum / available;
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  amrex::Real eligibleArea (amrex::Real stored_area,
                            amrex::Real segment_length,
                            bool is_live_tip,
                            AreaMode mode,
                            amrex::Real multiplier) noexcept
  {
    if (mode == AreaMode::zero) return 0.0;
    if (mode == AreaMode::full_exposed_surface) {
      return stored_area * multiplier;
    }
    amrex::Real terminal_distance = 0.0;
    if (mode == AreaMode::tip_005) terminal_distance = 0.005;
    if (mode == AreaMode::tip_010 ||
        mode == AreaMode::tip_010_area_matched) terminal_distance = 0.010;
    if (mode == AreaMode::tip_020) terminal_distance = 0.020;
    // The hash-bound P12 network is one 0.003-cm live-tip segment, so its
    // complete stored surface is inside every adopted terminal window.  Any
    // future topology needing graph distance, branch ties, or partial-segment
    // area fails closed until those presently unstated rules are frozen.
    if (!(terminal_distance > 0.0) || !is_live_tip ||
        !(segment_length >= 0.0) || segment_length > terminal_distance) {
      return -1.0;
    }
    return stored_area * multiplier;
  }

  Config readAndValidateInput ();
  const Config& config ();
  bool enabled ();
  const CumulativeLedger& cumulativeLedger ();
  void resetCumulativeLedger ();
  void restoreCumulativeLedger (const CumulativeLedger& ledger);
  void recordAcceptedStep (amrex::Real requested,
                           amrex::Real accepted,
                           amrex::Real eligible_area,
                           amrex::Real dt,
                           amrex::Real minimum_donor_scale,
                           amrex::Real maximum_donor_eta,
                           int zero_inventory_positive_request);
}

#endif
