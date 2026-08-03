#include <bmx_phosphorus_uptake_K.H>

#include <algorithm>
#include <cmath>
#include <iostream>
#include <limits>
#include <numeric>
#include <stdexcept>
#include <string>
#include <vector>

namespace U = BMXPhosphorusUptake;

namespace
{
  int checks = 0;
  constexpr double jmax = 2.95949412514e-12;
  constexpr double km = 1.00084710414e-9;

  void require (bool condition, const char* message)
  {
    ++checks;
    if (!condition) throw std::runtime_error(message);
  }

  bool close (double a, double b, double scale = 1.0)
  {
    return std::abs(a-b) <=
           64.0 * std::numeric_limits<double>::epsilon() *
               std::max(scale, std::abs(a) + std::abs(b));
  }

  std::vector<double> transact (const std::vector<double>& requests,
                                double available)
  {
    const double sum = std::accumulate(
        requests.begin(), requests.end(), 0.0);
    const double scale = U::donorScale(available, sum);
    std::vector<double> accepted;
    for (double request : requests) accepted.push_back(scale * request);
    return accepted;
  }
}

int main ()
{
  try {
    require(U::schema_version == 2, "runtime schema version");
    require(std::string(U::contract_id) ==
                "UDC-20260801-P12-UPTAKE-ONLY-V1",
            "contract id");
    require(std::string(U::contract_sha256).size() == 64,
            "contract hash width");
    require(std::string(U::authority_source_sha256).size() == 64,
            "authority hash width");
    require(std::string(U::numerical_contract_id) ==
                "USER-DIRECTED-20260801-P12-NUMERICAL-V2",
            "numerical contract id");
    require(std::string(U::numerical_contract_sha256).size() == 64,
            "numerical contract hash width");

    require(U::surfaceFlux(-1.0, jmax, km) == 0.0,
            "negative donor clamps to zero");
    require(U::surfaceFlux(0.0, jmax, km) == 0.0,
            "zero donor");
    require(U::surfaceFlux(km, jmax, km) == 0.5*jmax,
            "Michaelis half saturation");
    require(U::surfaceFlux(1.0e6*km, jmax, km) < jmax,
            "finite concentration remains below saturation");
    require(U::surfaceFlux(km, 0.0, km) == 0.0,
            "Jmax off control");
    require(U::surfaceFlux(km, jmax, 0.0) == 0.0,
            "invalid zero Km fails closed");

    const double area = 2.5e-5;
    const double dt = 1800.0;
    const double expected_request = area * 0.5 * jmax * dt;
    require(U::requestedAmount(km, area, dt, jmax, km) ==
                expected_request,
            "one-segment analytical request");
    require(U::requestedAmount(km, 0.0, dt, jmax, km) == 0.0,
            "zero area control");
    require(U::requestedAmount(km, area, 0.0, jmax, km) == 0.0,
            "zero dt control");

    require(U::donorScale(1.0, 0.0) == 0.0,
            "zero request scale");
    require(U::donorScale(-1.0, 2.0) == 0.0,
            "negative availability clamps");
    require(U::donorScale(2.0, 1.0) == 1.0,
            "uncapped donor");
    require(U::donorScale(1.0, 2.0) == 0.5,
            "shared donor cap");
    require(U::donorDemandRatio(2.0, 1.0) == 0.5,
            "uncapped donor demand ratio");
    require(U::donorDemandRatio(1.0, 2.0) == 2.0,
            "capped donor demand ratio");
    require(U::donorDemandRatio(0.0, 2.0) == 0.0,
            "zero inventory is reported through the separate event flag");

    const std::vector<double> requests{1.0, 2.0, 3.0};
    const auto accepted = transact(requests, 3.0);
    require(close(std::accumulate(accepted.begin(), accepted.end(), 0.0),
                  3.0),
            "accepted sum equals donor cap");
    require(accepted[0] == 0.5 && accepted[1] == 1.0 &&
                accepted[2] == 1.5,
            "common proportional scale");

    std::vector<double> permuted{3.0, 1.0, 2.0};
    auto permuted_accepted = transact(permuted, 3.0);
    std::sort(permuted_accepted.begin(), permuted_accepted.end());
    auto sorted_accepted = accepted;
    std::sort(sorted_accepted.begin(), sorted_accepted.end());
    require(permuted_accepted == sorted_accepted,
            "donor order permutation invariant");

    const auto subdivided = transact({0.5, 0.5, 2.0, 3.0}, 3.0);
    require(close(subdivided[0] + subdivided[1], accepted[0]),
            "segment subdivision invariant");
    require(close(std::accumulate(subdivided.begin(), subdivided.end(), 0.0),
                  3.0),
            "subdivision preserves donor cap");

    require(U::eligibleArea(
                4.0, 0.003, true,
                U::AreaMode::full_exposed_surface, 1.0) == 4.0,
            "full exposed area");
    require(U::eligibleArea(
                4.0, 0.003, true, U::AreaMode::zero, 1.0) == 0.0,
            "zero-area control");
    require(U::eligibleArea(
                4.0, 0.003, true, U::AreaMode::tip_005, 1.0) == 4.0,
            "complete fixed tip lies inside smallest terminal window");
    require(U::eligibleArea(
                4.0, 0.006, true, U::AreaMode::tip_005, 1.0) < 0.0,
            "partial-segment terminal area fails closed");
    require(U::eligibleArea(
                4.0, 0.003, false, U::AreaMode::tip_010, 1.0) < 0.0,
            "non-tip graph traversal fails closed");

    const double request_low =
        U::requestedAmount(1.61e-8, area, dt, jmax, km);
    const double request_high =
        U::requestedAmount(4.52e-8, area, dt, jmax, km);
    require(request_low > 0.0 && request_high > request_low,
            "both adopted D arms active and ordered");
    require(request_high / request_low < 4.52e-8 / 1.61e-8,
            "Michaelis saturation is nonlinear");

    std::cout << "C10_UPTAKE_UNIT PASS checks=" << checks << '\n';
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "C10_UPTAKE_UNIT FAIL check=" << checks
              << " error=" << error.what() << '\n';
    return 1;
  }
}
