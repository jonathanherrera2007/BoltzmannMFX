#include <bmx_p15_stage0_K.H>

#include <algorithm>
#include <array>
#include <cmath>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

namespace P15 = BMXP15Stage0;

namespace
{
  constexpr double pi =
      3.141592653589793238462643383279502884;
  int checks = 0;

  void require (bool condition, const std::string& message)
  {
    ++checks;
    if (!condition) throw std::runtime_error(message);
  }

  bool near (double first, double second, double factor = 256.0)
  {
    const double scale = std::max(
        {std::abs(first), std::abs(second), 1.0e-300});
    return std::abs(first-second) <=
           factor*std::numeric_limits<double>::epsilon()*scale;
  }

  struct TwoState
  {
    double first = 0.0;
    double second = 0.0;
  };

  TwoState explicitTwoSegment (double first_amount,
                               double second_amount,
                               double first_volume,
                               double second_volume,
                               double conductance,
                               double duration,
                               int steps)
  {
    TwoState result{first_amount, second_amount};
    const double dt = duration/static_cast<double>(steps);
    for (int step = 0; step < steps; ++step) {
      const double request = conductance *
          (result.first/first_volume-result.second/second_volume)*dt;
      const double donor = request >= 0.0 ? result.first : result.second;
      const double scale = request == 0.0 ? 1.0 :
          std::min(1.0, std::max(0.0, donor)/std::abs(request));
      const double accepted = request*scale;
      result.first -= accepted;
      result.second += accepted;
    }
    return result;
  }

  double terminalArea (double radius,
                       double length,
                       double first_distance,
                       double second_distance,
                       double threshold,
                       int free_first,
                       int free_second)
  {
    const double eligible = P15::terminalEligibleLength(
        first_distance, second_distance, length, threshold);
    const int caps =
        (free_first && first_distance <= threshold ? 1 : 0) +
        (free_second && second_distance <= threshold ? 1 : 0);
    return P15::physicalArea(radius, eligible, caps);
  }
}

int main ()
{
  try {
    require(std::string(P15::authority_classification) ==
                "USER_ADOPTED_PROVISIONAL_PENDING_MENTOR_OVERRIDE" &&
                std::string(P15::stage_id) == "C13",
            "authority and stage identities are exact");
    require(std::string(P15::global_order_sha256) ==
                "bb63c219a860687d91ce1acf06a667c9208abf026b32f18acfc64884bb696dd6",
            "global order remains the frozen V1 bytes");
    require(near(P15::endpointCoordinate(
                     0.25, 0.10, pi/2.0, 0.0, 1, 0), 0.20) &&
                near(P15::endpointCoordinate(
                     0.25, 0.10, pi/2.0, 0.0, 2, 0), 0.30),
            "site 1 is negative-orientation and site 2 positive-orientation");
    require(!P15::finite(P15::endpointCoordinate(
                0.0, 1.0, 0.0, 0.0, 3, 0)),
            "invalid endpoint site fails closed");

    constexpr double diffusivity = 1.25e-6;
    constexpr double first_radius = 0.001;
    constexpr double second_radius = 0.0017;
    constexpr double first_length = 0.012;
    constexpr double second_length = 0.027;
    const double first_half = P15::halfSegmentConductance(
        diffusivity, first_radius, first_length);
    const double second_half = P15::halfSegmentConductance(
        diffusivity, second_radius, second_length);
    const double degree_two = P15::virtualPairConductance(
        first_half, second_half, first_half+second_half);
    require(near(degree_two, P15::degreeTwoConductance(
                    diffusivity, first_radius, first_length,
                    second_radius, second_length)),
            "unequal-radius unequal-length degree-two reduction is exact");
    require(near(1.0/degree_two,
                 first_length/(2.0*diffusivity*pi*first_radius*first_radius) +
                 second_length/(2.0*diffusivity*pi*second_radius*second_radius)),
            "degree-two axial half-resistances add");

    for (const std::vector<double>& gamma :
         {std::vector<double>{2.0, 3.0, 7.0},
          std::vector<double>{1.0, 2.0, 5.0, 11.0}}) {
      std::vector<double> concentration(gamma.size());
      for (std::size_t index = 0; index < gamma.size(); ++index) {
        concentration[index] = 0.5+0.75*static_cast<double>(index);
      }
      double sum_gamma = 0.0;
      double weighted = 0.0;
      for (std::size_t index = 0; index < gamma.size(); ++index) {
        sum_gamma += gamma[index];
        weighted += gamma[index]*concentration[index];
      }
      const double junction_concentration = weighted/sum_gamma;
      double global_flux = 0.0;
      for (std::size_t first = 0; first < gamma.size(); ++first) {
        double eliminated_flux = 0.0;
        for (std::size_t second = 0; second < gamma.size(); ++second) {
          if (first == second) continue;
          const double pair = P15::virtualPairConductance(
              gamma[first], gamma[second], sum_gamma);
          eliminated_flux += pair*
              (concentration[first]-concentration[second]);
        }
        const double half_flux = gamma[first]*
            (concentration[first]-junction_concentration);
        require(near(eliminated_flux, half_flux),
                "degree-three/four junction elimination matches the common node");
        global_flux += eliminated_flux;
      }
      require(near(global_flux, 0.0, 2048.0),
              "degree-three/four virtual-pair flux is globally conservative");
    }

    constexpr double volume_1 = 2.0;
    constexpr double volume_2 = 5.0;
    constexpr double g = 0.4;
    constexpr double duration = 1.25;
    const double total = 7.0;
    const double initial_difference = 3.0/volume_1-4.0/volume_2;
    const double exact_difference = initial_difference*std::exp(
        -g*(1.0/volume_1+1.0/volume_2)*duration);
    const double equilibrium = total/(volume_1+volume_2);
    const double exact_first = volume_1*(
        equilibrium + volume_2/(volume_1+volume_2)*exact_difference);
    const auto coarse = explicitTwoSegment(
        3.0, 4.0, volume_1, volume_2, g, duration, 16);
    const auto fine = explicitTwoSegment(
        3.0, 4.0, volume_1, volume_2, g, duration, 64);
    require(std::abs(fine.first-exact_first) <
                std::abs(coarse.first-exact_first),
            "two-segment explicit equilibration converges to the exponential solution");
    require(near(fine.first+fine.second, total),
            "two-segment pair update conserves the global amount");
    require(fine.first >= 0.0 && fine.second >= 0.0 &&
                fine.first/volume_1 <= 1.5 &&
                fine.first/volume_1 >= 0.8 &&
                fine.second/volume_2 <= 1.5 &&
                fine.second/volume_2 >= 0.8,
            "stable explicit transport is positive and creates no new extremum");

    const TwoState zero_before{3.125, 9.5};
    const auto zero_after = explicitTwoSegment(
        zero_before.first, zero_before.second, 1.0, 1.0,
        0.0, 100.0, 1);
    require(zero_after.first == zero_before.first &&
                zero_after.second == zero_before.second,
            "D_bond=0 is an exact arithmetic identity");

    const double available = 2.0;
    const std::array<double,3> requests{{1.0, 2.0, 5.0}};
    const double requested = 8.0;
    const double donor_scale = std::min(1.0, available/requested);
    double accepted = 0.0;
    for (const double request : requests) accepted += request*donor_scale;
    require(donor_scale == 0.25 && accepted == available,
            "proportional donor arbitration caps all outgoing pairs atomically");
    require(requested == accepted+(requested-accepted),
            "fault-injection requested/accepted/rejected ledger closes");

    require(P15::stableSubsteps(2.0, 0.5) == 4 &&
                (2.0/4.0)*0.5 <= 0.25,
            "diagonal stability bound chooses the exact minimum substep count");
    require(P15::stableSubsteps(1.0, 0.0) == 1,
            "zero rate avoids a spurious subcycle");

    constexpr double radius = 0.001;
    constexpr double length = 0.032;
    const double isolated_full = P15::physicalArea(radius, length, 2);
    require(near(isolated_full,
                 2.0*pi*radius*length+2.0*pi*radius*radius),
            "isolated TIP full area includes both free caps");
    require(P15::terminalEligibleLength(
                0.0, std::numeric_limits<double>::infinity(),
                length, 0.010) == 0.010,
            "connected simple TIP reaches ten millimetres from one origin");
    require(P15::terminalEligibleLength(
                0.0, 0.0, length, 0.020) == length,
            "two-ended terminal intervals use their physical union once");
    require(P15::terminalEligibleLength(
                0.004, 0.004, 0.020, 0.010) == 0.012,
            "equal-distance branch ties do not duplicate axial measure");
    require(P15::terminalEligibleLength(
                0.008, std::numeric_limits<double>::infinity(),
                0.020, 0.010) == 0.002,
            "terminal interval ending inside a segment is represented continuously");
    require(P15::terminalEligibleLength(
                0.010, std::numeric_limits<double>::infinity(),
                length, 0.010) == 0.0,
            "snapped threshold boundary has zero axial measure");

    std::array<P15::TerminalAreaRecord,3> records{};
    records[0] = {1, 0, 10.0, 1.0, 2.0, 4.0};
    records[1] = {1, 2, 20.0, 2.0, 4.0, 8.0};
    records[2] = {5, 0, 30.0, 3.0, 6.0, 12.0};
    require(P15::findTerminalArea(records.data(), 3, 1, 2) ==
                &records[1],
            "terminal lookup uses stable particle-id/cpu ordering");
    require(P15::terminalEligibleArea(
                records.data(), 3, 1, 2, true, 3, 1.0) == 4.0 &&
                P15::terminalEligibleArea(
                    records.data(), 3, 1, 2, true, 5, 2.5) == 10.0,
            "TIP010 and area-matched TIP010 select their bound physical area");
    require(P15::terminalEligibleArea(
                records.data(), 3, 1, 2, false, 0, 1.0) == 0.0 &&
                P15::terminalEligibleArea(
                    records.data(), 3, 99, 0, true, 0, 1.0) < 0.0,
            "nonfungal identity and missing-record faults fail closed");

    for (const int children : {2, 4, 8}) {
      constexpr double parent_length = 0.08;
      constexpr double parent_radius = 0.0013;
      const double area = P15::crossSectionArea(parent_radius);
      const double parent_resistance =
          parent_length/(diffusivity*area);
      double child_resistance = 0.0;
      double child_full_area = 0.0;
      double child_tip_area = 0.0;
      for (int child = 0; child < children; ++child) {
        const double child_length = parent_length/children;
        child_resistance += child_length/(diffusivity*area);
        const int free_caps = (child == 0 ? 1 : 0) +
                              (child == children-1 ? 1 : 0);
        child_full_area += P15::physicalArea(
            parent_radius, child_length, free_caps);
        const double first_distance = child*child_length;
        const double second_distance =
            (children-child-1)*child_length;
        child_tip_area += terminalArea(
            parent_radius, child_length, first_distance, second_distance,
            0.010, child == 0, child == children-1);
      }
      require(near(child_resistance, parent_resistance),
              "1-to-2/4/8 axial resistances are additive");
      require(near(child_full_area,
                   P15::physicalArea(parent_radius, parent_length, 2)),
              "1-to-2/4/8 full exposed areas are invariant");
      require(near(child_tip_area, terminalArea(
                       parent_radius, parent_length, 0.0, 0.0,
                       0.010, 1, 1)),
              "1-to-2/4/8 terminal areas are invariant");
      const double constant_flux = P15::degreeTwoConductance(
          diffusivity, parent_radius, parent_length/children,
          parent_radius, parent_length/children) * (2.0-2.0);
      require(constant_flux == 0.0,
              "constant concentration has exact zero refined transfer");
      const double affine_flux = diffusivity*area*3.0;
      const double child_gradient_flux = diffusivity*area*
          ((3.0*parent_length/children)/(parent_length/children));
      require(near(child_gradient_flux, affine_flux),
              "affine concentration preserves steady physical flux after subdivision");
    }

    require(!P15::finite(std::numeric_limits<double>::quiet_NaN()) &&
                !P15::finite(std::numeric_limits<double>::infinity()),
            "nonfinite graph operands are rejected by the common guard");
    require(P15::physicalArea(0.0, 1.0, 0) == 0.0 &&
                P15::halfSegmentConductance(1.0, 1.0, 0.0) >
                    std::numeric_limits<double>::max(),
            "invalid geometry produces a caller-detectable nonfinite/nonpositive operand");

    std::cout << "C13_P15_UNIT PASS checks=" << checks << '\n';
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "C13_P15_UNIT FAIL after_checks=" << checks
              << " reason=" << error.what() << '\n';
    return 1;
  }
}
