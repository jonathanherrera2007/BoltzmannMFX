#define BMX_P11_GEOMETRY_PURE_TEST
#include <bmx_phosphorus_geometry_K.H>

#include <cmath>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>

namespace G = BMXPhosphorusGeometry;

namespace
{
  int checks = 0;

  void require (bool condition, const std::string& message)
  {
    ++checks;
    if (!condition) throw std::runtime_error(message);
  }

  G::RuntimeConfig config (amrex::Real xlo = -1.0,
                           amrex::Real xhi = 1.0)
  {
    G::RuntimeConfig result;
    result.enabled = 1;
    result.mesh_pd_component = 5;
    result.mesh_pf_component = 6;
    result.prob_lo[0] = xlo;
    result.prob_hi[0] = xhi;
    result.prob_lo[1] = 0.0;
    result.prob_hi[1] = 0.1;
    result.prob_lo[2] = 0.0;
    result.prob_hi[2] = 1.2;
    result.base_tolerance =
        64.0 * std::numeric_limits<double>::epsilon() *
        std::max(1.0, std::max(std::abs(xlo), std::abs(xhi)));
    return result;
  }

  G::Capsule xCapsule (amrex::Real x1, amrex::Real x2,
                       amrex::Real z, amrex::Real radius)
  {
    G::Capsule result;
    result.first = {x1, 0.05, z};
    result.second = {x2, 0.05, z};
    result.radius = radius;
    return result;
  }

  G::Pose xPose (amrex::Real x, amrex::Real z,
                 amrex::Real length, amrex::Real radius)
  {
    G::Pose result;
    result.center = {x, 0.05, z};
    result.length = length;
    result.radius = radius;
    result.theta = 0.5 * 3.141592653589793238462643383279502884;
    result.phi = 0.0;
    return result;
  }
}

int main ()
{
  try {
    const auto primary = config();
    const auto tolerance = primary.base_tolerance;

    require(G::classifyX(-0.0501, primary) == G::XRegion::host,
            "strict host interior");
    require(G::classifyX(-0.05, primary) == G::XRegion::barrier,
            "barrier lower face is included");
    require(G::classifyX(0.0, primary) == G::XRegion::barrier,
            "divider lies in barrier");
    require(G::classifyX(0.05, primary) == G::XRegion::fungus,
            "barrier upper face is excluded");
    require(G::classifyX(-0.05 - 0.5*tolerance, primary) ==
                G::XRegion::barrier,
            "near-face value snaps before half-open classification");
    require(G::classifyX(std::numeric_limits<double>::quiet_NaN(), primary) ==
                G::XRegion::invalid,
            "nonfinite x classification fails closed");

    require(G::classifyZ(0.0, primary) == G::ZRegion::frame,
            "frame lower face included");
    require(G::classifyZ(0.8, primary) == G::ZRegion::aperture,
            "aperture lower face included");
    require(G::classifyZ(1.0, primary) == G::ZRegion::frame,
            "aperture upper face excluded");
    require(G::classifyZ(1.2, primary) == G::ZRegion::outside_frame,
            "frame upper face excluded");
    require(G::classifyZ(std::numeric_limits<double>::infinity(), primary) ==
                G::ZRegion::invalid,
            "nonfinite z classification fails closed");

    require(G::canonicalPeriodicY(0.0, primary) == 0.0,
            "periodic lower endpoint");
    require(G::canonicalPeriodicY(0.1, primary) == 0.0,
            "periodic upper endpoint wraps");
    require(std::abs(G::canonicalPeriodicY(0.11, primary) - 0.01) < 1e-15,
            "positive periodic image");
    require(std::abs(G::canonicalPeriodicY(-0.01, primary) - 0.09) < 1e-15,
            "negative periodic image");

    const auto crossing = G::classifyCapsule(
        xCapsule(-0.2, 0.2, 0.9, 0.01), true, primary);
    require(crossing.window_contact == 1 && crossing.true_crossing == 1,
            "interior orthogonal finite-radius crossing");
    require(crossing.solid_contact == 0 && crossing.solid_penetration == 0,
            "interior crossing clears solid frame");

    const auto reverse_crossing = G::classifyCapsule(
        xCapsule(0.2, -0.2, 0.9, 0.01), true, primary);
    require(reverse_crossing.window_contact == crossing.window_contact &&
                reverse_crossing.true_crossing == crossing.true_crossing,
            "both crossing directions agree");

    const auto fungus_touch = G::classifyCapsule(
        xCapsule(0.06, 0.2, 0.9, 0.01), true, primary);
    require(fungus_touch.window_contact == 1 &&
                fungus_touch.true_crossing == 0,
            "finite radius touches window without crossing");
    const auto fungus_miss = G::classifyCapsule(
        xCapsule(0.061, 0.2, 0.9, 0.01), true, primary);
    require(fungus_miss.window_contact == 0,
            "positive-clearance finite-radius miss");

    const auto lower_edge = G::classifyCapsule(
        xCapsule(-0.2, 0.2, 0.81, 0.01), true, primary);
    require(lower_edge.solid_contact == 1 &&
                lower_edge.window_contact == 0,
            "solid frame wins exact lower-edge tangency");
    const auto upper_edge = G::classifyCapsule(
        xCapsule(-0.2, 0.2, 0.99, 0.01), true, primary);
    require(upper_edge.solid_contact == 1 &&
                upper_edge.window_contact == 0,
            "solid frame wins exact upper-edge tangency");
    const auto lower_corner = G::classifyCapsule(
        xCapsule(0.04, 0.06, 0.81, 0.01), true, primary);
    require(lower_corner.solid_contact == 1 &&
                lower_corner.window_contact == 0,
            "solid frame wins simultaneous x/z corner tangency");
    const auto frame_hit = G::classifyCapsule(
        xCapsule(-0.2, 0.2, 0.5, 0.01), true, primary);
    require(frame_hit.solid_penetration == 1 &&
                frame_hit.window_contact == 0,
            "solid frame penetration is not a window event");

    G::Capsule oblique;
    oblique.first = {-0.2, 0.02, 0.86};
    oblique.second = {0.2, 0.08, 0.94};
    oblique.radius = 0.01;
    const auto oblique_result = G::classifyCapsule(oblique, true, primary);
    require(oblique_result.window_contact == 1 &&
                oblique_result.true_crossing == 1,
            "oblique crossing uses physical capsule geometry");

    const auto nonfungal = G::classifyCapsule(
        xCapsule(-0.2, 0.2, 0.9, 0.01), false, primary);
    require(nonfungal.solid_penetration == 1 &&
                nonfungal.window_contact == 0,
            "fungus-only aperture rejects nonfungal particle");
    auto invalid_capsule = xCapsule(-0.2, 0.2, 0.9, 0.01);
    invalid_capsule.first.x = std::numeric_limits<double>::quiet_NaN();
    require(G::classifyCapsule(invalid_capsule, true, primary).valid == 0,
            "nonfinite capsule classification fails closed");

    for (int repeat = 0; repeat < 100; ++repeat) {
      const auto repeated = G::classifyCapsule(oblique, true, primary);
      require(repeated.window_contact == oblique_result.window_contact &&
                  repeated.true_crossing == oblique_result.true_crossing,
              "repeated classification is deterministic");
    }

    for (const auto extent : {config(-0.5, 0.5), config(-1.0, 1.0),
                              config(-2.0, 2.0)}) {
      const auto invariant = G::classifyCapsule(oblique, true, extent);
      require(invariant.window_contact == oblique_result.window_contact &&
                  invariant.true_crossing == oblique_result.true_crossing,
              "local result invariant to approved x-domain extent");
    }

    require(G::maskedFaceCoefficient(3.25, 0, 5, 0.0, primary) == 0.0,
            "P_D divider coefficient is literal zero");
    require(G::maskedFaceCoefficient(4.5, 0, 6, 0.0, primary) == 0.0,
            "P_F divider coefficient is literal zero");
    for (int legacy = 0; legacy < 5; ++legacy) {
      require(G::maskedFaceCoefficient(2.0 + legacy, 0, legacy, 0.0,
                                       primary) == 2.0 + legacy,
              "legacy species coefficient unchanged");
    }
    require(G::maskedFaceCoefficient(7.0, 0, 5, 0.1, primary) == 7.0,
            "nondivider P face unchanged");
    auto disabled = primary;
    disabled.enabled = 0;
    require(G::maskedFaceCoefficient(7.0, 0, 5, 0.0, disabled) == 7.0,
            "feature-off coefficient unchanged");

    const double forward_flux =
        -G::maskedFaceCoefficient(1.0, 0, 5, 0.0, primary) *
        (9.0 - 1.0) / 0.05;
    const double reverse_flux =
        -G::maskedFaceCoefficient(1.0, 0, 5, 0.0, primary) *
        (1.0 - 9.0) / 0.05;
    require(forward_flux == 0.0 && reverse_flux == 0.0,
            "paired-cell P transfer is zero in both gradient directions");

    {
      const auto old_pose = xPose(0.3, 0.5, 0.1, 0.01);
      auto proposed = xPose(-0.3, 0.5, 0.1, 0.01);
      double velocity[3] = {-0.6, 0.25, 0.1};
      double angular[3] = {0.0, 0.0, 0.0};
      const auto result = G::constrainMotion(
          old_pose, proposed, true, velocity, angular, primary);
      const auto projected = G::makeCapsule(proposed);
      const double minimum_x =
          std::min(projected.first.x, projected.second.x) - projected.radius;
      require(result.valid == 1 && result.solid_contact == 1 &&
                  result.projected == 1 &&
                  result.attempted_penetration == 1,
              "solid collision projects rather than reflecting or deleting");
      require(std::abs(minimum_x - G::barrier_x_hi) <= 2*tolerance,
              "solid collision projects to fungus-side support plane");
      require(velocity[0] == 0.0 && velocity[1] == 0.25 &&
                  velocity[2] == 0.1,
              "normal motion removed and tangential motion retained");
      require(result.tangential_motion == 1,
              "projected collision records retained tangential motion");
    }

    {
      const auto old_pose = xPose(0.2, 0.5, 0.1, 0.01);
      auto proposed = xPose(0.11, 0.5, 0.1, 0.01);
      double velocity[3] = {-0.09, 0.0, 0.0};
      double angular[3] = {0.0, 0.0, 0.0};
      const auto result = G::constrainMotion(
          old_pose, proposed, true, velocity, angular, primary);
      require(result.valid == 1 && result.solid_contact == 1 &&
                  result.projected == 1 && velocity[0] == 0.0,
              "first exact solid contact removes inward normal motion");
    }

    {
      const auto old_pose = xPose(0.3, 0.9, 0.1, 0.01);
      auto proposed = xPose(-0.3, 0.9, 0.1, 0.01);
      double velocity[3] = {-0.6, 0.1, 0.0};
      double angular[3] = {0.0, 0.0, 0.0};
      const auto result = G::constrainMotion(
          old_pose, proposed, true, velocity, angular, primary);
      require(result.valid == 1 && result.solid_contact == 0 &&
                  result.projected == 0 &&
                  result.attempted_penetration == 0 &&
                  result.tangential_motion == 0 && proposed.center.x == -0.3,
              "fungal capsule passes through clear aperture");
    }

    {
      const auto old_pose = xPose(0.3, 0.9, 0.0, 0.01);
      auto proposed = xPose(-0.3, 0.9, 0.0, 0.01);
      double velocity[3] = {-0.6, 0.1, 0.0};
      double angular[3] = {0.0, 0.0, 0.0};
      const auto result = G::constrainMotion(
          old_pose, proposed, false, velocity, angular, primary);
      require(result.valid == 1 && result.solid_contact == 1 &&
                  result.projected == 1,
              "nonfungal particle cannot use aperture");
    }

    {
      const auto old_pose = xPose(0.8, 0.9, 0.1, 0.01);
      auto proposed = xPose(1.1, 0.9, 0.1, 0.01);
      double velocity[3] = {0.3, 0.2, -0.1};
      double angular[3] = {0.0, 0.0, 0.0};
      const auto result = G::constrainMotion(
          old_pose, proposed, true, velocity, angular, primary);
      const auto projected = G::makeCapsule(proposed);
      const double maximum_x =
          std::max(projected.first.x, projected.second.x) + projected.radius;
      require(result.valid == 1 && result.outer_contact == 1 &&
                  result.attempted_penetration == 1 &&
                  std::abs(maximum_x - primary.prob_hi[0]) <= 2*tolerance,
              "outer x hard wall projects capsule in-domain");
      require(velocity[0] == 0.0 && velocity[1] == 0.2 &&
                  velocity[2] == -0.1,
              "outer wall preserves tangential translation");
    }

    {
      const auto old_pose = xPose(0.8, 0.9, 0.1, 0.01);
      auto proposed = xPose(0.94, 0.9, 0.1, 0.01);
      double velocity[3] = {0.14, 0.0, 0.0};
      double angular[3] = {0.0, 0.0, 0.0};
      const auto result = G::constrainMotion(
          old_pose, proposed, true, velocity, angular, primary);
      require(result.valid == 1 && result.outer_contact == 1 &&
                  result.projected == 1 && velocity[0] == 0.0,
              "first exact outer-wall contact removes outward normal motion");
    }

    {
      auto old_pose = xPose(0.94, 0.6, 0.2, 0.01);
      old_pose.theta = 0.0;
      auto proposed = old_pose;
      proposed.theta = 0.5 * 3.141592653589793238462643383279502884;
      double velocity[3] = {0.0, 0.0, 0.0};
      double angular[3] = {0.0, 1.0, 0.0};
      const auto result = G::constrainMotion(
          old_pose, proposed, true, velocity, angular, primary);
      const auto projected = G::makeCapsule(proposed);
      const double maximum_x =
          std::max(projected.first.x, projected.second.x) + projected.radius;
      require(result.valid == 1 && result.outer_contact == 1 &&
                  result.projected == 1 &&
                  std::abs(maximum_x - primary.prob_hi[0]) <= 2*tolerance,
              "rotation-induced outer-wall penetration is projected");
    }

    {
      const auto invalid = xPose(0.0, 0.5, 0.1, 0.01);
      auto proposed = invalid;
      double velocity[3] = {0.0, 0.0, 0.0};
      double angular[3] = {0.0, 0.0, 0.0};
      const auto result = G::constrainMotion(
          invalid, proposed, true, velocity, angular, primary);
      require(result.valid == 0,
              "initial capsule embedded in solid fails closed");
    }

    {
      const auto old_pose = xPose(0.3, 0.9, 0.1, 0.01);
      auto proposed = old_pose;
      double velocity[3] = {
          std::numeric_limits<double>::infinity(), 0.0, 0.0};
      double angular[3] = {0.0, 0.0, 0.0};
      const auto result = G::constrainMotion(
          old_pose, proposed, true, velocity, angular, primary);
      require(result.valid == 0,
              "nonfinite motion proposal fails closed");
    }

    std::cout << "C09_GEOMETRY_UNIT PASS checks=" << checks << '\n';
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "C09_GEOMETRY_UNIT FAIL after_checks=" << checks
              << " reason=" << error.what() << '\n';
    return 1;
  }
}
