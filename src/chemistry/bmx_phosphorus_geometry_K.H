//
//     Copyright (c) 2013 Battelle Memorial Institute
//     Licensed under modified BSD License. A copy of this license can be found
//     in the LICENSE file in the top level directory of this distribution.
//
#ifndef BMX_PHOSPHORUS_GEOMETRY_K_H_
#define BMX_PHOSPHORUS_GEOMETRY_K_H_

#include <AMReX_GpuQualifiers.H>
#include <AMReX_REAL.H>

#include <cmath>
#include <limits>

namespace BMXPhosphorusGeometry
{
  using amrex::Real;

  constexpr int schema_version = 1;
  constexpr const char* contract_id =
      "bmx-p11-split-plate-geometry-v1";
  constexpr const char* contract_sha256 =
      "6a4329f013c857c664a11d669747845006a6c0c9d34f568625b6939d1462acba";
  constexpr const char* stage_id = "local_quasi_2d_interface";

  constexpr Real barrier_x_lo = Real(-0.05);
  constexpr Real divider_x = Real(0.0);
  constexpr Real barrier_x_hi = Real(0.05);
  constexpr Real frame_z_lo = Real(0.0);
  constexpr Real aperture_z_lo = Real(0.8);
  constexpr Real aperture_z_hi = Real(1.0);
  constexpr Real frame_z_hi = Real(1.2);
  constexpr Real periodic_y_lo = Real(0.0);
  constexpr Real periodic_y_hi = Real(0.1);
  constexpr Real tolerance_multiplier = Real(64.0);

  enum class XRegion : int
  {
    invalid = -1,
    host = 0,
    barrier = 1,
    fungus = 2
  };

  enum class ZRegion : int
  {
    invalid = -1,
    outside_frame = 0,
    frame = 1,
    aperture = 2
  };

  struct RuntimeConfig
  {
    int enabled = 0;
    int mesh_pd_component = -1;
    int mesh_pf_component = -1;
    Real prob_lo[3] = {Real(0.0), Real(0.0), Real(0.0)};
    Real prob_hi[3] = {Real(0.0), Real(0.0), Real(0.0)};
    Real base_tolerance = Real(0.0);
  };

  struct Point
  {
    Real x = Real(0.0);
    Real y = Real(0.0);
    Real z = Real(0.0);
  };

  struct Capsule
  {
    Point first;
    Point second;
    Real radius = Real(0.0);
  };

  struct Pose
  {
    Point center;
    Real length = Real(0.0);
    Real radius = Real(0.0);
    Real theta = Real(0.0);
    Real phi = Real(0.0);
  };

  struct CapsuleClassification
  {
    int valid = 1;
    int solid_contact = 0;
    int solid_penetration = 0;
    int window_contact = 0;
    int true_crossing = 0;
  };

  struct MotionConstraintResult
  {
    int valid = 1;
    int attempted_penetration = 0;
    int outer_contact = 0;
    int solid_contact = 0;
    int projected = 0;
    int tangential_motion = 0;
    int rotation_rejected = 0;
  };

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  Real absReal (Real value) noexcept
  {
    return value < Real(0.0) ? -value : value;
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  bool finiteReal (Real value) noexcept
  {
    constexpr Real largest_finite = std::numeric_limits<Real>::max();
    return value == value && value <= largest_finite &&
           value >= -largest_finite;
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  bool validPoint (const Point& point) noexcept
  {
    return finiteReal(point.x) && finiteReal(point.y) &&
           finiteReal(point.z);
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  bool validCapsule (const Capsule& capsule) noexcept
  {
    return validPoint(capsule.first) && validPoint(capsule.second) &&
           finiteReal(capsule.radius) && capsule.radius >= Real(0.0);
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  bool validPose (const Pose& pose) noexcept
  {
    return validPoint(pose.center) && finiteReal(pose.length) &&
           pose.length >= Real(0.0) && finiteReal(pose.radius) &&
           pose.radius >= Real(0.0) && finiteReal(pose.theta) &&
           finiteReal(pose.phi);
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  Real minReal (Real left, Real right) noexcept
  {
    return left < right ? left : right;
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  Real maxReal (Real left, Real right) noexcept
  {
    return left > right ? left : right;
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  Real clampReal (Real value, Real lower, Real upper) noexcept
  {
    return maxReal(lower, minReal(value, upper));
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  Real snapToBoundary (Real value, Real boundary, Real tolerance) noexcept
  {
    return absReal(value - boundary) <= tolerance ? boundary : value;
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  Real coordinateScale (const RuntimeConfig& config) noexcept
  {
    Real scale = Real(1.0);
    for (int direction = 0; direction < 3; ++direction) {
      scale = maxReal(scale, absReal(config.prob_lo[direction]));
      scale = maxReal(scale, absReal(config.prob_hi[direction]));
      scale = maxReal(scale,
                      absReal(config.prob_hi[direction] -
                              config.prob_lo[direction]));
    }
    return scale;
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  Real capsuleTolerance (const RuntimeConfig& config,
                         const Capsule& capsule) noexcept
  {
    Real scale = coordinateScale(config);
    scale = maxReal(scale, absReal(capsule.radius));
    const Real dx = capsule.second.x - capsule.first.x;
    const Real dy = capsule.second.y - capsule.first.y;
    const Real dz = capsule.second.z - capsule.first.z;
    scale = maxReal(scale, std::sqrt(dx*dx + dy*dy + dz*dz));
    scale = maxReal(scale, absReal(capsule.first.x));
    scale = maxReal(scale, absReal(capsule.first.y));
    scale = maxReal(scale, absReal(capsule.first.z));
    scale = maxReal(scale, absReal(capsule.second.x));
    scale = maxReal(scale, absReal(capsule.second.y));
    scale = maxReal(scale, absReal(capsule.second.z));
    const Real local = tolerance_multiplier *
                       Real(2.220446049250313080847263336181640625e-16) *
                       scale;
    return maxReal(config.base_tolerance, local);
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  XRegion classifyX (Real x, const RuntimeConfig& config) noexcept
  {
    if (!finiteReal(x)) return XRegion::invalid;
    const Real tolerance = config.base_tolerance;
    x = snapToBoundary(x, barrier_x_lo, tolerance);
    x = snapToBoundary(x, barrier_x_hi, tolerance);
    if (x < barrier_x_lo) return XRegion::host;
    if (x < barrier_x_hi) return XRegion::barrier;
    return XRegion::fungus;
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  ZRegion classifyZ (Real z, const RuntimeConfig& config) noexcept
  {
    if (!finiteReal(z)) return ZRegion::invalid;
    const Real tolerance = config.base_tolerance;
    z = snapToBoundary(z, frame_z_lo, tolerance);
    z = snapToBoundary(z, aperture_z_lo, tolerance);
    z = snapToBoundary(z, aperture_z_hi, tolerance);
    z = snapToBoundary(z, frame_z_hi, tolerance);
    if (z < frame_z_lo || z >= frame_z_hi) {
      return ZRegion::outside_frame;
    }
    if (z >= aperture_z_lo && z < aperture_z_hi) {
      return ZRegion::aperture;
    }
    return ZRegion::frame;
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  Real canonicalPeriodicY (Real y, const RuntimeConfig& config) noexcept
  {
    const Real width = periodic_y_hi - periodic_y_lo;
    const Real tolerance = config.base_tolerance;
    Real shifted = y - periodic_y_lo;
    shifted -= std::floor(shifted / width) * width;
    Real canonical = periodic_y_lo + shifted;
    canonical = snapToBoundary(canonical, periodic_y_lo, tolerance);
    canonical = snapToBoundary(canonical, periodic_y_hi, tolerance);
    if (canonical >= periodic_y_hi) canonical = periodic_y_lo;
    return canonical;
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  Capsule makeCapsule (const Pose& pose) noexcept
  {
    const Real st = std::sin(pose.theta);
    const Real nx = st * std::cos(pose.phi);
    const Real ny = st * std::sin(pose.phi);
    const Real nz = std::cos(pose.theta);
    const Real half_length = Real(0.5) * pose.length;
    Capsule capsule;
    capsule.first = {pose.center.x - half_length*nx,
                     pose.center.y - half_length*ny,
                     pose.center.z - half_length*nz};
    capsule.second = {pose.center.x + half_length*nx,
                      pose.center.y + half_length*ny,
                      pose.center.z + half_length*nz};
    capsule.radius = pose.radius;
    return capsule;
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  Real pointSegmentDistanceSquared2D (Real px, Real pz,
                                      Real ax, Real az,
                                      Real bx, Real bz) noexcept
  {
    const Real dx = bx - ax;
    const Real dz = bz - az;
    const Real denominator = dx*dx + dz*dz;
    Real parameter = Real(0.0);
    if (denominator > Real(0.0)) {
      parameter = ((px-ax)*dx + (pz-az)*dz) / denominator;
      parameter = clampReal(parameter, Real(0.0), Real(1.0));
    }
    const Real qx = ax + parameter*dx;
    const Real qz = az + parameter*dz;
    const Real ex = px - qx;
    const Real ez = pz - qz;
    return ex*ex + ez*ez;
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  Real pointRectangleDistanceSquared2D (Real px, Real pz,
                                        Real xlo, Real xhi,
                                        Real zlo, Real zhi) noexcept
  {
    const Real qx = clampReal(px, xlo, xhi);
    const Real qz = clampReal(pz, zlo, zhi);
    const Real dx = px - qx;
    const Real dz = pz - qz;
    return dx*dx + dz*dz;
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  bool segmentIntersectsRectangle2D (Real ax, Real az,
                                     Real bx, Real bz,
                                     Real xlo, Real xhi,
                                     Real zlo, Real zhi) noexcept
  {
    Real lower = Real(0.0);
    Real upper = Real(1.0);
    const Real origin[2] = {ax, az};
    const Real delta[2] = {bx-ax, bz-az};
    const Real box_lo[2] = {xlo, zlo};
    const Real box_hi[2] = {xhi, zhi};
    for (int axis = 0; axis < 2; ++axis) {
      if (delta[axis] == Real(0.0)) {
        if (origin[axis] < box_lo[axis] ||
            origin[axis] > box_hi[axis]) return false;
        continue;
      }
      Real near_parameter = (box_lo[axis] - origin[axis]) / delta[axis];
      Real far_parameter = (box_hi[axis] - origin[axis]) / delta[axis];
      if (near_parameter > far_parameter) {
        const Real temporary = near_parameter;
        near_parameter = far_parameter;
        far_parameter = temporary;
      }
      lower = maxReal(lower, near_parameter);
      upper = minReal(upper, far_parameter);
      if (lower > upper) return false;
    }
    return true;
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  Real segmentRectangleDistanceSquared2D (const Capsule& capsule,
                                          Real xlo, Real xhi,
                                          Real zlo, Real zhi) noexcept
  {
    const Real ax = capsule.first.x;
    const Real az = capsule.first.z;
    const Real bx = capsule.second.x;
    const Real bz = capsule.second.z;
    if (segmentIntersectsRectangle2D(ax, az, bx, bz,
                                     xlo, xhi, zlo, zhi)) {
      return Real(0.0);
    }
    Real result = pointRectangleDistanceSquared2D(ax, az,
                                                  xlo, xhi, zlo, zhi);
    result = minReal(result,
                     pointRectangleDistanceSquared2D(bx, bz,
                                                     xlo, xhi, zlo, zhi));
    result = minReal(result,
                     pointSegmentDistanceSquared2D(xlo, zlo, ax, az, bx, bz));
    result = minReal(result,
                     pointSegmentDistanceSquared2D(xlo, zhi, ax, az, bx, bz));
    result = minReal(result,
                     pointSegmentDistanceSquared2D(xhi, zlo, ax, az, bx, bz));
    result = minReal(result,
                     pointSegmentDistanceSquared2D(xhi, zhi, ax, az, bx, bz));
    return result;
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  Real solidDistanceSquared (const Capsule& capsule,
                             bool fungal_segment) noexcept
  {
    if (!fungal_segment) {
      return segmentRectangleDistanceSquared2D(
          capsule, barrier_x_lo, barrier_x_hi,
          frame_z_lo, frame_z_hi);
    }
    const Real lower = segmentRectangleDistanceSquared2D(
        capsule, barrier_x_lo, barrier_x_hi,
        frame_z_lo, aperture_z_lo);
    const Real upper = segmentRectangleDistanceSquared2D(
        capsule, barrier_x_lo, barrier_x_hi,
        aperture_z_hi, frame_z_hi);
    return minReal(lower, upper);
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  bool capsuleContactsSolid (const Capsule& capsule,
                             bool fungal_segment,
                             const RuntimeConfig& config) noexcept
  {
    const Real tolerance = capsuleTolerance(config, capsule);
    const Real threshold = capsule.radius + tolerance;
    return solidDistanceSquared(capsule, fungal_segment) <=
           threshold*threshold;
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  bool capsulePenetratesSolid (const Capsule& capsule,
                               bool fungal_segment,
                               const RuntimeConfig& config) noexcept
  {
    const Real tolerance = capsuleTolerance(config, capsule);
    const Real distance_squared = solidDistanceSquared(capsule,
                                                       fungal_segment);
    if (capsule.radius <= tolerance) {
      return distance_squared <= tolerance*tolerance;
    }
    const Real threshold = capsule.radius - tolerance;
    return distance_squared < threshold*threshold;
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  CapsuleClassification classifyCapsule (const Capsule& capsule,
                                          bool fungal_segment,
                                          const RuntimeConfig& config) noexcept
  {
    CapsuleClassification classification;
    if (!config.enabled) return classification;
    if (!validCapsule(capsule)) {
      classification.valid = 0;
      return classification;
    }
    classification.solid_contact =
        capsuleContactsSolid(capsule, fungal_segment, config) ? 1 : 0;
    classification.solid_penetration =
        capsulePenetratesSolid(capsule, fungal_segment, config) ? 1 : 0;
    if (!fungal_segment || classification.solid_contact) {
      return classification;
    }
    const Real tolerance = capsuleTolerance(config, capsule);
    const Real window_distance = segmentRectangleDistanceSquared2D(
        capsule, barrier_x_lo, barrier_x_hi,
        aperture_z_lo, aperture_z_hi);
    const Real window_threshold = capsule.radius + tolerance;
    classification.window_contact =
        window_distance <= window_threshold*window_threshold ? 1 : 0;
    if (!classification.window_contact) return classification;

    Real minimum_x = minReal(capsule.first.x, capsule.second.x) -
                     capsule.radius;
    Real maximum_x = maxReal(capsule.first.x, capsule.second.x) +
                     capsule.radius;
    minimum_x = snapToBoundary(minimum_x, barrier_x_lo, tolerance);
    maximum_x = snapToBoundary(maximum_x, barrier_x_hi, tolerance);
    const bool reaches_host = minimum_x < barrier_x_lo;
    const bool reaches_fungus = maximum_x >= barrier_x_hi;
    classification.true_crossing = reaches_host && reaches_fungus ? 1 : 0;
    return classification;
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  bool isDividerFace (Real physical_x,
                      const RuntimeConfig& config) noexcept
  {
    return config.enabled &&
           absReal(physical_x - divider_x) <= config.base_tolerance;
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  bool isMaskedMeshComponent (int component,
                              const RuntimeConfig& config) noexcept
  {
    return config.enabled &&
           (component == config.mesh_pd_component ||
            component == config.mesh_pf_component);
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  Real maskedFaceCoefficient (Real coefficient,
                              int direction,
                              int component,
                              Real physical_face_coordinate,
                              const RuntimeConfig& config) noexcept
  {
    if (direction == 0 &&
        isMaskedMeshComponent(component, config) &&
        isDividerFace(physical_face_coordinate, config)) {
      return Real(0.0);
    }
    return coefficient;
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  bool capsuleOutsideAxis (const Capsule& capsule,
                           int direction,
                           Real lower,
                           Real upper,
                           Real tolerance) noexcept
  {
    const Real first = direction == 0 ? capsule.first.x : capsule.first.z;
    const Real second = direction == 0 ? capsule.second.x : capsule.second.z;
    const Real minimum = minReal(first, second) - capsule.radius;
    const Real maximum = maxReal(first, second) + capsule.radius;
    return minimum < lower - tolerance || maximum > upper + tolerance;
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  bool projectOuterAxis (Pose& pose,
                         Real* velocity,
                         int direction,
                         Real lower,
                         Real upper,
                         const RuntimeConfig& config) noexcept
  {
    Capsule capsule = makeCapsule(pose);
    const Real tolerance = capsuleTolerance(config, capsule);
    const Real first = direction == 0 ? capsule.first.x : capsule.first.z;
    const Real second = direction == 0 ? capsule.second.x : capsule.second.z;
    Real minimum = minReal(first, second) - capsule.radius;
    Real maximum = maxReal(first, second) + capsule.radius;
    bool contacted = false;
    const bool lower_penetration = minimum < lower - tolerance;
    const bool lower_outward_contact =
        minimum <= lower + tolerance && velocity[direction] < Real(0.0);
    if (lower_penetration || lower_outward_contact) {
      const Real shift = lower - minimum;
      if (direction == 0) pose.center.x += shift;
      else pose.center.z += shift;
      if (velocity[direction] < Real(0.0)) velocity[direction] = Real(0.0);
      contacted = true;
    }
    capsule = makeCapsule(pose);
    const Real adjusted_first =
        direction == 0 ? capsule.first.x : capsule.first.z;
    const Real adjusted_second =
        direction == 0 ? capsule.second.x : capsule.second.z;
    minimum = minReal(adjusted_first, adjusted_second) - capsule.radius;
    maximum = maxReal(adjusted_first, adjusted_second) + capsule.radius;
    const bool upper_penetration = maximum > upper + tolerance;
    const bool upper_outward_contact =
        maximum >= upper - tolerance && velocity[direction] > Real(0.0);
    if (upper_penetration || upper_outward_contact) {
      const Real shift = upper - maximum;
      if (direction == 0) pose.center.x += shift;
      else pose.center.z += shift;
      if (velocity[direction] > Real(0.0)) velocity[direction] = Real(0.0);
      contacted = true;
    }
    return contacted;
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  bool sweptCapsulePenetratesSolid (const Pose& old_pose,
                                    const Pose& proposed_pose,
                                    bool fungal_segment,
                                    const RuntimeConfig& config) noexcept
  {
    const Capsule old_capsule = makeCapsule(old_pose);
    const Capsule proposed_capsule = makeCapsule(proposed_pose);
    if (capsulePenetratesSolid(old_capsule, fungal_segment, config) ||
        capsulePenetratesSolid(proposed_capsule, fungal_segment, config)) {
      return true;
    }
    Capsule trajectory;
    trajectory.radius = maxReal(old_capsule.radius, proposed_capsule.radius);
    trajectory.first = old_capsule.first;
    trajectory.second = proposed_capsule.first;
    if (capsulePenetratesSolid(trajectory, fungal_segment, config)) return true;
    trajectory.first = old_capsule.second;
    trajectory.second = proposed_capsule.second;
    if (capsulePenetratesSolid(trajectory, fungal_segment, config)) return true;
    return false;
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  bool sweptCapsuleContactsSolid (const Pose& old_pose,
                                  const Pose& proposed_pose,
                                  bool fungal_segment,
                                  const RuntimeConfig& config) noexcept
  {
    const Capsule old_capsule = makeCapsule(old_pose);
    const Capsule proposed_capsule = makeCapsule(proposed_pose);
    if (capsuleContactsSolid(old_capsule, fungal_segment, config) ||
        capsuleContactsSolid(proposed_capsule, fungal_segment, config)) {
      return true;
    }
    Capsule trajectory;
    trajectory.radius = maxReal(old_capsule.radius, proposed_capsule.radius);
    trajectory.first = old_capsule.first;
    trajectory.second = proposed_capsule.first;
    if (capsuleContactsSolid(trajectory, fungal_segment, config)) return true;
    trajectory.first = old_capsule.second;
    trajectory.second = proposed_capsule.second;
    if (capsuleContactsSolid(trajectory, fungal_segment, config)) return true;
    return false;
  }

  AMREX_GPU_HOST_DEVICE AMREX_FORCE_INLINE
  MotionConstraintResult constrainMotion (const Pose& old_pose,
                                           Pose& proposed_pose,
                                           bool fungal_segment,
                                           Real* velocity,
                                           Real* angular_velocity,
                                           const RuntimeConfig& config) noexcept
  {
    MotionConstraintResult result;
    if (!config.enabled) return result;
    if (!validPose(old_pose) || !validPose(proposed_pose) ||
        !finiteReal(velocity[0]) || !finiteReal(velocity[1]) ||
        !finiteReal(velocity[2]) || !finiteReal(angular_velocity[0]) ||
        !finiteReal(angular_velocity[1]) ||
        !finiteReal(angular_velocity[2])) {
      result.valid = 0;
      return result;
    }

    int constrained_x = 0;
    int constrained_z = 0;

    const Capsule old_capsule = makeCapsule(old_pose);
    const Real old_tolerance = capsuleTolerance(config, old_capsule);
    if (capsuleOutsideAxis(old_capsule, 0, config.prob_lo[0],
                           config.prob_hi[0], old_tolerance) ||
        capsuleOutsideAxis(old_capsule, 2, config.prob_lo[2],
                           config.prob_hi[2], old_tolerance) ||
        capsulePenetratesSolid(old_capsule, fungal_segment, config)) {
      result.valid = 0;
      return result;
    }

    // Resolve the internal fungus-side support first.  Outer constraints are
    // then applied in deterministic x-before-z order below, so a simultaneous
    // frame/domain-corner proposal retains motion tangent to every active
    // normal without depending on the order in which walls were discovered.
    const bool old_solid_contact =
        capsuleContactsSolid(old_capsule, fungal_segment, config);
    const bool first_solid_contact =
        !old_solid_contact &&
        sweptCapsuleContactsSolid(old_pose, proposed_pose,
                                  fungal_segment, config);
    if (first_solid_contact ||
        sweptCapsulePenetratesSolid(old_pose, proposed_pose,
                                    fungal_segment, config)) {
      result.attempted_penetration = 1;
      result.solid_contact = 1;
      result.projected = 1;
      constrained_x = 1;
      Capsule proposed_capsule = makeCapsule(proposed_pose);
      Real minimum_x = minReal(proposed_capsule.first.x,
                               proposed_capsule.second.x) -
                       proposed_capsule.radius;
      proposed_pose.center.x += barrier_x_hi - minimum_x;
      if (velocity[0] < Real(0.0)) velocity[0] = Real(0.0);

      proposed_capsule = makeCapsule(proposed_pose);
      if (capsulePenetratesSolid(proposed_capsule,
                                 fungal_segment, config)) {
        proposed_pose.theta = old_pose.theta;
        proposed_pose.phi = old_pose.phi;
        proposed_capsule = makeCapsule(proposed_pose);
        minimum_x = minReal(proposed_capsule.first.x,
                            proposed_capsule.second.x) -
                    proposed_capsule.radius;
        proposed_pose.center.x += barrier_x_hi - minimum_x;
        angular_velocity[0] = Real(0.0);
        angular_velocity[1] = Real(0.0);
        angular_velocity[2] = Real(0.0);
        result.rotation_rejected = 1;
      }
    }

    if (projectOuterAxis(proposed_pose, velocity, 0,
                         config.prob_lo[0], config.prob_hi[0], config)) {
      result.attempted_penetration = 1;
      result.outer_contact = 1;
      result.projected = 1;
      constrained_x = 1;
    }
    if (projectOuterAxis(proposed_pose, velocity, 2,
                         config.prob_lo[2], config.prob_hi[2], config)) {
      result.attempted_penetration = 1;
      result.outer_contact = 1;
      result.projected = 1;
      constrained_z = 1;
    }

    if (result.projected) {
      const Real dx = proposed_pose.center.x - old_pose.center.x;
      const Real dy = proposed_pose.center.y - old_pose.center.y;
      const Real dz = proposed_pose.center.z - old_pose.center.z;
      const Real tolerance = capsuleTolerance(config,
                                                makeCapsule(proposed_pose));
      result.tangential_motion =
          ((!constrained_x &&
            (absReal(dx) > tolerance ||
             absReal(velocity[0]) > tolerance)) ||
           absReal(dy) > tolerance ||
           absReal(velocity[1]) > tolerance ||
           (!constrained_z &&
            (absReal(dz) > tolerance ||
             absReal(velocity[2]) > tolerance))) ? 1 : 0;
    }

    const Capsule final_capsule = makeCapsule(proposed_pose);
    const Real final_tolerance = capsuleTolerance(config, final_capsule);
    if (capsuleOutsideAxis(final_capsule, 0, config.prob_lo[0],
                           config.prob_hi[0], final_tolerance) ||
        capsuleOutsideAxis(final_capsule, 2, config.prob_lo[2],
                           config.prob_hi[2], final_tolerance) ||
        capsulePenetratesSolid(final_capsule, fungal_segment, config)) {
      result.valid = 0;
    }
    return result;
  }
}

#ifndef BMX_P11_GEOMETRY_PURE_TEST

#include <AMReX.H>
#include <AMReX_Geometry.H>
#include <AMReX_ParmParse.H>

#include <bmx_chem_layout.H>

#include <algorithm>
#include <iomanip>
#include <limits>
#include <sstream>
#include <string>
#include <vector>

namespace BMXPhosphorusGeometry
{
  struct InputBinding
  {
    bool enabled = false;
    int version = 0;
    std::string contract = "DISABLED";
    std::string stage = "DISABLED";
  };

  [[noreturn]] inline void rejectConfiguration (const std::string& reason)
  {
    amrex::Abort("P11 geometry configuration rejected: " + reason);
  }

  inline InputBinding readInputBinding ()
  {
    amrex::ParmParse parameters("p11_geometry");
    int enabled = 0;
    parameters.query("enabled", enabled);
    if (enabled != 0 && enabled != 1) {
      rejectConfiguration("p11_geometry.enabled must be 0 or 1");
    }
    InputBinding binding;
    binding.enabled = enabled == 1;
    if (!binding.enabled) return binding;

    parameters.get("schema_version", binding.version);
    parameters.get("contract_id", binding.contract);
    parameters.get("stage", binding.stage);
    if (binding.version != schema_version) {
      rejectConfiguration("schema_version mismatch");
    }
    if (binding.contract != contract_id) {
      rejectConfiguration("contract_id mismatch");
    }
    if (binding.stage != stage_id) {
      rejectConfiguration("stage must be local_quasi_2d_interface");
    }
    return binding;
  }

  inline bool nearlyEqual (Real left, Real right, Real tolerance)
  {
    return std::abs(left - right) <= tolerance;
  }

  inline void requireAlignedFace (const amrex::Geometry& geometry,
                                  int direction,
                                  Real coordinate,
                                  Real tolerance,
                                  const char* label)
  {
    const Real lower = geometry.ProbLo(direction);
    const Real spacing = geometry.CellSize(direction);
    if (!std::isfinite(spacing) || spacing <= Real(0.0)) {
      rejectConfiguration(std::string(label) + " has invalid cell spacing");
    }
    const Real index = (coordinate - lower) / spacing;
    const Real nearest_index = std::round(index);
    const Real reconstructed = lower + nearest_index * spacing;
    if (std::abs(reconstructed - coordinate) > tolerance) {
      std::ostringstream message;
      message << std::setprecision(17) << label
              << " is not grid-face aligned: coordinate=" << coordinate
              << " reconstructed=" << reconstructed
              << " dx=" << spacing;
      rejectConfiguration(message.str());
    }
  }

  inline RuntimeConfig loadAndValidate (
      const amrex::Geometry& geometry,
      const std::vector<std::string>& mesh_names)
  {
    RuntimeConfig config;
    for (int direction = 0; direction < 3; ++direction) {
      config.prob_lo[direction] = geometry.ProbLo(direction);
      config.prob_hi[direction] = geometry.ProbHi(direction);
    }
    Real scale = Real(1.0);
    for (int direction = 0; direction < 3; ++direction) {
      scale = std::max(scale, std::abs(config.prob_lo[direction]));
      scale = std::max(scale, std::abs(config.prob_hi[direction]));
      scale = std::max(scale,
                       std::abs(config.prob_hi[direction] -
                                config.prob_lo[direction]));
    }
    config.base_tolerance = tolerance_multiplier *
                            std::numeric_limits<double>::epsilon() * scale;

    const auto binding = readInputBinding();
    if (!binding.enabled) return config;
    for (int direction = 0; direction < 3; ++direction) {
      if (!std::isfinite(config.prob_lo[direction]) ||
          !std::isfinite(config.prob_hi[direction]) ||
          config.prob_hi[direction] <= config.prob_lo[direction]) {
        rejectConfiguration("domain bounds must be finite and strictly ordered");
      }
    }
    if (sizeof(Real) != sizeof(double)) {
      rejectConfiguration("P11 v1 requires double-precision amrex::Real");
    }
    config.enabled = 1;

    std::string layout_error;
    const auto mode = BMXChemLayout::classifyMeshSpecies(mesh_names,
                                                         &layout_error);
    if (mode != BMXChemLayout::MeshMode::enabled) {
      rejectConfiguration(
          "enabled P11 geometry requires the exact three-state mesh layout" +
          (layout_error.empty() ? std::string() : ": " + layout_error));
    }
    config.mesh_pd_component = BMXChemLayout::particleToMesh(
        BMXChemLayout::P_D, mode);
    config.mesh_pf_component = BMXChemLayout::particleToMesh(
        BMXChemLayout::P_F, mode);
    if (config.mesh_pd_component < 0 || config.mesh_pf_component < 0 ||
        mesh_names[config.mesh_pd_component] != "P_D" ||
        mesh_names[config.mesh_pf_component] != "P_F") {
      rejectConfiguration("P_D/P_F mesh component binding failed");
    }

    if (geometry.Coord() != 0) {
      rejectConfiguration("coordinate system must be Cartesian");
    }
    if (geometry.isPeriodic(0) || !geometry.isPeriodic(1) ||
        geometry.isPeriodic(2)) {
      rejectConfiguration("periodicity must be nonperiodic x/z and periodic y");
    }

    const Real tolerance = config.base_tolerance;
    const bool x_domain =
        (nearlyEqual(config.prob_lo[0], Real(-1.0), tolerance) &&
         nearlyEqual(config.prob_hi[0], Real(1.0), tolerance)) ||
        (nearlyEqual(config.prob_lo[0], Real(-0.5), tolerance) &&
         nearlyEqual(config.prob_hi[0], Real(0.5), tolerance)) ||
        (nearlyEqual(config.prob_lo[0], Real(-2.0), tolerance) &&
         nearlyEqual(config.prob_hi[0], Real(2.0), tolerance));
    if (!x_domain) {
      rejectConfiguration("x domain is not an approved central/sensitivity extent");
    }
    if (!nearlyEqual(config.prob_lo[1], periodic_y_lo, tolerance) ||
        !nearlyEqual(config.prob_hi[1], periodic_y_hi, tolerance)) {
      rejectConfiguration("y domain must be [0,0.1) cm");
    }
    if (!nearlyEqual(config.prob_lo[2], frame_z_lo, tolerance) ||
        !nearlyEqual(config.prob_hi[2], frame_z_hi, tolerance)) {
      rejectConfiguration("z domain must be [0,1.2) cm");
    }

    requireAlignedFace(geometry, 0, barrier_x_lo, tolerance,
                       "barrier x lower face");
    requireAlignedFace(geometry, 0, divider_x, tolerance,
                       "divider x face");
    requireAlignedFace(geometry, 0, barrier_x_hi, tolerance,
                       "barrier x upper face");
    requireAlignedFace(geometry, 2, frame_z_lo, tolerance,
                       "frame z lower face");
    requireAlignedFace(geometry, 2, aperture_z_lo, tolerance,
                       "aperture z lower face");
    requireAlignedFace(geometry, 2, aperture_z_hi, tolerance,
                       "aperture z upper face");
    requireAlignedFace(geometry, 2, frame_z_hi, tolerance,
                       "frame z upper face");
    return config;
  }
}

#endif
#endif
