//
// C11/P13 local D/E reaction and Liebig-limited fungal growth transaction.
//
#ifndef BMX_PHOSPHORUS_REACTIONS_K_H_
#define BMX_PHOSPHORUS_REACTIONS_K_H_

#include <bmx_pc_phosphorus.H>

#include <AMReX_GpuAtomic.H>
#include <AMReX_GpuQualifiers.H>
#include <AMReX_Math.H>
#include <AMReX_REAL.H>

#include <cstdint>
#include <cmath>
#include <string>

namespace BMXPhosphorusReactions
{
  constexpr int schema_version = 1;
  constexpr const char* contract_id = "bmx-p13-reaction-liebig-v1";
  constexpr const char* contract_sha256 =
      "06f575a09b56178d74f809003fec532d6d3d509b972e62c29da21754cab0d26d";
  constexpr const char* operator_fit_id = "bmx-p13-o02-fit-v1";
  constexpr const char* operator_fit_sha256 =
      "ea6e8dc2ca3f69fe2f366801c9df8ec9832b58f399d605c88d91527ff2098407";
  constexpr const char* authority_source_sha256 =
      "283eace4f34e0a3d6961d49db2ab2c75ac6e384a9077a7044313a20f7bd4bc93";
  constexpr const char* stage_id = "C11";
  constexpr const char* authority_classification =
      "USER_ADOPTED_PROVISIONAL_PENDING_MENTOR_OVERRIDE";

  struct Config
  {
    bool enabled = false;
    bool integrated_p15 = false;
    std::string bound_stage_id;
    bool reactions_enabled = false;
    bool growth_enabled = false;
    amrex::Real k_de = 0.0;
    amrex::Real k_ed = 0.0;
    amrex::Real q_p = 0.0;
    amrex::Real k_gp_over_k_gb = 0.0;
  };

  struct CumulativeLedger
  {
    amrex::Real reaction_forward = 0.0;
    amrex::Real reaction_reverse = 0.0;
    amrex::Real carbon_supported_growth = 0.0;
    amrex::Real phosphorus_supported_growth = 0.0;
    amrex::Real requested_growth = 0.0;
    amrex::Real accepted_growth = 0.0;
    amrex::Real rejected_growth = 0.0;
    amrex::Real b_debit = 0.0;
    amrex::Real e_debit = 0.0;
    amrex::Real structuralized_p = 0.0;
    std::uint64_t updates = 0;
    std::uint64_t particles_evaluated = 0;
    std::uint64_t accepted_growth_events = 0;
    std::uint64_t roundoff_clamps = 0;
  };

  enum class StepStatus : int
  {
    ok = 0,
    nonfinite = 1,
    negative_amount = 2,
    invalid_parameter = 3,
    invalid_geometry = 4,
    conservation_failure = 5
  };

  struct StepResult
  {
    StepStatus status = StepStatus::ok;
    amrex::Real reaction_forward = 0.0;
    amrex::Real reaction_reverse = 0.0;
    amrex::Real carbon_supported_growth = 0.0;
    amrex::Real phosphorus_supported_growth = 0.0;
    amrex::Real requested_growth = 0.0;
    amrex::Real accepted_growth = 0.0;
    amrex::Real rejected_growth = 0.0;
    amrex::Real b_debit = 0.0;
    amrex::Real e_debit = 0.0;
    amrex::Real structuralized_p = 0.0;
    int evaluated = 0;
    int accepted_growth_event = 0;
    int roundoff_clamps = 0;
  };

  struct DeviceAccumulator
  {
    amrex::Real reaction_forward = 0.0;
    amrex::Real reaction_reverse = 0.0;
    amrex::Real carbon_supported_growth = 0.0;
    amrex::Real phosphorus_supported_growth = 0.0;
    amrex::Real requested_growth = 0.0;
    amrex::Real accepted_growth = 0.0;
    amrex::Real rejected_growth = 0.0;
    amrex::Real b_debit = 0.0;
    amrex::Real e_debit = 0.0;
    amrex::Real structuralized_p = 0.0;
    amrex::Long particles_evaluated = 0;
    amrex::Long accepted_growth_events = 0;
    amrex::Long roundoff_clamps = 0;
    int maximum_status = 0;
  };

  AMREX_GPU_DEVICE AMREX_FORCE_INLINE
  void accumulate (const StepResult& step,
                   DeviceAccumulator* accumulator) noexcept
  {
    amrex::Gpu::Atomic::AddNoRet(
        &accumulator->reaction_forward, step.reaction_forward);
    amrex::Gpu::Atomic::AddNoRet(
        &accumulator->reaction_reverse, step.reaction_reverse);
    amrex::Gpu::Atomic::AddNoRet(
        &accumulator->carbon_supported_growth,
        step.carbon_supported_growth);
    amrex::Gpu::Atomic::AddNoRet(
        &accumulator->phosphorus_supported_growth,
        step.phosphorus_supported_growth);
    amrex::Gpu::Atomic::AddNoRet(
        &accumulator->requested_growth, step.requested_growth);
    amrex::Gpu::Atomic::AddNoRet(
        &accumulator->accepted_growth, step.accepted_growth);
    amrex::Gpu::Atomic::AddNoRet(
        &accumulator->rejected_growth, step.rejected_growth);
    amrex::Gpu::Atomic::AddNoRet(&accumulator->b_debit, step.b_debit);
    amrex::Gpu::Atomic::AddNoRet(&accumulator->e_debit, step.e_debit);
    amrex::Gpu::Atomic::AddNoRet(
        &accumulator->structuralized_p, step.structuralized_p);
    amrex::Gpu::Atomic::AddNoRet(
        &accumulator->particles_evaluated,
        static_cast<amrex::Long>(step.evaluated));
    amrex::Gpu::Atomic::AddNoRet(
        &accumulator->accepted_growth_events,
        static_cast<amrex::Long>(step.accepted_growth_event));
    amrex::Gpu::Atomic::AddNoRet(
        &accumulator->roundoff_clamps,
        static_cast<amrex::Long>(step.roundoff_clamps));
    amrex::Gpu::Atomic::Max(
        &accumulator->maximum_status, static_cast<int>(step.status));
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  amrex::Real smaller (amrex::Real first, amrex::Real second) noexcept
  {
    return first < second ? first : second;
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  bool finite (amrex::Real value) noexcept
  {
    return BMXPhosphorus::finite(value);
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  bool clampRoundoffNegative (amrex::Real& amount,
                              amrex::Real scale,
                              int& clamp_count,
                              amrex::Real& correction) noexcept
  {
    if (amount >= 0.0) return true;
    if (amrex::Math::abs(amount) <=
        BMXPhosphorus::integratedTolerance(scale)) {
      correction += -amount;
      amount = 0.0;
      ++clamp_count;
      return true;
    }
    return false;
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  StepResult apply (amrex::Real* particle,
                    int* particle_integer,
                    amrex::Real dt,
                    bool reactions_enabled,
                    bool growth_enabled,
                    amrex::Real k_de,
                    amrex::Real k_ed,
                    amrex::Real q_p,
                    amrex::Real k_gp_over_k_gb,
                    amrex::Real k_gb,
                    amrex::Real k_vb,
                    amrex::Real radius_max,
                    amrex::Real length_max) noexcept
  {
    StepResult result;
    if (!reactions_enabled && !growth_enabled) return result;
    if (particle_integer[intIdx::cell_type] != cellType::FUNGI) return result;
    result.evaluated = 1;

    const amrex::Real old_volume = particle[realIdx::vol];
    const amrex::Real old_radius = particle[realIdx::radius];
    const amrex::Real old_length = particle[realIdx::c_length];
    const amrex::Real old_area = particle[realIdx::area];
    if (!finite(dt) || !(dt > 0.0) || !finite(old_volume) ||
        !(old_volume > 0.0) || !finite(old_radius) ||
        !(old_radius > 0.0) || !finite(old_length) ||
        !(old_length >= 0.0) || !finite(old_area) ||
        !(old_area >= 0.0)) {
      result.status = StepStatus::invalid_geometry;
      return result;
    }

    amrex::Real* values = &particle[realIdx::first_data];
    amrex::Real amount[NUM_PARTICLE_CHEM_COMPONENTS]{};
    for (int component = 0;
         component < NUM_PARTICLE_CHEM_COMPONENTS; ++component) {
      if (!finite(values[component])) {
        result.status = StepStatus::nonfinite;
        return result;
      }
      amount[component] = values[component] * old_volume;
      if (!finite(amount[component])) {
        result.status = StepStatus::nonfinite;
        return result;
      }
    }

    amrex::Real p_scale =
        amrex::Math::abs(amount[BMXChemLayout::P_D]) +
        amrex::Math::abs(amount[BMXChemLayout::P_E]) +
        amrex::Math::abs(amount[BMXChemLayout::P_F]);
    amrex::Real p_roundoff_correction = 0.0;
    if (!clampRoundoffNegative(amount[BMXChemLayout::P_D], p_scale,
                               result.roundoff_clamps,
                               p_roundoff_correction) ||
        !clampRoundoffNegative(amount[BMXChemLayout::P_E], p_scale,
                               result.roundoff_clamps,
                               p_roundoff_correction) ||
        !clampRoundoffNegative(amount[BMXChemLayout::P_F], p_scale,
                               result.roundoff_clamps,
                               p_roundoff_correction)) {
      result.status = StepStatus::negative_amount;
      return result;
    }

    if (!finite(k_de) || !finite(k_ed) || k_de < 0.0 || k_ed < 0.0) {
      result.status = StepStatus::invalid_parameter;
      return result;
    }
    if (reactions_enabled) {
      result.reaction_forward = smaller(
          k_de * amount[BMXChemLayout::P_D] * dt,
          amount[BMXChemLayout::P_D]);
      result.reaction_reverse = smaller(
          k_ed * amount[BMXChemLayout::P_E] * dt,
          amount[BMXChemLayout::P_E]);
      if (!finite(result.reaction_forward) ||
          !finite(result.reaction_reverse) ||
          result.reaction_forward < 0.0 ||
          result.reaction_reverse < 0.0) {
        result.status = StepStatus::nonfinite;
        return result;
      }
      amount[BMXChemLayout::P_D] +=
          result.reaction_reverse - result.reaction_forward;
      amount[BMXChemLayout::P_E] +=
          result.reaction_forward - result.reaction_reverse;
    }

    p_scale += amrex::Math::abs(result.reaction_forward) +
               amrex::Math::abs(result.reaction_reverse);
    if (!clampRoundoffNegative(amount[BMXChemLayout::P_D], p_scale,
                               result.roundoff_clamps,
                               p_roundoff_correction) ||
        !clampRoundoffNegative(amount[BMXChemLayout::P_E], p_scale,
                               result.roundoff_clamps,
                               p_roundoff_correction)) {
      result.status = StepStatus::negative_amount;
      return result;
    }

    amrex::Real accepted_volume = 0.0;
    if (growth_enabled) {
      if (!finite(q_p) || !(q_p > 0.0) ||
          !finite(k_gp_over_k_gb) || !(k_gp_over_k_gb > 0.0) ||
          !finite(k_gb) || !(k_gb > 0.0) ||
          !finite(k_vb) || !(k_vb > 0.0) ||
          !finite(radius_max) || !(radius_max > 0.0) ||
          !finite(length_max) || !(length_max > 0.0)) {
        result.status = StepStatus::invalid_parameter;
        return result;
      }
      amrex::Real b_scale = amrex::Math::abs(amount[1]);
      amrex::Real b_roundoff_correction = 0.0;
      if (!clampRoundoffNegative(amount[1], b_scale,
                                 result.roundoff_clamps,
                                 b_roundoff_correction)) {
        result.status = StepStatus::negative_amount;
        return result;
      }
      const amrex::Real q_b = k_gb / k_vb;
      const amrex::Real k_gp = k_gp_over_k_gb * k_gb;
      result.carbon_supported_growth = dt * k_vb * amount[1];
      result.phosphorus_supported_growth =
          dt * (k_gp / q_p) * amount[BMXChemLayout::P_E];
      result.requested_growth = smaller(result.carbon_supported_growth,
                                        result.phosphorus_supported_growth);
      accepted_volume = result.requested_growth;
      accepted_volume = smaller(accepted_volume, amount[1] / q_b);
      accepted_volume = smaller(
          accepted_volume, amount[BMXChemLayout::P_E] / q_p);

      const bool is_tip =
          particle_integer[intIdx::position] == siteLocation::TIP;
      const bool native_geometry_eligible =
          is_tip ? !(old_radius >= radius_max && old_length >= length_max)
                 : old_radius < radius_max;
      if (!native_geometry_eligible) accepted_volume = 0.0;
      if (!finite(result.carbon_supported_growth) ||
          !finite(result.phosphorus_supported_growth) ||
          !finite(result.requested_growth) || !finite(accepted_volume) ||
          result.carbon_supported_growth < 0.0 ||
          result.phosphorus_supported_growth < 0.0 ||
          result.requested_growth < 0.0 || accepted_volume < 0.0) {
        result.status = StepStatus::nonfinite;
        return result;
      }

      result.accepted_growth = accepted_volume;
      result.rejected_growth = result.requested_growth - accepted_volume;
      result.b_debit = q_b * accepted_volume;
      result.e_debit = q_p * accepted_volume;
      result.structuralized_p = result.e_debit;
      if (!finite(result.rejected_growth) || !finite(result.b_debit) ||
          !finite(result.e_debit) || result.rejected_growth < 0.0 ||
          result.b_debit < 0.0 || result.e_debit < 0.0 ||
          result.b_debit > amount[1] ||
          result.e_debit > amount[BMXChemLayout::P_E]) {
        result.status = StepStatus::conservation_failure;
        return result;
      }
      amount[1] -= result.b_debit;
      amount[BMXChemLayout::P_E] -= result.e_debit;
    }

    amrex::Real new_volume = old_volume + accepted_volume;
    amrex::Real new_radius = old_radius;
    amrex::Real new_length = old_length;
    amrex::Real new_area = old_area;
    if (accepted_volume > 0.0) {
      constexpr amrex::Real pi =
          3.141592653589793238462643383279502884;
      const bool is_tip =
          particle_integer[intIdx::position] == siteLocation::TIP;
      if (is_tip) {
        if (old_radius < radius_max && old_length < length_max) {
          const amrex::Real scale =
              pow(new_volume / old_volume, amrex::Real(1.0 / 3.0));
          new_radius = scale * old_radius;
          new_length = scale * old_length;
        } else if (old_radius < radius_max) {
          const amrex::Real scale = sqrt(new_volume / old_volume);
          new_radius = scale * old_radius;
        } else {
          new_length = (new_volume / old_volume) * old_length;
        }
        new_area = particle_integer[intIdx::n_bnds] == 0
                       ? 2.0 * pi * new_radius *
                             (new_radius + new_length)
                       : pi * new_radius *
                             (new_radius + 2.0 * new_length);
      } else {
        const amrex::Real scale = sqrt(new_volume / old_volume);
        new_radius = scale * old_radius;
        new_area = 2.0 * pi * new_radius * new_length;
      }
      if (!finite(new_volume) || !(new_volume > old_volume) ||
          !finite(new_radius) || !(new_radius > 0.0) ||
          !finite(new_length) || !(new_length >= 0.0) ||
          !finite(new_area) || !(new_area >= 0.0)) {
        result.status = StepStatus::invalid_geometry;
        return result;
      }
      result.accepted_growth_event = 1;
    }

    const amrex::Real p_before =
        values[BMXChemLayout::P_D] * old_volume +
        values[BMXChemLayout::P_E] * old_volume +
        values[BMXChemLayout::P_F] * old_volume;
    const amrex::Real p_after = amount[BMXChemLayout::P_D] +
                                amount[BMXChemLayout::P_E] +
                                amount[BMXChemLayout::P_F] +
                                result.structuralized_p;
    const amrex::Real conservation_scale =
        amrex::Math::abs(p_before) + amrex::Math::abs(p_after);
    if (!finite(p_before) || !finite(p_after) ||
        !finite(p_roundoff_correction) ||
        amrex::Math::abs((p_after - p_before) -
                         p_roundoff_correction) >
            BMXPhosphorus::localTolerance(conservation_scale)) {
      result.status = StepStatus::conservation_failure;
      return result;
    }

    for (int component = 0;
         component < NUM_PARTICLE_CHEM_COMPONENTS; ++component) {
      values[component] = amount[component] / new_volume;
      if (component < BMXChemLayout::P_D) {
        values[NUM_PARTICLE_CHEM_COMPONENTS + component] =
            values[component];
      }
    }
    // P working buffers remain canonical zero at every P10 audit boundary.
    values[NUM_PARTICLE_CHEM_COMPONENTS + BMXChemLayout::P_D] = 0.0;
    values[NUM_PARTICLE_CHEM_COMPONENTS + BMXChemLayout::P_E] = 0.0;
    values[NUM_PARTICLE_CHEM_COMPONENTS + BMXChemLayout::P_F] = 0.0;
    particle[realIdx::vol] = new_volume;
    particle[realIdx::radius] = new_radius;
    particle[realIdx::c_length] = new_length;
    particle[realIdx::area] = new_area;
    particle[realIdx::dvdt] = accepted_volume / dt;
    particle[realIdx::dadt] = (new_area - old_area) / dt;
    return result;
  }

  Config readAndValidateInput ();
  const Config& config ();
  bool enabled ();
  const CumulativeLedger& cumulativeLedger ();
  void resetCumulativeLedger ();
  void restoreCumulativeLedger (const CumulativeLedger& ledger);
  void recordStep (const StepResult& local,
                   std::uint64_t particles_evaluated,
                   std::uint64_t accepted_growth_events,
                   std::uint64_t roundoff_clamps);
}

#endif
