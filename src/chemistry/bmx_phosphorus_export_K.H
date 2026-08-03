//
// C12/P14 finite-radius interface export and carbon-reward transaction.
//
#ifndef BMX_PHOSPHORUS_EXPORT_K_H_
#define BMX_PHOSPHORUS_EXPORT_K_H_

#include <bmx_pc_phosphorus.H>
#include <bmx_phosphorus_geometry_K.H>

#include <AMReX_GpuAtomic.H>
#include <AMReX_GpuQualifiers.H>
#include <AMReX_Math.H>
#include <AMReX_REAL.H>

#include <cmath>
#include <cstdint>
#include <limits>
#include <string>

namespace BMXPhosphorusExport
{
  constexpr int schema_version = 1;
  constexpr const char* contract_id = "bmx-p14-export-reward-v1";
  constexpr const char* contract_sha256 =
      "01a9d6eb7291cc8bc0c98f52afbf3c5ea1c86da4fd3f992a02665e283f81ff4e";
  constexpr const char* operator_fit_id = "bmx-p14-o09-fit-v1";
  constexpr const char* operator_fit_sha256 =
      "72193a1034d4148d167f059c347053d2206fa580cce9a156ec705304e7f378e7";
  constexpr const char* stage_id = "C12";
  constexpr const char* interface_fraction_id =
      "continuous-finite-radius-axial-contact-v1";
  constexpr const char* authority_classification =
      "USER_ADOPTED_PROVISIONAL_PENDING_MENTOR_OVERRIDE";
  constexpr amrex::Real reward_molar_multiplier =
      amrex::Real(967.0) / amrex::Real(125.0);
  static_assert(reward_molar_multiplier == amrex::Real(7.736),
                "P14 exact reward multiplier must be 967/125 = 7.736");

  struct Config
  {
    bool enabled = false;
    bool integrated_p15 = false;
    std::string bound_stage_id;
    amrex::Real k_export = 0.0;
  };

  struct CumulativeLedger
  {
    amrex::Real requested_p = 0.0;
    amrex::Real accepted_p = 0.0;
    amrex::Real rejected_p = 0.0;
    amrex::Real exported_p = 0.0;
    amrex::Real exchange_derived_a = 0.0;
    amrex::Real bootstrap_a_credit = 0.0;
    amrex::Real active_volume = 0.0;
    amrex::Real active_d_basis = 0.0;
    std::uint64_t updates = 0;
    std::uint64_t particles_evaluated = 0;
    std::uint64_t eligible_particles = 0;
    std::uint64_t true_crossings = 0;
    std::uint64_t solid_contacts = 0;
    std::uint64_t accepted_export_events = 0;
    std::uint64_t donor_capped_events = 0;
    std::uint64_t roundoff_clamps = 0;
    std::int64_t last_update_id = -1;
  };

  enum class StepStatus : int
  {
    ok = 0,
    nonfinite = 1,
    invalid_geometry = 2,
    invalid_parameter = 3,
    negative_amount = 4,
    fraction_out_of_range = 5,
    conservation_failure = 6
  };

  struct AmountTransaction
  {
    StepStatus status = StepStatus::ok;
    amrex::Real donor_before = 0.0;
    amrex::Real donor_after = 0.0;
    amrex::Real a_before = 0.0;
    amrex::Real a_after = 0.0;
    amrex::Real requested = 0.0;
    amrex::Real accepted = 0.0;
    amrex::Real rejected = 0.0;
    amrex::Real reward = 0.0;
    int donor_capped = 0;
  };

  struct StepResult
  {
    StepStatus status = StepStatus::ok;
    amrex::Real interface_fraction = 0.0;
    amrex::Real active_volume = 0.0;
    amrex::Real active_d_basis = 0.0;
    amrex::Real requested_p = 0.0;
    amrex::Real accepted_p = 0.0;
    amrex::Real rejected_p = 0.0;
    amrex::Real exported_p = 0.0;
    amrex::Real reward_a = 0.0;
    int evaluated = 0;
    int eligible = 0;
    int true_crossing = 0;
    int solid_contact = 0;
    int accepted_export_event = 0;
    int donor_capped_event = 0;
    int roundoff_clamps = 0;
  };

  struct DeviceAccumulator
  {
    amrex::Real interface_fraction_sum = 0.0;
    amrex::Real active_volume = 0.0;
    amrex::Real active_d_basis = 0.0;
    amrex::Real requested_p = 0.0;
    amrex::Real accepted_p = 0.0;
    amrex::Real rejected_p = 0.0;
    amrex::Real exported_p = 0.0;
    amrex::Real reward_a = 0.0;
    amrex::Long particles_evaluated = 0;
    amrex::Long eligible_particles = 0;
    amrex::Long true_crossings = 0;
    amrex::Long solid_contacts = 0;
    amrex::Long accepted_export_events = 0;
    amrex::Long donor_capped_events = 0;
    amrex::Long roundoff_clamps = 0;
    int maximum_status = 0;
  };

  struct ParameterInterval
  {
    amrex::Real lower = 0.0;
    amrex::Real upper = 0.0;
    int valid = 0;
  };

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  bool finite (amrex::Real value) noexcept
  {
    return BMXPhosphorus::finite(value);
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  amrex::Real smaller (amrex::Real left, amrex::Real right) noexcept
  {
    return left < right ? left : right;
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  amrex::Real larger (amrex::Real left, amrex::Real right) noexcept
  {
    return left > right ? left : right;
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  ParameterInterval rectangleInterval (amrex::Real ax,
                                       amrex::Real az,
                                       amrex::Real bx,
                                       amrex::Real bz,
                                       amrex::Real xlo,
                                       amrex::Real xhi,
                                       amrex::Real zlo,
                                       amrex::Real zhi) noexcept
  {
    ParameterInterval result;
    amrex::Real lower = 0.0;
    amrex::Real upper = 1.0;
    const amrex::Real origin[2] = {ax, az};
    const amrex::Real delta[2] = {bx-ax, bz-az};
    const amrex::Real bounds_lo[2] = {xlo, zlo};
    const amrex::Real bounds_hi[2] = {xhi, zhi};
    for (int axis = 0; axis < 2; ++axis) {
      if (delta[axis] == 0.0) {
        if (origin[axis] < bounds_lo[axis] ||
            origin[axis] > bounds_hi[axis]) return result;
        continue;
      }
      amrex::Real near_parameter =
          (bounds_lo[axis] - origin[axis]) / delta[axis];
      amrex::Real far_parameter =
          (bounds_hi[axis] - origin[axis]) / delta[axis];
      if (near_parameter > far_parameter) {
        const amrex::Real temporary = near_parameter;
        near_parameter = far_parameter;
        far_parameter = temporary;
      }
      lower = larger(lower, near_parameter);
      upper = smaller(upper, far_parameter);
      if (!(upper > lower)) return result;
    }
    result.lower = larger(0.0, lower);
    result.upper = smaller(1.0, upper);
    result.valid = result.upper > result.lower ? 1 : 0;
    return result;
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  ParameterInterval circleInterval (amrex::Real ax,
                                    amrex::Real az,
                                    amrex::Real bx,
                                    amrex::Real bz,
                                    amrex::Real cx,
                                    amrex::Real cz,
                                    amrex::Real radius) noexcept
  {
    ParameterInterval result;
    const amrex::Real dx = bx - ax;
    const amrex::Real dz = bz - az;
    const amrex::Real ox = ax - cx;
    const amrex::Real oz = az - cz;
    const amrex::Real quadratic = dx*dx + dz*dz;
    if (quadratic == 0.0) {
      if (ox*ox + oz*oz < radius*radius) {
        result.lower = 0.0;
        result.upper = 1.0;
        result.valid = 1;
      }
      return result;
    }
    const amrex::Real linear = 2.0 * (ox*dx + oz*dz);
    const amrex::Real constant = ox*ox + oz*oz - radius*radius;
    const amrex::Real discriminant =
        linear*linear - 4.0*quadratic*constant;
    // A zero discriminant is tangency and contributes no interval measure.
    if (!(discriminant > 0.0)) return result;
    const amrex::Real root = std::sqrt(discriminant);
    amrex::Real lower = (-linear - root) / (2.0*quadratic);
    amrex::Real upper = (-linear + root) / (2.0*quadratic);
    if (lower > upper) {
      const amrex::Real temporary = lower;
      lower = upper;
      upper = temporary;
    }
    result.lower = larger(0.0, lower);
    result.upper = smaller(1.0, upper);
    result.valid = result.upper > result.lower ? 1 : 0;
    return result;
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  bool intervalMidpointIsActive (
      const ParameterInterval& interval,
      amrex::Real ax,
      amrex::Real az,
      amrex::Real bx,
      amrex::Real bz,
      amrex::Real active_radius) noexcept
  {
    if (!interval.valid) return false;
    const amrex::Real parameter =
        0.5 * (interval.lower + interval.upper);
    const amrex::Real x = ax + parameter*(bx-ax);
    const amrex::Real z = az + parameter*(bz-az);
    return BMXPhosphorusGeometry::pointRectangleDistanceSquared2D(
               x, z,
               BMXPhosphorusGeometry::barrier_x_lo,
               BMXPhosphorusGeometry::barrier_x_hi,
               BMXPhosphorusGeometry::aperture_z_lo,
               BMXPhosphorusGeometry::aperture_z_hi) <
           active_radius*active_radius;
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  void appendActiveInterval (ParameterInterval candidate,
                             ParameterInterval* intervals,
                             int& count,
                             amrex::Real ax,
                             amrex::Real az,
                             amrex::Real bx,
                             amrex::Real bz,
                             amrex::Real active_radius) noexcept
  {
    if (candidate.valid &&
        intervalMidpointIsActive(candidate, ax, az, bx, bz,
                                 active_radius)) {
      intervals[count++] = candidate;
    }
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  amrex::Real continuousAxialFraction (
      const BMXPhosphorusGeometry::Capsule& original,
      const BMXPhosphorusGeometry::RuntimeConfig& geometry,
      BMXPhosphorusGeometry::CapsuleClassification* classification_out =
          nullptr) noexcept
  {
    const auto classification = BMXPhosphorusGeometry::classifyCapsule(
        original, true, geometry);
    if (classification_out != nullptr) {
      *classification_out = classification;
    }
    if (!classification.valid) return -1.0;
    if (classification.solid_contact || !classification.window_contact) {
      return 0.0;
    }

    const amrex::Real dx3 = original.second.x - original.first.x;
    const amrex::Real dy3 = original.second.y - original.first.y;
    const amrex::Real dz3 = original.second.z - original.first.z;
    const amrex::Real length_squared = dx3*dx3 + dy3*dy3 + dz3*dz3;
    if (!finite(length_squared) || !(length_squared > 0.0) ||
        !finite(original.radius) || !(original.radius > 0.0)) {
      return -1.0;
    }

    const amrex::Real tolerance =
        BMXPhosphorusGeometry::capsuleTolerance(geometry, original);
    const amrex::Real active_radius = original.radius - tolerance;
    if (!(active_radius > 0.0)) return 0.0;

    amrex::Real ax = original.first.x;
    amrex::Real az = original.first.z;
    amrex::Real bx = original.second.x;
    amrex::Real bz = original.second.z;
    const amrex::Real xlo = BMXPhosphorusGeometry::barrier_x_lo;
    const amrex::Real xhi = BMXPhosphorusGeometry::barrier_x_hi;
    const amrex::Real zlo = BMXPhosphorusGeometry::aperture_z_lo;
    const amrex::Real zhi = BMXPhosphorusGeometry::aperture_z_hi;
    ax = BMXPhosphorusGeometry::snapToBoundary(ax, xlo, tolerance);
    ax = BMXPhosphorusGeometry::snapToBoundary(ax, xhi, tolerance);
    az = BMXPhosphorusGeometry::snapToBoundary(az, zlo, tolerance);
    az = BMXPhosphorusGeometry::snapToBoundary(az, zhi, tolerance);
    bx = BMXPhosphorusGeometry::snapToBoundary(bx, xlo, tolerance);
    bx = BMXPhosphorusGeometry::snapToBoundary(bx, xhi, tolerance);
    bz = BMXPhosphorusGeometry::snapToBoundary(bz, zlo, tolerance);
    bz = BMXPhosphorusGeometry::snapToBoundary(bz, zhi, tolerance);

    ParameterInterval intervals[6]{};
    int count = 0;
    appendActiveInterval(
        rectangleInterval(ax, az, bx, bz,
                          xlo-active_radius, xhi+active_radius,
                          zlo, zhi),
        intervals, count, ax, az, bx, bz, active_radius);
    appendActiveInterval(
        rectangleInterval(ax, az, bx, bz,
                          xlo, xhi,
                          zlo-active_radius, zhi+active_radius),
        intervals, count, ax, az, bx, bz, active_radius);
    appendActiveInterval(circleInterval(ax, az, bx, bz, xlo, zlo,
                                        active_radius),
                         intervals, count, ax, az, bx, bz, active_radius);
    appendActiveInterval(circleInterval(ax, az, bx, bz, xlo, zhi,
                                        active_radius),
                         intervals, count, ax, az, bx, bz, active_radius);
    appendActiveInterval(circleInterval(ax, az, bx, bz, xhi, zlo,
                                        active_radius),
                         intervals, count, ax, az, bx, bz, active_radius);
    appendActiveInterval(circleInterval(ax, az, bx, bz, xhi, zhi,
                                        active_radius),
                         intervals, count, ax, az, bx, bz, active_radius);

    for (int left = 0; left < count; ++left) {
      for (int right = left + 1; right < count; ++right) {
        if (intervals[right].lower < intervals[left].lower) {
          const ParameterInterval temporary = intervals[left];
          intervals[left] = intervals[right];
          intervals[right] = temporary;
        }
      }
    }
    if (count == 0) return 0.0;

    constexpr amrex::Real parameter_tolerance =
        64.0 * std::numeric_limits<amrex::Real>::epsilon();
    amrex::Real measure = 0.0;
    amrex::Real current_lower = intervals[0].lower;
    amrex::Real current_upper = intervals[0].upper;
    for (int interval = 1; interval < count; ++interval) {
      if (intervals[interval].lower <=
          current_upper + parameter_tolerance) {
        current_upper = larger(current_upper, intervals[interval].upper);
      } else {
        measure += current_upper - current_lower;
        current_lower = intervals[interval].lower;
        current_upper = intervals[interval].upper;
      }
    }
    measure += current_upper - current_lower;
    return measure;
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  AmountTransaction transactAmounts (amrex::Real donor,
                                     amrex::Real a_amount,
                                     amrex::Real requested) noexcept
  {
    AmountTransaction result;
    result.donor_before = donor;
    result.a_before = a_amount;
    if (!finite(donor) || !finite(a_amount) || !finite(requested)) {
      result.status = StepStatus::nonfinite;
      return result;
    }
    if (donor < 0.0 || a_amount < 0.0 || requested < 0.0) {
      result.status = StepStatus::negative_amount;
      return result;
    }
    result.requested = requested;
    result.accepted = smaller(requested, donor);
    result.rejected = requested - result.accepted;
    result.reward = reward_molar_multiplier * result.accepted;
    result.donor_after = donor - result.accepted;
    result.a_after = a_amount + result.reward;
    result.donor_capped = requested > donor ? 1 : 0;
    if (!finite(result.accepted) || !finite(result.rejected) ||
        !finite(result.reward) || !finite(result.donor_after) ||
        !finite(result.a_after) || result.accepted < 0.0 ||
        result.rejected < 0.0 || result.donor_after < 0.0 ||
        result.a_after < a_amount) {
      result.status = StepStatus::conservation_failure;
      return result;
    }
    const amrex::Real p_scale =
        amrex::Math::abs(donor) + amrex::Math::abs(result.donor_after) +
        amrex::Math::abs(result.accepted);
    const amrex::Real request_scale =
        amrex::Math::abs(requested) + amrex::Math::abs(result.accepted) +
        amrex::Math::abs(result.rejected);
    if (amrex::Math::abs(
            donor - (result.donor_after + result.accepted)) >
            BMXPhosphorus::localTolerance(p_scale) ||
        amrex::Math::abs(
            requested - (result.accepted + result.rejected)) >
            BMXPhosphorus::localTolerance(request_scale) ||
        result.reward != reward_molar_multiplier * result.accepted) {
      result.status = StepStatus::conservation_failure;
    }
    return result;
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  StepResult apply (const amrex::Real* position,
                    amrex::Real* particle,
                    int* particle_integer,
                    amrex::Real dt,
                    amrex::Real k_export,
                    const BMXPhosphorusGeometry::RuntimeConfig& geometry)
      noexcept
  {
    StepResult result;
    if (particle_integer[intIdx::cell_type] != cellType::FUNGI) return result;
    result.evaluated = 1;
    if (!finite(dt) || !(dt > 0.0) || !finite(k_export) ||
        k_export < 0.0) {
      result.status = StepStatus::invalid_parameter;
      return result;
    }
    BMXPhosphorusGeometry::Pose pose;
    pose.center = {position[0], position[1], position[2]};
    pose.radius = particle[realIdx::radius];
    pose.length = particle[realIdx::c_length];
    pose.theta = particle[realIdx::theta];
    pose.phi = particle[realIdx::phi];
    const amrex::Real volume = particle[realIdx::vol];
    if (!BMXPhosphorusGeometry::validPose(pose) ||
        !(pose.radius > 0.0) || !(pose.length > 0.0) ||
        !finite(volume) || !(volume > 0.0)) {
      result.status = StepStatus::invalid_geometry;
      return result;
    }
    const auto capsule = BMXPhosphorusGeometry::makeCapsule(pose);
    BMXPhosphorusGeometry::CapsuleClassification classification;
    result.interface_fraction = continuousAxialFraction(
        capsule, geometry, &classification);
    if (!classification.valid || result.interface_fraction < 0.0) {
      result.status = StepStatus::invalid_geometry;
      return result;
    }
    result.solid_contact = classification.solid_contact;
    result.true_crossing = classification.true_crossing;
    result.eligible =
        classification.window_contact && !classification.solid_contact ? 1 : 0;
    if (!finite(result.interface_fraction) ||
        result.interface_fraction < 0.0 ||
        result.interface_fraction > 1.0) {
      result.status = StepStatus::fraction_out_of_range;
      return result;
    }

    amrex::Real* values = &particle[realIdx::first_data];
    const amrex::Real donor = values[BMXChemLayout::P_D] * volume;
    const amrex::Real a_amount = values[BMXChemLayout::A] * volume;
    if (!finite(donor) || !finite(a_amount)) {
      result.status = StepStatus::nonfinite;
      return result;
    }
    if (donor < 0.0 || a_amount < 0.0) {
      result.status = StepStatus::negative_amount;
      return result;
    }
    result.active_volume = result.interface_fraction * volume;
    result.active_d_basis = result.interface_fraction * donor;
    const amrex::Real export_fraction = 1.0 - std::exp(-k_export*dt);
    if (!finite(result.active_volume) || !finite(result.active_d_basis) ||
        !finite(export_fraction) || export_fraction < 0.0 ||
        export_fraction > 1.0) {
      result.status = StepStatus::invalid_parameter;
      return result;
    }
    const auto transaction = transactAmounts(
        donor, a_amount, result.active_d_basis * export_fraction);
    if (transaction.status != StepStatus::ok) {
      result.status = transaction.status;
      return result;
    }
    result.requested_p = transaction.requested;
    result.accepted_p = transaction.accepted;
    result.rejected_p = transaction.rejected;
    result.exported_p = transaction.accepted;
    result.reward_a = transaction.reward;
    result.accepted_export_event = transaction.accepted > 0.0 ? 1 : 0;
    result.donor_capped_event = transaction.donor_capped;

    // Commit only after every geometry, dimensional, cap, and conservation
    // check has succeeded.  These two writes are the particle-local atomic
    // D-debit/A-credit portion of O09.
    values[BMXChemLayout::P_D] = transaction.donor_after / volume;
    values[BMXChemLayout::A] = transaction.a_after / volume;
    if (!finite(values[BMXChemLayout::P_D]) ||
        !finite(values[BMXChemLayout::A]) ||
        values[BMXChemLayout::P_D] < 0.0 ||
        values[BMXChemLayout::A] < 0.0) {
      result.status = StepStatus::conservation_failure;
      return result;
    }
    return result;
  }

  AMREX_GPU_DEVICE AMREX_FORCE_INLINE
  void accumulate (const StepResult& step,
                   DeviceAccumulator* accumulator) noexcept
  {
    amrex::Gpu::Atomic::AddNoRet(
        &accumulator->interface_fraction_sum, step.interface_fraction);
    amrex::Gpu::Atomic::AddNoRet(
        &accumulator->active_volume, step.active_volume);
    amrex::Gpu::Atomic::AddNoRet(
        &accumulator->active_d_basis, step.active_d_basis);
    amrex::Gpu::Atomic::AddNoRet(
        &accumulator->requested_p, step.requested_p);
    amrex::Gpu::Atomic::AddNoRet(
        &accumulator->accepted_p, step.accepted_p);
    amrex::Gpu::Atomic::AddNoRet(
        &accumulator->rejected_p, step.rejected_p);
    amrex::Gpu::Atomic::AddNoRet(
        &accumulator->exported_p, step.exported_p);
    amrex::Gpu::Atomic::AddNoRet(
        &accumulator->reward_a, step.reward_a);
    amrex::Gpu::Atomic::AddNoRet(
        &accumulator->particles_evaluated,
        static_cast<amrex::Long>(step.evaluated));
    amrex::Gpu::Atomic::AddNoRet(
        &accumulator->eligible_particles,
        static_cast<amrex::Long>(step.eligible));
    amrex::Gpu::Atomic::AddNoRet(
        &accumulator->true_crossings,
        static_cast<amrex::Long>(step.true_crossing));
    amrex::Gpu::Atomic::AddNoRet(
        &accumulator->solid_contacts,
        static_cast<amrex::Long>(step.solid_contact));
    amrex::Gpu::Atomic::AddNoRet(
        &accumulator->accepted_export_events,
        static_cast<amrex::Long>(step.accepted_export_event));
    amrex::Gpu::Atomic::AddNoRet(
        &accumulator->donor_capped_events,
        static_cast<amrex::Long>(step.donor_capped_event));
    amrex::Gpu::Atomic::AddNoRet(
        &accumulator->roundoff_clamps,
        static_cast<amrex::Long>(step.roundoff_clamps));
    amrex::Gpu::Atomic::Max(
        &accumulator->maximum_status, static_cast<int>(step.status));
  }

  Config readAndValidateInput ();
  const Config& config ();
  bool enabled ();
  const CumulativeLedger& cumulativeLedger ();
  void resetCumulativeLedger ();
  void restoreCumulativeLedger (const CumulativeLedger& ledger);
  void requireUpdateAvailable (int update_id);
  void recordStep (int update_id,
                   const StepResult& local,
                   std::uint64_t particles_evaluated,
                   std::uint64_t eligible_particles,
                   std::uint64_t true_crossings,
                   std::uint64_t solid_contacts,
                   std::uint64_t accepted_export_events,
                   std::uint64_t donor_capped_events,
                   std::uint64_t roundoff_clamps);
}

#endif
