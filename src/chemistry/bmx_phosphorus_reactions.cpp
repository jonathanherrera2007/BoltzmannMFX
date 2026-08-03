//
// C11/P13 input binding and persistent diagnostics.
//
#include <bmx_phosphorus_reactions_K.H>

#include <AMReX.H>
#include <AMReX_ParallelDescriptor.H>
#include <AMReX_ParmParse.H>
#include <AMReX_Print.H>

#include <bmx_chem_layout.H>
#include <bmx_fluid_parms.H>
#include <bmx_p15_stage0_K.H>

#include <cmath>
#include <iomanip>
#include <limits>
#include <string>

namespace
{
  BMXPhosphorusReactions::CumulativeLedger reaction_ledger;

  bool allowedRatePair (amrex::Real forward, amrex::Real reverse)
  {
    return (forward == 0.0 && reverse == 0.0) ||
           (forward == 1.0e-5 && reverse == 0.0) ||
           (forward == 1.0e-6 && reverse == 1.0e-6) ||
           (forward == 1.0e-5 && reverse == 1.0e-5) ||
           (forward == 1.0e-4 && reverse == 1.0e-4);
  }

  bool allowedQuota (amrex::Real value)
  {
    return value == 3.0e-6 || value == 3.0e-5 || value == 3.0e-4;
  }

  bool allowedGrowthRatio (amrex::Real value)
  {
    return value == 0.1 || value == 1.0 || value == 10.0;
  }
}

namespace BMXPhosphorusReactions
{
  Config readAndValidateInput ()
  {
    Config result;
    amrex::ParmParse parameters("p13");
    int enabled_value = 0;
    parameters.query("enabled", enabled_value);
    if (enabled_value != 0 && enabled_value != 1) {
      amrex::Abort("p13.enabled must be 0 or 1");
    }
    result.enabled = enabled_value == 1;
    if (!result.enabled) return result;
    result.integrated_p15 = BMXP15Stage0::enabled();

    if (BMXChemLayout::classifyMeshSpecies(FLUID::chem_species) !=
        BMXChemLayout::MeshMode::enabled) {
      amrex::Abort("P13 requires the enabled P09 three-state layout");
    }

    std::string contract;
    std::string contract_hash;
    std::string operator_fit;
    std::string operator_fit_hash;
    std::string stage;
    parameters.get("contract", contract);
    parameters.get("contract_sha256", contract_hash);
    parameters.get("operator_fit", operator_fit);
    parameters.get("operator_fit_sha256", operator_fit_hash);
    parameters.get("stage", stage);
    const std::string expected_stage = result.integrated_p15
        ? BMXP15Stage0::stage_id : stage_id;
    if (contract != contract_id || contract_hash != contract_sha256 ||
        operator_fit != operator_fit_id ||
        operator_fit_hash != operator_fit_sha256 ||
        stage != expected_stage) {
      amrex::Abort("P13 contract, O02 fit, or stage identity mismatch");
    }
    result.bound_stage_id = stage;

    int reactions = 0;
    int growth = 0;
    parameters.get("reactions_enabled", reactions);
    parameters.get("growth_enabled", growth);
    if ((reactions != 0 && reactions != 1) ||
        (growth != 0 && growth != 1)) {
      amrex::Abort("P13 reaction/growth enabled fields must be 0 or 1");
    }
    result.reactions_enabled = reactions == 1;
    result.growth_enabled = growth == 1;
    parameters.get("k_de", result.k_de);
    parameters.get("k_ed", result.k_ed);
    parameters.get("q_p", result.q_p);
    parameters.get("k_gP_over_k_gB", result.k_gp_over_k_gb);

    if (!finite(result.k_de) || !finite(result.k_ed) ||
        !allowedRatePair(result.k_de, result.k_ed) ||
        (!result.reactions_enabled &&
         (result.k_de != 0.0 || result.k_ed != 0.0))) {
      amrex::Abort("P13 D/E rates are outside the adopted sensitivity set");
    }
    if (result.growth_enabled) {
      if (!finite(result.q_p) || !finite(result.k_gp_over_k_gb) ||
          !allowedQuota(result.q_p) ||
          !allowedGrowthRatio(result.k_gp_over_k_gb)) {
        amrex::Abort("P13 q_p or k_gP/k_gB is outside the adopted sensitivity set");
      }
    } else if (result.q_p != 0.0 || result.k_gp_over_k_gb != 0.0) {
      amrex::Abort("disabled P13 growth requires q_p and k_gP/k_gB exactly zero");
    }

    amrex::ParmParse chemistry("chem_species");
    amrex::Real legacy_growth_limit = 0.0;
    amrex::Real legacy_qp = 0.0;
    amrex::Real legacy_kp = 0.0;
    amrex::Real legacy_krp = 0.0;
    amrex::Real legacy_transfer = 0.0;
    chemistry.query("p_growth_limit", legacy_growth_limit);
    chemistry.query("qP", legacy_qp);
    chemistry.query("kP", legacy_kp);
    chemistry.query("krP", legacy_krp);
    chemistry.query("mass_transfer_P", legacy_transfer);
    if (legacy_growth_limit != 0.0 || legacy_qp != 0.0 ||
        legacy_kp != 0.0 || legacy_krp != 0.0 || legacy_transfer != 0.0) {
      amrex::Abort("P13 requires every superseded legacy inert-P operator exactly zero");
    }

    amrex::Print() << std::setprecision(17)
                   << "P13_CONTRACT classification="
                   << authority_classification
                   << " contract=" << contract_id
                   << " contract_sha256=" << contract_sha256
                   << " operator_fit=" << operator_fit_id
                   << " operator_fit_sha256=" << operator_fit_sha256
                   << " stage=" << result.bound_stage_id
                   << " integrated_p15=" << result.integrated_p15
                   << " global_order=bmx-p10-global-order-v1"
                   << " global_order_changed=0"
                   << " source_sha256=" << authority_source_sha256
                   << " reactions_enabled=" << reactions
                   << " growth_enabled=" << growth
                   << " k_de=" << result.k_de
                   << " k_ed=" << result.k_ed
                   << " q_p=" << result.q_p
                   << " k_gP_over_k_gB=" << result.k_gp_over_k_gb
                   << " F_active=0 claim=SOFTWARE_NUMERICAL_ONLY\n";
    return result;
  }

  const Config& config ()
  {
    static const Config value = readAndValidateInput();
    return value;
  }

  bool enabled () { return config().enabled; }

  const CumulativeLedger& cumulativeLedger () { return reaction_ledger; }

  void resetCumulativeLedger () { reaction_ledger = CumulativeLedger{}; }

  void restoreCumulativeLedger (const CumulativeLedger& ledger)
  {
    const amrex::Real values[] = {
        ledger.reaction_forward, ledger.reaction_reverse,
        ledger.carbon_supported_growth,
        ledger.phosphorus_supported_growth, ledger.requested_growth,
        ledger.accepted_growth, ledger.rejected_growth, ledger.b_debit,
        ledger.e_debit, ledger.structuralized_p};
    for (const auto value : values) {
      if (!finite(value) || value < 0.0) {
        amrex::Abort("P13 checkpoint contains a nonfinite or negative ledger value");
      }
    }
    const amrex::Real growth_scale =
        std::abs(ledger.requested_growth) +
        std::abs(ledger.accepted_growth) +
        std::abs(ledger.rejected_growth);
    const amrex::Real structural_scale =
        std::abs(ledger.e_debit) + std::abs(ledger.structuralized_p);
    if (std::abs((ledger.requested_growth - ledger.accepted_growth) -
                 ledger.rejected_growth) >
            BMXPhosphorus::localTolerance(growth_scale) ||
        std::abs(ledger.e_debit - ledger.structuralized_p) >
            BMXPhosphorus::localTolerance(structural_scale) ||
        ledger.accepted_growth_events > ledger.particles_evaluated) {
      amrex::Abort("P13 checkpoint ledger violates its algebraic identities");
    }
    reaction_ledger = ledger;
  }

  void recordStep (const StepResult& local,
                   std::uint64_t particles_evaluated,
                   std::uint64_t accepted_growth_events,
                   std::uint64_t roundoff_clamps)
  {
    const auto long_max =
        static_cast<std::uint64_t>(std::numeric_limits<amrex::Long>::max());
    if (particles_evaluated > long_max ||
        accepted_growth_events > long_max || roundoff_clamps > long_max) {
      amrex::Abort("P13 step counter exceeds AMReX MPI reduction range");
    }
    amrex::Long particles_evaluated_global =
        static_cast<amrex::Long>(particles_evaluated);
    amrex::Long accepted_growth_events_global =
        static_cast<amrex::Long>(accepted_growth_events);
    amrex::Long roundoff_clamps_global =
        static_cast<amrex::Long>(roundoff_clamps);

    StepResult global = local;
    amrex::ParallelDescriptor::ReduceRealSum(global.reaction_forward);
    amrex::ParallelDescriptor::ReduceRealSum(global.reaction_reverse);
    amrex::ParallelDescriptor::ReduceRealSum(global.carbon_supported_growth);
    amrex::ParallelDescriptor::ReduceRealSum(
        global.phosphorus_supported_growth);
    amrex::ParallelDescriptor::ReduceRealSum(global.requested_growth);
    amrex::ParallelDescriptor::ReduceRealSum(global.accepted_growth);
    amrex::ParallelDescriptor::ReduceRealSum(global.rejected_growth);
    amrex::ParallelDescriptor::ReduceRealSum(global.b_debit);
    amrex::ParallelDescriptor::ReduceRealSum(global.e_debit);
    amrex::ParallelDescriptor::ReduceRealSum(global.structuralized_p);
    amrex::ParallelDescriptor::ReduceLongSum(particles_evaluated_global);
    amrex::ParallelDescriptor::ReduceLongSum(accepted_growth_events_global);
    amrex::ParallelDescriptor::ReduceLongSum(roundoff_clamps_global);

    if (global.status != StepStatus::ok) {
      amrex::Abort("P13 transaction reported a non-ok step status");
    }
    const amrex::Real growth_scale =
        std::abs(global.requested_growth) +
        std::abs(global.accepted_growth) +
        std::abs(global.rejected_growth);
    const amrex::Real structural_scale =
        std::abs(global.e_debit) + std::abs(global.structuralized_p);
    if (std::abs((global.requested_growth - global.accepted_growth) -
                 global.rejected_growth) >
            BMXPhosphorus::localTolerance(growth_scale) ||
        std::abs(global.e_debit - global.structuralized_p) >
            BMXPhosphorus::localTolerance(structural_scale)) {
      amrex::Abort("P13 step violates growth or structuralization conservation");
    }

    reaction_ledger.reaction_forward += global.reaction_forward;
    reaction_ledger.reaction_reverse += global.reaction_reverse;
    reaction_ledger.carbon_supported_growth +=
        global.carbon_supported_growth;
    reaction_ledger.phosphorus_supported_growth +=
        global.phosphorus_supported_growth;
    reaction_ledger.requested_growth += global.requested_growth;
    reaction_ledger.accepted_growth += global.accepted_growth;
    reaction_ledger.rejected_growth += global.rejected_growth;
    reaction_ledger.b_debit += global.b_debit;
    reaction_ledger.e_debit += global.e_debit;
    reaction_ledger.structuralized_p += global.structuralized_p;
    ++reaction_ledger.updates;
    reaction_ledger.particles_evaluated +=
        static_cast<std::uint64_t>(particles_evaluated_global);
    reaction_ledger.accepted_growth_events +=
        static_cast<std::uint64_t>(accepted_growth_events_global);
    reaction_ledger.roundoff_clamps +=
        static_cast<std::uint64_t>(roundoff_clamps_global);
    BMXPhosphorus::creditStructuralP(global.structuralized_p);

    amrex::Print() << std::setprecision(17)
                   << "P13_STEP update=" << reaction_ledger.updates
                   << " reaction_forward=" << global.reaction_forward
                   << " reaction_reverse=" << global.reaction_reverse
                   << " carbon_supported_growth="
                   << global.carbon_supported_growth
                   << " phosphorus_supported_growth="
                   << global.phosphorus_supported_growth
                   << " requested_growth=" << global.requested_growth
                   << " accepted_growth=" << global.accepted_growth
                   << " rejected_growth=" << global.rejected_growth
                   << " b_debit=" << global.b_debit
                   << " e_debit=" << global.e_debit
                   << " structuralized_p=" << global.structuralized_p
                   << " particles=" << particles_evaluated_global
                   << " accepted_events=" << accepted_growth_events_global
                   << " roundoff_clamps=" << roundoff_clamps_global
                   << " cumulative_reaction_forward="
                   << reaction_ledger.reaction_forward
                   << " cumulative_reaction_reverse="
                   << reaction_ledger.reaction_reverse
                   << " cumulative_requested_growth="
                   << reaction_ledger.requested_growth
                   << " cumulative_accepted_growth="
                   << reaction_ledger.accepted_growth
                   << " cumulative_rejected_growth="
                   << reaction_ledger.rejected_growth
                   << " cumulative_b_debit=" << reaction_ledger.b_debit
                   << " cumulative_e_debit=" << reaction_ledger.e_debit
                   << " cumulative_structuralized_p="
                   << reaction_ledger.structuralized_p
                   << " cumulative_particles="
                   << reaction_ledger.particles_evaluated
                   << " cumulative_accepted_events="
                   << reaction_ledger.accepted_growth_events
                   << " cumulative_roundoff_clamps="
                   << reaction_ledger.roundoff_clamps << '\n';
  }
}
