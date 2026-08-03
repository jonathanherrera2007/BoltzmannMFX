#include <bmx_phosphorus_export_K.H>

#include <algorithm>
#include <array>
#include <cmath>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

namespace P14 = BMXPhosphorusExport;
namespace P11 = BMXPhosphorusGeometry;

namespace
{
  int checks = 0;

  void require (bool condition, const std::string& message)
  {
    ++checks;
    if (!condition) throw std::runtime_error(message);
  }

  P11::RuntimeConfig geometry ()
  {
    P11::RuntimeConfig result;
    result.enabled = 1;
    result.mesh_pd_component = 5;
    result.mesh_pf_component = 6;
    result.prob_lo[0] = -1.0;
    result.prob_hi[0] = 1.0;
    result.prob_lo[1] = 0.0;
    result.prob_hi[1] = 0.1;
    result.prob_lo[2] = 0.0;
    result.prob_hi[2] = 1.2;
    result.base_tolerance =
        64.0 * std::numeric_limits<double>::epsilon();
    return result;
  }

  P11::Capsule capsule (double ax, double az, double bx, double bz,
                        double radius = 0.01)
  {
    return {{ax, 0.05, az}, {bx, 0.05, bz}, radius};
  }

  double length (const P11::Capsule& value)
  {
    const double dx = value.second.x-value.first.x;
    const double dy = value.second.y-value.first.y;
    const double dz = value.second.z-value.first.z;
    return std::sqrt(dx*dx+dy*dy+dz*dz);
  }

  P11::Capsule child (const P11::Capsule& parent, int index, int count)
  {
    const auto point = [&](double s) {
      return P11::Point{
          parent.first.x+s*(parent.second.x-parent.first.x),
          parent.first.y+s*(parent.second.y-parent.first.y),
          parent.first.z+s*(parent.second.z-parent.first.z)};
    };
    P11::Capsule result;
    result.first = point(static_cast<double>(index)/count);
    result.second = point(static_cast<double>(index+1)/count);
    result.radius = parent.radius;
    return result;
  }

  struct ParticleFixture
  {
    std::array<double, MAX_CHEM_REAL_VAR> real{};
    std::array<int, MAX_CHEM_INT_VAR> integer{};
    std::array<double, 3> position{};
  };

  ParticleFixture fullContactParticle ()
  {
    ParticleFixture result;
    result.position = {0.0, 0.05, 0.9};
    result.real[realIdx::radius] = 0.01;
    result.real[realIdx::c_length] = 0.08;
    result.real[realIdx::theta] =
        0.5 * 3.141592653589793238462643383279502884;
    result.real[realIdx::phi] = 0.0;
    result.real[realIdx::vol] = 2.0;
    result.real[realIdx::first_data+BMXChemLayout::A] = 1.5;
    result.real[realIdx::first_data+BMXChemLayout::P_D] = 5.0;
    result.real[realIdx::first_data+BMXChemLayout::P_E] = 2.0;
    result.real[realIdx::first_data+BMXChemLayout::P_F] = 3.0;
    result.integer[intIdx::cell_type] = cellType::FUNGI;
    return result;
  }
}

int main ()
{
  try {
    const auto config = geometry();
    P11::CapsuleClassification classification;

    const auto no_contact = capsule(0.2, 0.9, 0.3, 0.9);
    require(P14::continuousAxialFraction(
                no_contact, config, &classification) == 0.0 &&
                classification.window_contact == 0,
            "no-contact segment has zero active fraction");

    const auto tangent = capsule(0.06, 0.9, 0.2, 0.9);
    require(P14::continuousAxialFraction(
                tangent, config, &classification) == 0.0 &&
                classification.window_contact == 1 &&
                classification.solid_contact == 0,
            "finite-radius tangency has zero active measure");

    const auto partial = capsule(0.055, 0.9, 0.2, 0.9);
    const double partial_fraction = P14::continuousAxialFraction(
        partial, config, &classification);
    require(partial_fraction > 0.0 && partial_fraction < 1.0 &&
                classification.window_contact == 1 &&
                classification.true_crossing == 0,
            "partial window contact is continuous and crossing-independent");

    const auto full = capsule(-0.04, 0.9, 0.04, 0.9);
    require(P14::continuousAxialFraction(full, config) == 1.0,
            "centerline fully within support has unit fraction");

    const auto crossing = capsule(-0.2, 0.9, 0.2, 0.9);
    const double crossing_fraction = P14::continuousAxialFraction(
        crossing, config, &classification);
    require(crossing_fraction > 0.0 && crossing_fraction < 1.0 &&
                classification.true_crossing == 1,
            "true crossing is diagnostic and remains eligible");

    const auto oblique = capsule(-0.2, 0.86, 0.2, 0.94);
    const double oblique_forward = P14::continuousAxialFraction(
        oblique, config);
    const auto oblique_reverse = capsule(0.2, 0.94, -0.2, 0.86);
    const double oblique_backward = P14::continuousAxialFraction(
        oblique_reverse, config);
    require(oblique_forward > 0.0 && oblique_forward < 1.0 &&
                std::abs(oblique_forward-oblique_backward) <=
                    P14::reward_molar_multiplier*
                    std::numeric_limits<double>::epsilon(),
            "oblique contact is orientation-reversal invariant");

    const auto solid_edge = capsule(-0.2, 0.81, 0.2, 0.81);
    require(P14::continuousAxialFraction(
                solid_edge, config, &classification) == 0.0 &&
                classification.solid_contact == 1 &&
                classification.window_contact == 0,
            "solid-frame edge has precedence over window support");

    for (const auto& parent :
         {capsule(-0.2, 0.9, 0.2, 0.9),
          capsule(-0.2, 0.86, 0.2, 0.94)}) {
      for (const int count : {2, 4, 8}) {
      const double area = 3.141592653589793238462643383279502884 *
                          parent.radius*parent.radius;
      const double parent_volume = area*length(parent);
      const double parent_fraction =
          P14::continuousAxialFraction(parent, config);
      double child_active_volume = 0.0;
      double child_active_d = 0.0;
      const double concentration = 2.75;
      for (int index = 0; index < count; ++index) {
        const auto segment = child(parent, index, count);
        const double volume = area*length(segment);
        const double fraction =
            P14::continuousAxialFraction(segment, config);
        child_active_volume += fraction*volume;
        child_active_d += fraction*concentration*volume;
      }
      const double expected_volume = parent_fraction*parent_volume;
      const double expected_d = concentration*expected_volume;
      require(std::abs(expected_volume-child_active_volume) <=
                  BMXPhosphorus::localTolerance(
                      std::abs(expected_volume)+
                      std::abs(child_active_volume)),
              "geometry-preserving subdivision conserves f*V");
      require(std::abs(expected_d-child_active_d) <=
                  BMXPhosphorus::localTolerance(
                      std::abs(expected_d)+std::abs(child_active_d)),
              "volume-partitioned subdivision conserves f*N_D");
      }
    }

    auto invalid = crossing;
    invalid.first.x = std::numeric_limits<double>::quiet_NaN();
    require(P14::continuousAxialFraction(invalid, config) < 0.0,
            "nonfinite geometry fails closed");
    auto zero_length = capsule(0.0, 0.9, 0.0, 0.9);
    require(P14::continuousAxialFraction(zero_length, config) < 0.0,
            "nonpositive centerline length fails closed");
    auto zero_radius = crossing;
    zero_radius.radius = 0.0;
    require(P14::continuousAxialFraction(zero_radius, config) < 0.0,
            "nonpositive radius fails closed");

    require(P14::reward_molar_multiplier == 967.0/125.0 &&
                P14::reward_molar_multiplier == 7.736,
            "executable reward multiplier is exact 967/125");
    for (const double rate :
         {0.0, 1.0e-6, 5.26977773579e-6, 1.0e-5, 1.0e-4}) {
      const double donor = 4.0;
      const double dt = 120.0;
      const double request = donor*(1.0-std::exp(-rate*dt));
      const auto transaction = P14::transactAmounts(donor, 3.0, request);
      require(transaction.status == P14::StepStatus::ok &&
                  transaction.accepted == request &&
                  transaction.reward == 7.736*transaction.accepted &&
                  std::abs((transaction.a_after-transaction.a_before)-
                           transaction.reward) <=
                      BMXPhosphorus::localTolerance(
                          std::abs(transaction.a_after)+
                          std::abs(transaction.a_before)+
                          std::abs(transaction.reward)),
              "adopted export level obeys analytic and exact reward algebra");
      if (rate == 0.0) {
        require(transaction.accepted == 0.0 &&
                    transaction.reward == 0.0,
                "matched zero control is exact");
      }
    }

    double donor = 8.0;
    constexpr double rate = 5.26977773579e-6;
    constexpr double dt = 60.0;
    for (int update = 0; update < 100; ++update) {
      const auto transaction = P14::transactAmounts(
          donor, 0.0, donor*(1.0-std::exp(-rate*dt)));
      require(transaction.status == P14::StepStatus::ok,
              "analytic export transaction remains valid");
      donor = transaction.donor_after;
    }
    require(std::abs(donor-8.0*std::exp(-rate*dt*100.0)) <=
                BMXPhosphorus::localTolerance(
                    std::abs(donor)+
                    std::abs(8.0*std::exp(-rate*dt*100.0))),
            "full-contact repeated export is analytically exponential");

    const auto capped = P14::transactAmounts(1.0, 2.0, 3.0);
    require(capped.status == P14::StepStatus::ok &&
                capped.accepted == 1.0 && capped.rejected == 2.0 &&
                capped.donor_after == 0.0 && capped.donor_capped == 1 &&
                capped.reward == 7.736,
            "donor cap is nonnegative and conserves request");
    require(P14::transactAmounts(-1.0, 0.0, 0.0).status ==
                P14::StepStatus::negative_amount,
            "negative donor fault fails closed");
    require(P14::transactAmounts(
                1.0, 0.0, std::numeric_limits<double>::infinity()).status ==
                P14::StepStatus::nonfinite,
            "nonfinite request fault fails closed");

    auto particle = fullContactParticle();
    const auto before = particle.real;
    const auto step = P14::apply(
        particle.position.data(), particle.real.data(), particle.integer.data(),
        100.0, rate, config);
    const double old_d = before[realIdx::first_data+BMXChemLayout::P_D] *
                         before[realIdx::vol];
    const double new_d =
        particle.real[realIdx::first_data+BMXChemLayout::P_D] *
        particle.real[realIdx::vol];
    const double old_a = before[realIdx::first_data+BMXChemLayout::A] *
                         before[realIdx::vol];
    const double new_a =
        particle.real[realIdx::first_data+BMXChemLayout::A] *
        particle.real[realIdx::vol];
    require(step.status == P14::StepStatus::ok && step.eligible == 1 &&
                step.interface_fraction == 1.0 &&
                std::abs((old_d-new_d)-step.accepted_p) <=
                    BMXPhosphorus::localTolerance(
                        std::abs(old_d)+std::abs(new_d)+
                        std::abs(step.accepted_p)) &&
                std::abs((new_a-old_a)-step.reward_a) <=
                    BMXPhosphorus::localTolerance(
                        std::abs(new_a)+std::abs(old_a)+
                        std::abs(step.reward_a)) &&
                step.reward_a == 7.736*step.accepted_p,
            "O09 local D debit and A credit are one accepted transaction");
    require(particle.real[realIdx::first_data+BMXChemLayout::P_E] ==
                before[realIdx::first_data+BMXChemLayout::P_E] &&
                particle.real[realIdx::first_data+BMXChemLayout::P_F] ==
                before[realIdx::first_data+BMXChemLayout::P_F],
            "P14 leaves E and inactive F unchanged");

    auto bad_volume = fullContactParticle();
    bad_volume.real[realIdx::vol] = 0.0;
    const auto bad_before = bad_volume.real;
    const auto bad_step = P14::apply(
        bad_volume.position.data(), bad_volume.real.data(),
        bad_volume.integer.data(), 100.0, rate, config);
    require(bad_step.status == P14::StepStatus::invalid_geometry &&
                bad_volume.real == bad_before,
            "invalid owning volume abort path performs no local write");
    auto bad_amount = fullContactParticle();
    bad_amount.real[realIdx::first_data+BMXChemLayout::P_D] =
        std::numeric_limits<double>::quiet_NaN();
    const auto nan_step = P14::apply(
        bad_amount.position.data(), bad_amount.real.data(),
        bad_amount.integer.data(), 100.0, rate, config);
    require(nan_step.status == P14::StepStatus::nonfinite,
            "nonfinite particle amount fails closed");

    std::cout << "C12_EXPORT_UNIT PASS checks=" << checks << '\n';
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "C12_EXPORT_UNIT FAIL after_checks=" << checks
              << " reason=" << error.what() << '\n';
    return 1;
  }
}
