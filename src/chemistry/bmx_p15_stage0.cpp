//
// C13/P15 Stage 0 input binding and persistent graph diagnostics.
//
#include <bmx_p15_stage0_K.H>

#include <AMReX.H>
#include <AMReX_ParallelDescriptor.H>
#include <AMReX_ParmParse.H>
#include <AMReX_Print.H>

#include <bmx_chem_layout.H>
#include <bmx_fluid_parms.H>
#include <bmx_pc_phosphorus.H>

#include <cmath>
#include <iomanip>
#include <limits>
#include <string>

namespace
{
  BMXP15Stage0::AreaMatchState area_match_state{};
  BMXP15Stage0::TerminalLedger terminal_ledger{};
  BMXP15Stage0::BondedLedger bonded_ledger{};

  bool hexadecimalHash (const std::string& value, std::size_t length)
  {
    if (value.size() != length) return false;
    for (const char character : value) {
      const bool digit = character >= '0' && character <= '9';
      const bool lower = character >= 'a' && character <= 'f';
      if (!digit && !lower) return false;
    }
    return true;
  }

  bool allowedDiffusivity (amrex::Real value)
  {
    return value == 0.0 || value == 1.25e-7 || value == 1.25e-6 ||
           value == 1.25e-5;
  }

  bool nearLocal (amrex::Real first, amrex::Real second)
  {
    const amrex::Real scale = std::abs(first) + std::abs(second);
    return std::abs(first-second) <= BMXPhosphorus::localTolerance(scale);
  }

  void validateAreaMatch (const BMXP15Stage0::AreaMatchState& state,
                          const char* context)
  {
    if (state.bound != 0 && state.bound != 1) {
      amrex::Abort(std::string("P15 ") + context +
                   " area-match bound flag must be 0 or 1");
    }
    const amrex::Real values[] = {
        state.multiplier, state.initial_full_area,
        state.initial_tip010_area};
    for (const amrex::Real value : values) {
      if (!BMXP15Stage0::finite(value) || value < 0.0) {
        amrex::Abort(std::string("P15 ") + context +
                     " area-match state is nonfinite or negative");
      }
    }
    if ((state.bound == 0 &&
         (state.multiplier != 0.0 || state.initial_full_area != 0.0 ||
          state.initial_tip010_area != 0.0)) ||
        (state.bound == 1 &&
         (!(state.multiplier > 0.0) ||
          !(state.initial_full_area > 0.0) ||
          !(state.initial_tip010_area > 0.0) ||
          state.multiplier !=
              state.initial_full_area/state.initial_tip010_area))) {
      amrex::Abort(std::string("P15 ") + context +
                   " area-match algebra is invalid");
    }
  }

  void validateTerminal (const BMXP15Stage0::TerminalLedger& ledger,
                         const char* context)
  {
    const amrex::Real values[] = {
        ledger.current_full_area, ledger.current_tip_005_area,
        ledger.current_tip_010_area, ledger.current_tip_020_area,
        ledger.current_effective_area};
    for (const amrex::Real value : values) {
      if (!BMXP15Stage0::finite(value) || value < 0.0) {
        amrex::Abort(std::string("P15 ") + context +
                     " terminal ledger is nonfinite or negative");
      }
    }
    if (ledger.current_tip_005_area > ledger.current_tip_010_area ||
        ledger.current_tip_010_area > ledger.current_tip_020_area ||
        ledger.current_tip_020_area > ledger.current_full_area) {
      amrex::Abort(std::string("P15 ") + context +
                   " terminal areas are not nested");
    }
  }

  void validateBonded (const BMXP15Stage0::BondedLedger& ledger,
                       const char* context)
  {
    const amrex::Real values[] = {
        ledger.requested, ledger.accepted, ledger.rejected,
        ledger.gross_absolute_accepted, ledger.maximum_diagonal_rate,
        ledger.minimum_donor_scale};
    for (const amrex::Real value : values) {
      if (!BMXP15Stage0::finite(value) || value < 0.0) {
        amrex::Abort(std::string("P15 ") + context +
                     " bonded ledger is nonfinite or negative");
      }
    }
    if (ledger.minimum_donor_scale > 1.0 ||
        !nearLocal(ledger.requested,
                   ledger.accepted + ledger.rejected) ||
        !nearLocal(ledger.accepted,
                   ledger.gross_absolute_accepted)) {
      amrex::Abort(std::string("P15 ") + context +
                   " bonded ledger algebra is invalid");
    }
  }
}

namespace BMXP15Stage0
{
  Config readAndValidateInput ()
  {
    Config result;
    amrex::ParmParse parameters("p15");
    int enabled_value = 0;
    parameters.query("enabled", enabled_value);
    if (enabled_value != 0 && enabled_value != 1) {
      amrex::Abort("p15.enabled must be 0 or 1");
    }
    result.enabled = enabled_value == 1;
    if (!result.enabled) return result;

    if (BMXChemLayout::classifyMeshSpecies(FLUID::chem_species) !=
        BMXChemLayout::MeshMode::enabled) {
      amrex::Abort("P15 Stage 0 requires the enabled P09 three-state layout");
    }

    std::string binding;
    std::string binding_hash;
    std::string bonded;
    std::string bonded_hash;
    std::string numerical;
    std::string numerical_hash;
    std::string terminal;
    std::string terminal_hash;
    std::string fit;
    std::string fit_hash;
    std::string stage;
    parameters.get("binding_contract", binding);
    parameters.get("binding_contract_sha256", binding_hash);
    parameters.get("bonded_contract", bonded);
    parameters.get("bonded_contract_sha256", bonded_hash);
    parameters.get("numerical_contract", numerical);
    parameters.get("numerical_contract_sha256", numerical_hash);
    parameters.get("terminal_contract", terminal);
    parameters.get("terminal_contract_sha256", terminal_hash);
    parameters.get("operator_fit", fit);
    parameters.get("operator_fit_sha256", fit_hash);
    parameters.get("stage", stage);
    if (binding != binding_contract_id ||
        binding_hash != binding_contract_sha256 ||
        bonded != bonded_contract_id ||
        bonded_hash != bonded_contract_sha256 ||
        numerical != numerical_contract_id ||
        numerical_hash != numerical_contract_sha256 ||
        terminal != terminal_contract_id ||
        terminal_hash != terminal_contract_sha256 ||
        fit != operator_fit_id || fit_hash != operator_fit_sha256 ||
        stage != stage_id) {
      amrex::Abort("P15 Stage 0 contract, operator-fit, or stage identity mismatch");
    }

    parameters.get("bonded_d_diffusivity", result.bonded_d_diffusivity);
    if (!finite(result.bonded_d_diffusivity) ||
        !allowedDiffusivity(result.bonded_d_diffusivity)) {
      amrex::Abort("P15 bonded_d_diffusivity is outside the adopted set");
    }
    int cap_fault = 0;
    int outcomes = 0;
    parameters.query("cap_fault_injection", cap_fault);
    parameters.query("qualification_outcomes_enabled", outcomes);
    if ((cap_fault != 0 && cap_fault != 1) ||
        (outcomes != 0 && outcomes != 1)) {
      amrex::Abort("P15 Boolean controls must be 0 or 1");
    }
    result.cap_fault_injection = cap_fault == 1;
    result.qualification_outcomes_enabled = outcomes == 1;

    parameters.get("initial_network_sha256", result.initial_network_sha256);
    parameters.get("generated_configuration_sha256",
                   result.generated_configuration_sha256);
    if (!hexadecimalHash(result.initial_network_sha256, 64) ||
        !hexadecimalHash(result.generated_configuration_sha256, 64)) {
      amrex::Abort("P15 initial-network or generated-configuration SHA-256 is invalid");
    }
    parameters.query("expected_area_match_multiplier",
                     result.expected_area_match_multiplier);
    parameters.query("expected_initial_full_area",
                     result.expected_initial_full_area);
    parameters.query("expected_initial_tip010_area",
                     result.expected_initial_tip010_area);
    const amrex::Real area_values[] = {
        result.expected_area_match_multiplier,
        result.expected_initial_full_area,
        result.expected_initial_tip010_area};
    for (const auto value : area_values) {
      if (!finite(value) || value < 0.0) {
        amrex::Abort("P15 expected area-match fields must be finite and nonnegative");
      }
    }

    parameters.query("independent_review_status",
                     result.independent_review_status);
    parameters.query("independent_review_sha256",
                     result.independent_review_sha256);
    parameters.query("reviewed_source_commit",
                     result.reviewed_source_commit);
    if (result.qualification_outcomes_enabled &&
        (result.independent_review_status != "PASS" ||
         !hexadecimalHash(result.independent_review_sha256, 64) ||
         !hexadecimalHash(result.reviewed_source_commit, 40))) {
      amrex::Abort(
          "P15 216-hour qualification outcomes remain prohibited pending a hash-bound independent PASS review of the frozen source");
    }
    if (result.cap_fault_injection && result.qualification_outcomes_enabled) {
      amrex::Abort("P15 bonded-D cap fault injection is prohibited in qualification outcomes");
    }

    amrex::Print() << std::setprecision(17)
                   << "P15_STAGE0 classification="
                   << authority_classification
                   << " binding_contract=" << binding_contract_id
                   << " binding_contract_sha256="
                   << binding_contract_sha256
                   << " bonded_contract=" << bonded_contract_id
                   << " bonded_contract_sha256="
                   << bonded_contract_sha256
                   << " numerical_contract=" << numerical_contract_id
                   << " numerical_contract_sha256="
                   << numerical_contract_sha256
                   << " terminal_contract=" << terminal_contract_id
                   << " terminal_contract_sha256="
                   << terminal_contract_sha256
                   << " operator_fit=" << operator_fit_id
                   << " operator_fit_sha256=" << operator_fit_sha256
                   << " global_order=" << global_order_id
                   << " global_order_sha256=" << global_order_sha256
                   << " global_order_changed=0 frozen_kernel_changed=0"
                   << " source_sha256=" << authority_source_sha256
                   << " initial_network_sha256="
                   << result.initial_network_sha256
                   << " generated_configuration_sha256="
                   << result.generated_configuration_sha256
                   << " bonded_d_diffusivity="
                   << result.bonded_d_diffusivity
                   << " qualification_outcomes_enabled="
                   << outcomes
                   << " claim_boundary=" << claim_boundary << '\n';
    return result;
  }

  const Config& config ()
  {
    static const Config value = readAndValidateInput();
    return value;
  }

  bool enabled () { return config().enabled; }

  const AreaMatchState& areaMatchState () { return area_match_state; }
  const TerminalLedger& terminalLedger () { return terminal_ledger; }
  const BondedLedger& bondedLedger () { return bonded_ledger; }

  void resetRuntimeState ()
  {
    area_match_state = AreaMatchState{};
    terminal_ledger = TerminalLedger{};
    bonded_ledger = BondedLedger{};
  }

  void restoreRuntimeState (const AreaMatchState& area_match,
                            const TerminalLedger& terminal,
                            const BondedLedger& bonded)
  {
    validateAreaMatch(area_match, "checkpoint");
    validateTerminal(terminal, "checkpoint");
    validateBonded(bonded, "checkpoint");
    if (!config().enabled &&
        (area_match.bound != 0 || terminal.updates != 0 ||
         bonded.updates != 0)) {
      amrex::Abort("P15 disabled restart contains enabled P15 runtime state");
    }
    area_match_state = area_match;
    terminal_ledger = terminal;
    bonded_ledger = bonded;
  }

  void bindAreaMatch (const AreaMatchState& state)
  {
    validateAreaMatch(state, "initial");
    if (state.bound != 1) {
      amrex::Abort("P15 initial area-match binding must be bound");
    }
    if (area_match_state.bound) {
      if (area_match_state.multiplier != state.multiplier ||
          area_match_state.initial_full_area != state.initial_full_area ||
          area_match_state.initial_tip010_area !=
              state.initial_tip010_area) {
        amrex::Abort("P15 area-match state cannot be rebound");
      }
      return;
    }
    area_match_state = state;
  }

  void recordTerminalSnapshot (amrex::Real full_area,
                               amrex::Real tip_005_area,
                               amrex::Real tip_010_area,
                               amrex::Real tip_020_area,
                               amrex::Real effective_area,
                               std::uint64_t segments,
                               std::uint64_t live_terminal_origins)
  {
    TerminalLedger next = terminal_ledger;
    next.current_full_area = full_area;
    next.current_tip_005_area = tip_005_area;
    next.current_tip_010_area = tip_010_area;
    next.current_tip_020_area = tip_020_area;
    next.current_effective_area = effective_area;
    next.segments = segments;
    next.live_terminal_origins = live_terminal_origins;
    ++next.updates;
    validateTerminal(next, "runtime");
    terminal_ledger = next;
    amrex::Print() << std::setprecision(17)
                   << "P15_TERMINAL update=" << next.updates
                   << " segments=" << next.segments
                   << " live_terminal_origins="
                   << next.live_terminal_origins
                   << " physical_full_area=" << next.current_full_area
                   << " physical_tip005_area="
                   << next.current_tip_005_area
                   << " physical_tip010_area="
                   << next.current_tip_010_area
                   << " physical_tip020_area="
                   << next.current_tip_020_area
                   << " effective_uptake_area="
                   << next.current_effective_area << '\n';
  }

  void recordBondedStep (const BondedStep& local)
  {
    BondedStep step = local;
    auto requireIdentical = [] (amrex::Real& value, const char* field)
    {
      amrex::Real minimum = value;
      amrex::Real maximum = value;
      amrex::ParallelDescriptor::ReduceRealMin(minimum);
      amrex::ParallelDescriptor::ReduceRealMax(maximum);
      if (minimum != maximum) {
        amrex::Abort(std::string("P15 canonical MPI mismatch in ") + field);
      }
      value = minimum;
    };
    requireIdentical(step.requested, "bonded requested");
    requireIdentical(step.accepted, "bonded accepted");
    requireIdentical(step.rejected, "bonded rejected");
    requireIdentical(step.gross_absolute_accepted,
                     "bonded gross absolute accepted");
    requireIdentical(step.maximum_diagonal_rate,
                     "bonded maximum diagonal rate");
    requireIdentical(step.minimum_donor_scale,
                     "bonded minimum donor scale");
    amrex::Long substeps = static_cast<amrex::Long>(step.internal_substeps);
    amrex::Long pairs = static_cast<amrex::Long>(step.virtual_pairs);
    amrex::Long caps = static_cast<amrex::Long>(step.material_cap_activations);
    amrex::Long substeps_min = substeps;
    amrex::Long substeps_max = substeps;
    amrex::Long pairs_min = pairs;
    amrex::Long pairs_max = pairs;
    amrex::Long caps_min = caps;
    amrex::Long caps_max = caps;
    amrex::ParallelDescriptor::ReduceLongMin(substeps_min);
    amrex::ParallelDescriptor::ReduceLongMax(substeps_max);
    amrex::ParallelDescriptor::ReduceLongMin(pairs_min);
    amrex::ParallelDescriptor::ReduceLongMax(pairs_max);
    amrex::ParallelDescriptor::ReduceLongMin(caps_min);
    amrex::ParallelDescriptor::ReduceLongMax(caps_max);
    if (substeps_min != substeps_max || pairs_min != pairs_max ||
        caps_min != caps_max) {
      amrex::Abort("P15 canonical MPI mismatch in bonded integer ledger");
    }

    const amrex::Real values[] = {
        step.requested, step.accepted, step.rejected,
        step.gross_absolute_accepted, step.maximum_diagonal_rate,
        step.minimum_donor_scale};
    for (const auto value : values) {
      if (!finite(value) || value < 0.0) {
        amrex::Abort("P15 bonded step contains nonfinite or negative state");
      }
    }
    if (step.minimum_donor_scale > 1.0 ||
        !nearLocal(step.requested, step.accepted + step.rejected) ||
        !nearLocal(step.accepted, step.gross_absolute_accepted)) {
      amrex::Abort("P15 bonded step violates requested/accepted/rejected algebra");
    }
    if (step.material_cap_activations > 0 &&
        !config().cap_fault_injection) {
      amrex::Abort("BONDED_D_CAP_ACTIVATED");
    }

    bonded_ledger.requested += step.requested;
    bonded_ledger.accepted += step.accepted;
    bonded_ledger.rejected += step.rejected;
    bonded_ledger.gross_absolute_accepted +=
        step.gross_absolute_accepted;
    bonded_ledger.maximum_diagonal_rate = amrex::max(
        bonded_ledger.maximum_diagonal_rate,
        step.maximum_diagonal_rate);
    bonded_ledger.minimum_donor_scale = amrex::min(
        bonded_ledger.minimum_donor_scale,
        step.minimum_donor_scale);
    ++bonded_ledger.updates;
    bonded_ledger.internal_substeps += step.internal_substeps;
    bonded_ledger.virtual_pairs += step.virtual_pairs;
    bonded_ledger.material_cap_activations +=
        step.material_cap_activations;
    validateBonded(bonded_ledger, "runtime");

    amrex::Print() << std::setprecision(17)
                   << "P15_BONDED_D update=" << bonded_ledger.updates
                   << " internal_substeps=" << step.internal_substeps
                   << " virtual_pairs=" << step.virtual_pairs
                   << " requested=" << step.requested
                   << " accepted=" << step.accepted
                   << " rejected=" << step.rejected
                   << " gross_absolute_accepted="
                   << step.gross_absolute_accepted
                   << " maximum_diagonal_rate="
                   << step.maximum_diagonal_rate
                   << " minimum_donor_scale="
                   << step.minimum_donor_scale
                   << " material_cap_activations="
                   << step.material_cap_activations
                   << " cumulative_requested=" << bonded_ledger.requested
                   << " cumulative_accepted=" << bonded_ledger.accepted
                   << " cumulative_rejected=" << bonded_ledger.rejected
                   << " cumulative_gross_absolute_accepted="
                   << bonded_ledger.gross_absolute_accepted << '\n';
  }
}
