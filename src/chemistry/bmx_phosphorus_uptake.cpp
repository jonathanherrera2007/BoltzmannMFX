//
// C10/P12 configuration and cumulative diagnostic ledger.
//
#include <bmx_phosphorus_uptake_K.H>

#include <AMReX.H>
#include <AMReX_ParallelDescriptor.H>
#include <AMReX_ParmParse.H>
#include <AMReX_Print.H>

#include <bmx_chem_layout.H>
#include <bmx_chem_species_parms.H>
#include <bmx_fluid_parms.H>
#include <bmx_phosphorus_geometry_K.H>
#include <bmx_p15_stage0_K.H>

#include <algorithm>
#include <cmath>
#include <iomanip>
#include <limits>
#include <sstream>
#include <vector>

namespace
{
  BMXPhosphorusUptake::CumulativeLedger uptake_ledger;

  bool allowedJmax (amrex::Real value)
  {
    constexpr amrex::Real primary = 2.95949412514e-12;
    return value == 0.0 || value == primary / 3.0 ||
           value == primary || value == 3.0 * primary;
  }

  bool allowedKm (amrex::Real value)
  {
    constexpr amrex::Real primary = 1.00084710414e-9;
    return value == 0.1 * primary || value == primary ||
           value == 10.0 * primary;
  }

  amrex::Real requiredZero (amrex::ParmParse& parameters,
                            const char* name)
  {
    amrex::Real value = 0.0;
    parameters.query(name, value);
    if (value != 0.0) {
      amrex::Abort(std::string("P12 uptake-only requires chem_species.") +
                   name + " to be exactly zero");
    }
    return value;
  }
}

namespace BMXPhosphorusUptake
{
  Config readAndValidateInput ()
  {
    Config result;
    amrex::ParmParse parameters("p12");
    int enabled_value = 0;
    parameters.query("enabled", enabled_value);
    if (enabled_value != 0 && enabled_value != 1) {
      amrex::Abort("p12.enabled must be 0 or 1");
    }
    result.enabled = enabled_value == 1;
    if (!result.enabled) return result;
    result.integrated_p15 = BMXP15Stage0::enabled();

    if (BMXChemLayout::classifyMeshSpecies(FLUID::chem_species) !=
        BMXChemLayout::MeshMode::enabled) {
      amrex::Abort("P12 uptake requires the enabled P09 three-state layout");
    }
    if (!result.integrated_p15 &&
        BMXPhosphorusGeometry::readInputBinding().enabled) {
      amrex::Abort("P12 uptake-only forbids the P11 divider/window geometry");
    }

    std::string contract;
    std::string contract_hash;
    std::string numerical_contract;
    std::string numerical_contract_hash;
    std::string stage;
    parameters.get("contract", contract);
    parameters.get("contract_sha256", contract_hash);
    parameters.get("numerical_contract", numerical_contract);
    parameters.get("numerical_contract_sha256", numerical_contract_hash);
    parameters.get("stage", stage);
    const std::string expected_numerical_id = result.integrated_p15
        ? BMXP15Stage0::numerical_contract_id : numerical_contract_id;
    const std::string expected_numerical_hash = result.integrated_p15
        ? BMXP15Stage0::numerical_contract_sha256
        : numerical_contract_sha256;
    const std::string expected_stage = result.integrated_p15
        ? BMXP15Stage0::stage_id : stage_id;
    if (contract != contract_id || contract_hash != contract_sha256 ||
        stage != expected_stage) {
      amrex::Abort("P12 contract identity or stage mismatch");
    }
    if (numerical_contract != expected_numerical_id ||
        numerical_contract_hash != expected_numerical_hash) {
      amrex::Abort("P12 numerical preregistration identity mismatch");
    }
    std::string network_hash;
    parameters.get("network_sha256", network_hash);
    const std::string expected_network_hash = result.integrated_p15
        ? BMXP15Stage0::config().initial_network_sha256 : network_sha256;
    if (network_hash != expected_network_hash) {
      amrex::Abort("P12 fixed-network SHA-256 mismatch");
    }
    result.bound_contract_id = contract;
    result.bound_contract_sha256 = contract_hash;
    result.bound_numerical_contract_id = numerical_contract;
    result.bound_numerical_contract_sha256 = numerical_contract_hash;
    result.bound_stage_id = stage;
    result.bound_network_sha256 = network_hash;

    parameters.get("j_max", result.j_max);
    parameters.get("k_m", result.k_m);
    if (!finite(result.j_max) || !finite(result.k_m) ||
        !allowedJmax(result.j_max) || !allowedKm(result.k_m)) {
      amrex::Abort("P12 j_max or k_m is outside the adopted sensitivity set");
    }

    std::string mode;
    parameters.get("area_mode", mode);
    if (mode == "FULL_EXPOSED_EXTRARADICAL_SURFACE") {
      result.area_mode = AreaMode::full_exposed_surface;
    } else if (mode == "ZERO") {
      result.area_mode = AreaMode::zero;
    } else if (mode == "TIP_005") {
      result.area_mode = AreaMode::tip_005;
    } else if (mode == "TIP_010") {
      result.area_mode = AreaMode::tip_010;
    } else if (mode == "TIP_020") {
      result.area_mode = AreaMode::tip_020;
    } else if (mode == "TIP_010_AREA_MATCHED") {
      result.area_mode = AreaMode::tip_010_area_matched;
    } else {
      amrex::Abort("P12 area_mode is not in the adopted contract");
    }
    parameters.query("area_multiplier", result.area_multiplier);
    const bool matched =
        result.area_mode == AreaMode::tip_010_area_matched;
    if (!finite(result.area_multiplier) || result.area_multiplier < 0.0 ||
        (!result.integrated_p15 &&
         result.area_mode != AreaMode::zero &&
         result.area_multiplier != 1.0) ||
        (result.integrated_p15 && !matched &&
         result.area_multiplier != 1.0) ||
        (result.integrated_p15 && matched &&
         !(result.area_multiplier > 0.0))) {
      amrex::Abort("P12 area_multiplier violates the stage-specific area contract");
    }

    amrex::ParmParse chemistry("chem_species");
    // The integrated C13 transaction consumes the same membrane law but then
    // fills the already frozen P13 growth/reaction and later topology slots.
    // Only the C10 uptake-only fixture requires every unrelated mechanism off.
    requiredZero(chemistry, "mass_transfer_P");
    if (!result.integrated_p15) {
      requiredZero(chemistry, "kP");
      requiredZero(chemistry, "krP");
      requiredZero(chemistry, "p_growth_limit");
      requiredZero(chemistry, "kg");
      requiredZero(chemistry, "kv");
      requiredZero(chemistry, "branching_probability");
      requiredZero(chemistry, "splitting_probability");
      requiredZero(chemistry, "fusion_probability");
    }

    if (FLUID::D_k0.size() != BMXChemLayout::enabled_mesh_components ||
        FLUID::D_k0[6] != 0.0) {
      amrex::Abort("P12 requires exactly zero mesh P_F diffusion");
    }
    const amrex::Real d_diffusion = FLUID::D_k0[BMXChemLayout::P_D];
    if (d_diffusion != 0.0 && d_diffusion != 1.0e-7 &&
        d_diffusion != 1.0e-6 && d_diffusion != 5.0e-6 &&
        d_diffusion != 1.0e-5) {
      amrex::Abort("P12 mesh P_D diffusion is outside the adopted set");
    }
    result.mesh_d_diffusivity = d_diffusion;
    if (result.integrated_p15 && d_diffusion != 5.0e-6) {
      amrex::Abort("P15 central Stage 0 requires mesh P_D diffusivity exactly 5e-6 cm^2/s");
    }
    amrex::ParmParse diffusion("diffusion");
    if (!diffusion.contains("rtol")) {
      amrex::Abort("P12 requires an explicit diffusion.rtol engineering guard");
    }
    diffusion.get("rtol", result.solver_rtol);
    diffusion.query("atol", result.solver_atol);
    if (!finite(result.solver_rtol) || result.solver_rtol <= 0.0 ||
        result.solver_rtol > 1.0e-13 || !finite(result.solver_atol) ||
        result.solver_atol != 0.0) {
      amrex::Abort(
          "P12 requires 0 < diffusion.rtol <= 1e-13 and diffusion.atol exactly zero to protect the P10 ledger");
    }

    amrex::Print() << std::setprecision(17)
                   << "P12_CONTRACT classification=USER_ADOPTED_PROVISIONAL_PENDING_MENTOR_OVERRIDE"
                   << " contract=" << result.bound_contract_id
                   << " contract_sha256=" << result.bound_contract_sha256
                   << " numerical_contract="
                   << result.bound_numerical_contract_id
                   << " numerical_contract_sha256="
                   << result.bound_numerical_contract_sha256
                   << " source_sha256=" << authority_source_sha256
                   << " stage=" << result.bound_stage_id
                   << " network_sha256=" << result.bound_network_sha256
                   << " integrated_p15=" << result.integrated_p15
                   << " claim_boundary=" << claim_boundary
                   << " j_max=" << result.j_max
                   << " k_m=" << result.k_m
                   << " mesh_d_diffusivity=" << result.mesh_d_diffusivity
                   << " solver_rtol=" << result.solver_rtol
                   << " solver_atol=" << result.solver_atol
                   << " area_mode=" << mode << '\n';
    return result;
  }

  const Config& config ()
  {
    static const Config value = readAndValidateInput();
    return value;
  }

  bool enabled () { return config().enabled; }

  const CumulativeLedger& cumulativeLedger () { return uptake_ledger; }

  void resetCumulativeLedger () { uptake_ledger = CumulativeLedger{}; }

  void restoreCumulativeLedger (const CumulativeLedger& ledger)
  {
    if (!finite(ledger.requested) || !finite(ledger.accepted) ||
        !finite(ledger.rejected) || !finite(ledger.area_time) ||
        !finite(ledger.minimum_donor_scale) ||
        !finite(ledger.maximum_donor_eta) ||
        ledger.requested < 0.0 || ledger.accepted < 0.0 ||
        ledger.rejected < 0.0 || ledger.area_time < 0.0 ||
        ledger.minimum_donor_scale < 0.0 ||
        ledger.minimum_donor_scale > 1.0 ||
        ledger.maximum_donor_eta < 0.0 ||
        ledger.positive_request_updates > ledger.updates ||
        ledger.zero_inventory_positive_request_updates >
            ledger.positive_request_updates ||
        (ledger.positive_request_updates == 0 &&
         (ledger.minimum_donor_scale != 1.0 ||
          ledger.maximum_donor_eta != 0.0 ||
          ledger.zero_inventory_positive_request_updates != 0)) ||
        ledger.accepted > ledger.requested ||
        std::abs((ledger.requested - ledger.accepted) - ledger.rejected) >
            64.0 * std::numeric_limits<amrex::Real>::epsilon() *
                (std::abs(ledger.requested) + std::abs(ledger.accepted) +
                 std::abs(ledger.rejected))) {
      amrex::Abort("P12 checkpoint contains an invalid uptake ledger");
    }
    uptake_ledger = ledger;
  }

  void recordAcceptedStep (amrex::Real requested,
                           amrex::Real accepted,
                           amrex::Real eligible_area,
                           amrex::Real dt,
                           amrex::Real minimum_donor_scale,
                           amrex::Real maximum_donor_eta,
                           int zero_inventory_positive_request)
  {
    amrex::ParallelDescriptor::ReduceRealSum(requested);
    amrex::ParallelDescriptor::ReduceRealSum(accepted);
    amrex::ParallelDescriptor::ReduceRealSum(eligible_area);
    amrex::ParallelDescriptor::ReduceRealMin(minimum_donor_scale);
    amrex::ParallelDescriptor::ReduceRealMax(maximum_donor_eta);
    amrex::ParallelDescriptor::ReduceIntMax(zero_inventory_positive_request);
    if (requested == 0.0) minimum_donor_scale = 1.0;
    const amrex::Real rejected = requested - accepted;
    if (!finite(requested) || !finite(accepted) || !finite(eligible_area) ||
        !finite(minimum_donor_scale) || !finite(maximum_donor_eta) ||
        requested < 0.0 || accepted < 0.0 || accepted > requested ||
        eligible_area < 0.0 || minimum_donor_scale < 0.0 ||
        minimum_donor_scale > 1.0 || maximum_donor_eta < 0.0 ||
        (zero_inventory_positive_request != 0 &&
         zero_inventory_positive_request != 1) || !(dt > 0.0) ||
        (requested == 0.0 &&
         (accepted != 0.0 || maximum_donor_eta != 0.0 ||
          zero_inventory_positive_request != 0))) {
      amrex::Abort("P12 uptake step produced invalid requested/accepted/area state");
    }
    uptake_ledger.requested += requested;
    uptake_ledger.accepted += accepted;
    uptake_ledger.rejected += rejected;
    uptake_ledger.area_time += eligible_area * dt;
    ++uptake_ledger.updates;
    if (requested > 0.0) {
      uptake_ledger.minimum_donor_scale = std::min(
          uptake_ledger.minimum_donor_scale, minimum_donor_scale);
      uptake_ledger.maximum_donor_eta = std::max(
          uptake_ledger.maximum_donor_eta, maximum_donor_eta);
      ++uptake_ledger.positive_request_updates;
      uptake_ledger.zero_inventory_positive_request_updates +=
          static_cast<std::uint64_t>(zero_inventory_positive_request);
    }
    amrex::Print() << std::setprecision(17)
                   << "P12_UPTAKE update=" << uptake_ledger.updates
                   << " requested=" << requested
                   << " accepted=" << accepted
                   << " rejected=" << rejected
                   << " eligible_area=" << eligible_area
                   << " min_donor_scale=" << minimum_donor_scale
                   << " max_donor_eta=" << maximum_donor_eta
                   << " zero_inventory_positive_request="
                   << zero_inventory_positive_request
                   << " cumulative_requested=" << uptake_ledger.requested
                   << " cumulative_accepted=" << uptake_ledger.accepted
                   << " cumulative_rejected=" << uptake_ledger.rejected
                   << " cumulative_area_time=" << uptake_ledger.area_time
                   << " run_min_donor_scale="
                   << uptake_ledger.minimum_donor_scale
                   << " run_max_donor_eta="
                   << uptake_ledger.maximum_donor_eta
                   << " run_positive_request_updates="
                   << uptake_ledger.positive_request_updates
                   << " run_zero_inventory_positive_request_updates="
                   << uptake_ledger.zero_inventory_positive_request_updates
                   << " E=0 F=0 structural=0 export=0 reward=0 growth=0\n";
  }
}
