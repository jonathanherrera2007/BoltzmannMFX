#include <bmx_phosphorus_reactions_K.H>

#include <algorithm>
#include <cmath>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>

namespace P13 = BMXPhosphorusReactions;

namespace
{
  int checks = 0;
  constexpr double pi = 3.141592653589793238462643383279502884;

  void require (bool condition, const char* message)
  {
    ++checks;
    if (!condition) throw std::runtime_error(message);
  }

  bool close (double first, double second, double scale = 1.0)
  {
    return std::abs(first - second) <=
           128.0 * std::numeric_limits<double>::epsilon() *
               std::max(scale, std::abs(first) + std::abs(second));
  }

  struct Fixture
  {
    double real[MAX_CHEM_REAL_VAR]{};
    int integer[MAX_CHEM_INT_VAR]{};

    Fixture (double b_amount, double d_amount, double e_amount,
             double f_amount = 0.0)
    {
      const double radius = 2.0e-4;
      const double length = 3.0e-3;
      const double volume = pi * radius * radius * length;
      real[realIdx::radius] = radius;
      real[realIdx::c_length] = length;
      real[realIdx::area] = 2.0 * pi * radius * (radius + length);
      real[realIdx::vol] = volume;
      integer[intIdx::cell_type] = cellType::FUNGI;
      integer[intIdx::position] = siteLocation::TIP;
      integer[intIdx::n_bnds] = 0;
      auto* values = &real[realIdx::first_data];
      values[1] = b_amount / volume;
      values[BMXChemLayout::P_D] = d_amount / volume;
      values[BMXChemLayout::P_E] = e_amount / volume;
      values[BMXChemLayout::P_F] = f_amount / volume;
    }

    double amount (int component) const
    {
      return real[realIdx::first_data + component] * real[realIdx::vol];
    }
  };

  P13::StepResult apply (Fixture& fixture,
                         bool reactions,
                         bool growth,
                         double k_de,
                         double k_ed,
                         double q_p = 3.0e-5,
                         double growth_ratio = 1.0,
                         double dt = 100.0)
  {
    return P13::apply(fixture.real, fixture.integer, dt, reactions, growth,
                      k_de, k_ed, q_p, growth_ratio,
                      1.0e-5, 0.1, 2.5e-4, 3.5e-3);
  }
}

int main ()
{
  try {
    require(P13::schema_version == 1, "schema version");
    require(std::string(P13::contract_id) ==
                "bmx-p13-reaction-liebig-v1",
            "contract identity");
    require(std::string(P13::contract_sha256).size() == 64,
            "contract hash width");
    require(std::string(P13::operator_fit_id) == "bmx-p13-o02-fit-v1",
            "O02 fit identity");

    {
      Fixture fixture(1.0e-13, 1.0e-12, 2.0e-13);
      const double old_volume = fixture.real[realIdx::vol];
      const auto result = apply(fixture, false, false, 0.0, 0.0);
      require(result.status == P13::StepStatus::ok,
              "disabled operators return ok");
      require(fixture.real[realIdx::vol] == old_volume,
              "disabled operators preserve geometry");
      require(close(fixture.amount(BMXChemLayout::P_D), 1.0e-12, 1.0e-12) &&
                  close(fixture.amount(BMXChemLayout::P_E), 2.0e-13, 2.0e-13),
              "disabled operators preserve D/E");
    }

    {
      Fixture fixture(1.0e-13, 1.0e-12, 0.0);
      const auto result = apply(
          fixture, true, false, 1.0e-5, 0.0, 0.0, 0.0, 1000.0);
      require(result.status == P13::StepStatus::ok,
              "one-way reaction status");
      require(close(result.reaction_forward, 1.0e-14, 1.0e-14),
              "one-way forward amount");
      require(result.reaction_reverse == 0.0, "one-way reverse zero");
      require(close(fixture.amount(BMXChemLayout::P_D), 9.9e-13, 1.0e-12) &&
                  close(fixture.amount(BMXChemLayout::P_E), 1.0e-14, 1.0e-14),
              "one-way state update");
      require(close(fixture.amount(BMXChemLayout::P_D) +
                        fixture.amount(BMXChemLayout::P_E),
                    1.0e-12, 1.0e-12),
              "one-way P conservation");
    }

    for (const double rate : {1.0e-6, 1.0e-5, 1.0e-4}) {
      Fixture fixture(1.0e-13, 8.0e-13, 2.0e-13);
      const auto result = apply(
          fixture, true, false, rate, rate, 0.0, 0.0, 1000.0);
      const double forward = rate * 8.0e-13 * 1000.0;
      const double reverse = rate * 2.0e-13 * 1000.0;
      require(close(result.reaction_forward, forward, forward) &&
                  close(result.reaction_reverse, reverse, reverse),
              "symmetric common-prestate transfers");
      require(close(fixture.amount(BMXChemLayout::P_D),
                    8.0e-13 - forward + reverse, 1.0e-12) &&
                  close(fixture.amount(BMXChemLayout::P_E),
                    2.0e-13 + forward - reverse, 1.0e-12),
              "symmetric reaction state");
    }

    {
      Fixture zero_d(1.0e-13, 0.0, 2.0e-13);
      const auto result = apply(
          zero_d, true, false, 1.0e-5, 0.0, 0.0, 0.0, 1000.0);
      require(result.reaction_forward == 0.0 &&
                  result.reaction_reverse == 0.0,
              "zero D has no one-way reaction");
      Fixture zero_e(1.0e-13, 1.0e-12, 0.0);
      const auto symmetric = apply(
          zero_e, true, false, 1.0e-5, 1.0e-5, 0.0, 0.0, 1000.0);
      require(symmetric.reaction_forward > 0.0 &&
                  symmetric.reaction_reverse == 0.0,
              "zero E has no reverse reaction");
    }

    {
      Fixture fixture(1.0e-13, 1.0e-12, 0.0);
      const auto result = apply(
          fixture, true, false, 1.0e-5, 0.0, 0.0, 0.0, 2.0e5);
      require(result.reaction_forward == 1.0e-12,
              "forward donor cap");
      require(fixture.amount(BMXChemLayout::P_D) == 0.0 &&
                  close(fixture.amount(BMXChemLayout::P_E), 1.0e-12, 1.0e-12),
              "donor cap remains nonnegative");
    }

    {
      const double b = 1.0e-13;
      const double e = 3.0e-14;
      Fixture fixture(b, 0.0, e, 7.0e-15);
      const auto result = apply(fixture, false, true, 0.0, 0.0);
      require(close(result.carbon_supported_growth, 1.0e-12, 1.0e-12) &&
                  close(result.phosphorus_supported_growth, 1.0e-12, 1.0e-12),
              "exact Liebig tie");
      require(close(result.accepted_growth, 1.0e-12, 1.0e-12),
              "tie accepted growth");
      require(close(result.b_debit, 1.0e-16, 1.0e-16) &&
                  close(result.e_debit, 3.0e-17, 3.0e-17),
              "quota debits");
      require(result.e_debit == result.structuralized_p,
              "E debit equals structural credit");
      require(close(fixture.amount(BMXChemLayout::P_F), 7.0e-15, 7.0e-15),
              "F inventory inert");
      require(fixture.real[realIdx::vol] > 0.0 &&
                  fixture.real[realIdx::dvdt] > 0.0,
              "accepted geometry committed");
      require(fixture.real[realIdx::first_data +
                           NUM_PARTICLE_CHEM_COMPONENTS +
                           BMXChemLayout::P_D] == 0.0 &&
                  fixture.real[realIdx::first_data +
                               NUM_PARTICLE_CHEM_COMPONENTS +
                               BMXChemLayout::P_E] == 0.0,
              "P working buffers stay zero");
    }

    {
      Fixture carbon_limited(1.0e-14, 0.0, 1.0e-12);
      const auto carbon = apply(
          carbon_limited, false, true, 0.0, 0.0);
      require(carbon.carbon_supported_growth <
                  carbon.phosphorus_supported_growth &&
                  close(carbon.accepted_growth,
                        carbon.carbon_supported_growth,
                        carbon.carbon_supported_growth),
              "carbon unique limiter");

      Fixture phosphorus_limited(1.0e-12, 0.0, 1.0e-16);
      const auto phosphorus = apply(
          phosphorus_limited, false, true, 0.0, 0.0);
      require(phosphorus.phosphorus_supported_growth <
                  phosphorus.carbon_supported_growth &&
                  close(phosphorus.accepted_growth,
                        phosphorus.phosphorus_supported_growth,
                        phosphorus.phosphorus_supported_growth),
              "phosphorus unique limiter");
    }

    {
      const double b = 1.0e-13;
      Fixture near_tie_carbon(b, 0.0, 0.3000000001 * b);
      const auto carbon = apply(
          near_tie_carbon, false, true, 0.0, 0.0);
      require(carbon.carbon_supported_growth <
                  carbon.phosphorus_supported_growth &&
                  close(carbon.accepted_growth,
                        carbon.carbon_supported_growth,
                        carbon.carbon_supported_growth),
              "near tie selects carbon deterministically");
      Fixture near_tie_phosphorus(b, 0.0, 0.2999999999 * b);
      const auto phosphorus = apply(
          near_tie_phosphorus, false, true, 0.0, 0.0);
      require(phosphorus.phosphorus_supported_growth <
                  phosphorus.carbon_supported_growth &&
                  close(phosphorus.accepted_growth,
                        phosphorus.phosphorus_supported_growth,
                        phosphorus.phosphorus_supported_growth),
              "near tie selects phosphorus deterministically");
    }

    {
      Fixture availability(1.0e-13, 0.0, 3.0e-14);
      const auto result = apply(
          availability, false, true, 0.0, 0.0,
          3.0e-5, 1.0, 2.0e5);
      require(close(result.accepted_growth, 1.0e-9, 1.0e-9),
              "B/E availability cap");
      require(close(result.b_debit, 1.0e-13, 1.0e-13) &&
                  close(result.e_debit, 3.0e-14, 3.0e-14),
              "availability cap consumes no more than donors");
      require(close(availability.amount(1), 0.0, 1.0e-13) &&
                  close(availability.amount(BMXChemLayout::P_E), 0.0, 3.0e-14),
              "availability donors reach zero exactly");
    }

    {
      Fixture b_capped(1.0e-13, 0.0, 1.0e-9);
      const auto b_result = apply(
          b_capped, false, true, 0.0, 0.0,
          3.0e-5, 1.0, 2.0e5);
      require(close(b_result.accepted_growth, 1.0e-9, 1.0e-9) &&
                  close(b_result.b_debit, 1.0e-13, 1.0e-13) &&
                  b_result.e_debit < 1.0e-9,
              "B availability cap is independent");

      Fixture e_capped(1.0e-9, 0.0, 3.0e-14);
      const auto e_result = apply(
          e_capped, false, true, 0.0, 0.0,
          3.0e-5, 1.0, 2.0e5);
      require(close(e_result.accepted_growth, 1.0e-9, 1.0e-9) &&
                  close(e_result.e_debit, 3.0e-14, 3.0e-14) &&
                  e_result.b_debit < 1.0e-9,
              "E availability cap is independent");
    }

    {
      Fixture blocked(1.0e-13, 0.0, 3.0e-14);
      blocked.real[realIdx::radius] = 2.5e-4;
      blocked.real[realIdx::c_length] = 3.5e-3;
      const double b_before = blocked.amount(1);
      const double e_before = blocked.amount(BMXChemLayout::P_E);
      const double volume_before = blocked.real[realIdx::vol];
      const auto result = apply(blocked, false, true, 0.0, 0.0);
      require(result.requested_growth > 0.0 &&
                  result.accepted_growth == 0.0 &&
                  result.rejected_growth == result.requested_growth,
              "geometry-ineligible growth rejected");
      require(blocked.amount(1) == b_before &&
                  blocked.amount(BMXChemLayout::P_E) == e_before &&
                  blocked.real[realIdx::vol] == volume_before,
              "rejected growth consumes neither B nor E");
    }

    {
      Fixture invalid(1.0e-13, 1.0e-12, 0.0);
      invalid.real[realIdx::first_data + BMXChemLayout::P_D] =
          std::numeric_limits<double>::infinity();
      const auto result = apply(
          invalid, true, false, 1.0e-5, 0.0, 0.0, 0.0);
      require(result.status == P13::StepStatus::nonfinite,
              "nonfinite input fails closed");
    }

    {
      Fixture invalid_negative(1.0e-13, -1.0e-13, 1.0e-12);
      const auto result = apply(
          invalid_negative, true, false, 1.0e-5, 0.0, 0.0, 0.0);
      require(result.status == P13::StepStatus::negative_amount,
              "negative amount beyond integrated tolerance fails closed");
    }

    {
      Fixture roundoff(1.0e-13, -1.0e-24, 1.0e-12);
      const auto result = apply(
          roundoff, true, false, 1.0e-5, 0.0, 0.0, 0.0);
      require(result.status == P13::StepStatus::ok &&
                  result.roundoff_clamps == 1 &&
                  roundoff.amount(BMXChemLayout::P_D) == 0.0,
              "integrated-tolerance negative clamps once and is reported");
    }

    std::cout << "C11_REACTION_UNIT PASS checks=" << checks << '\n';
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "C11_REACTION_UNIT FAIL check=" << checks
              << " error=" << error.what() << '\n';
    return 1;
  }
}
