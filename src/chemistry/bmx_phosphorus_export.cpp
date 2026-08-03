//
// C12/P14 input binding and persistent export/reward diagnostics.
//
#include <bmx_phosphorus_export_K.H>

#include <AMReX.H>
#include <AMReX_ParallelDescriptor.H>
#include <AMReX_ParmParse.H>
#include <AMReX_Print.H>

#include <bmx_chem_layout.H>
#include <bmx_fluid_parms.H>
#include <bmx_phosphorus_geometry_K.H>
#include <bmx_p15_stage0_K.H>

#include <cmath>
#include <iomanip>
#include <limits>
#include <string>

namespace
{
  BMXPhosphorusExport::CumulativeLedger export_ledger;

  bool allowedExportRate (amrex::Real value)
  {
    return value == 0.0 || value == 1.0e-6 ||
           value == 5.26977773579e-6 || value == 1.0e-5 ||
           value == 1.0e-4;
  }

  bool nearLocal (amrex::Real left, amrex::Real right)
  {
    const amrex::Real scale = std::abs(left) + std::abs(right);
    return std::abs(left-right) <= BMXPhosphorus::localTolerance(scale);
  }

  void addCounter (std::uint64_t& cumulative,
                   amrex::Long increment,
                   const char* name)
  {
    if (increment < 0 ||
        cumulative > std::numeric_limits<std::uint64_t>::max() -
                         static_cast<std::uint64_t>(increment)) {
      amrex::Abort(std::string("P14 cumulative counter overflow: ") + name);
    }
    cumulative += static_cast<std::uint64_t>(increment);
  }

  void validateLedgerAlgebra (
      const BMXPhosphorusExport::CumulativeLedger& ledger,
      const char* context)
  {
    const amrex::Real values[] = {
        ledger.requested_p, ledger.accepted_p, ledger.rejected_p,
        ledger.exported_p, ledger.exchange_derived_a,
        ledger.bootstrap_a_credit, ledger.active_volume,
        ledger.active_d_basis};
    for (const auto value : values) {
      if (!BMXPhosphorusExport::finite(value) || value < 0.0) {
        amrex::Abort(std::string("P14 ") + context +
                     " contains a nonfinite or negative ledger value");
      }
    }
    if (!nearLocal(ledger.requested_p,
                   ledger.accepted_p + ledger.rejected_p) ||
        !nearLocal(ledger.accepted_p, ledger.exported_p) ||
        ledger.exchange_derived_a !=
            BMXPhosphorusExport::reward_molar_multiplier *
                ledger.accepted_p ||
        ledger.bootstrap_a_credit != 0.0 ||
        ledger.eligible_particles > ledger.particles_evaluated ||
        ledger.accepted_export_events > ledger.eligible_particles ||
        ledger.true_crossings > ledger.eligible_particles) {
      amrex::Abort(std::string("P14 ") + context +
                   " violates export, reward, or provenance algebra");
    }
  }
}

namespace BMXPhosphorusExport
{
  Config readAndValidateInput ()
  {
    Config result;
    amrex::ParmParse parameters("p14");
    int enabled_value = 0;
    parameters.query("enabled", enabled_value);
    if (enabled_value != 0 && enabled_value != 1) {
      amrex::Abort("p14.enabled must be 0 or 1");
    }
    result.enabled = enabled_value == 1;
    if (!result.enabled) return result;
    result.integrated_p15 = BMXP15Stage0::enabled();

    if (BMXChemLayout::classifyMeshSpecies(FLUID::chem_species) !=
        BMXChemLayout::MeshMode::enabled) {
      amrex::Abort("P14 requires the enabled P09 three-state layout");
    }
    const auto p11 = BMXPhosphorusGeometry::readInputBinding();
    if (!p11.enabled) {
      amrex::Abort("P14 requires the hash-bound P11 geometry contract");
    }

    std::string contract;
    std::string contract_hash;
    std::string operator_fit;
    std::string operator_fit_hash;
    std::string stage;
    std::string interface_fraction;
    amrex::Real multiplier = 0.0;
    parameters.get("contract", contract);
    parameters.get("contract_sha256", contract_hash);
    parameters.get("operator_fit", operator_fit);
    parameters.get("operator_fit_sha256", operator_fit_hash);
    parameters.get("stage", stage);
    parameters.get("interface_fraction", interface_fraction);
    parameters.get("reward_molar_multiplier", multiplier);
    parameters.get("k_export", result.k_export);
    const std::string expected_stage = result.integrated_p15
        ? BMXP15Stage0::stage_id : stage_id;
    if (contract != contract_id || contract_hash != contract_sha256 ||
        operator_fit != operator_fit_id ||
        operator_fit_hash != operator_fit_sha256 ||
        stage != expected_stage ||
        interface_fraction != interface_fraction_id ||
        multiplier != reward_molar_multiplier) {
      amrex::Abort("P14 contract, O09 fit, interface, reward, or stage identity mismatch");
    }
    result.bound_stage_id = stage;
    if (!finite(result.k_export) || !allowedExportRate(result.k_export)) {
      amrex::Abort("P14 k_export is outside the five adopted levels");
    }

    amrex::Print() << std::setprecision(17)
                   << "P14_CONTRACT classification="
                   << authority_classification
                   << " contract=" << contract_id
                   << " contract_sha256=" << contract_sha256
                   << " operator_fit=" << operator_fit_id
                   << " operator_fit_sha256=" << operator_fit_sha256
                   << " stage=" << result.bound_stage_id
                   << " integrated_p15=" << result.integrated_p15
                   << " global_order=bmx-p10-global-order-v1"
                   << " global_order_changed=0"
                   << " interface_fraction=" << interface_fraction_id
                   << " reward_molar_multiplier="
                   << reward_molar_multiplier
                   << " k_export=" << result.k_export
                   << " F_active=0 claim=SOFTWARE_NUMERICAL_ONLY\n";
    return result;
  }

  const Config& config ()
  {
    static const Config value = readAndValidateInput();
    return value;
  }

  bool enabled () { return config().enabled; }

  const CumulativeLedger& cumulativeLedger () { return export_ledger; }

  void resetCumulativeLedger () { export_ledger = CumulativeLedger{}; }

  void restoreCumulativeLedger (const CumulativeLedger& ledger)
  {
    validateLedgerAlgebra(ledger, "checkpoint");
    export_ledger = ledger;
  }

  void requireUpdateAvailable (int update_id)
  {
    if (update_id < 0 || update_id <= export_ledger.last_update_id) {
      amrex::Abort("P14 rejected a negative, duplicate, or out-of-order update id");
    }
  }

  void recordStep (int update_id,
                   const StepResult& local,
                   std::uint64_t particles_evaluated,
                   std::uint64_t eligible_particles,
                   std::uint64_t true_crossings,
                   std::uint64_t solid_contacts,
                   std::uint64_t accepted_export_events,
                   std::uint64_t donor_capped_events,
                   std::uint64_t roundoff_clamps)
  {
    requireUpdateAvailable(update_id);
    const auto long_max =
        static_cast<std::uint64_t>(std::numeric_limits<amrex::Long>::max());
    const std::uint64_t counters[] = {
        particles_evaluated, eligible_particles, true_crossings,
        solid_contacts, accepted_export_events, donor_capped_events,
        roundoff_clamps};
    for (const auto counter : counters) {
      if (counter > long_max) {
        amrex::Abort("P14 step counter exceeds AMReX MPI reduction range");
      }
    }

    StepResult global = local;
    amrex::Long global_counters[] = {
        static_cast<amrex::Long>(particles_evaluated),
        static_cast<amrex::Long>(eligible_particles),
        static_cast<amrex::Long>(true_crossings),
        static_cast<amrex::Long>(solid_contacts),
        static_cast<amrex::Long>(accepted_export_events),
        static_cast<amrex::Long>(donor_capped_events),
        static_cast<amrex::Long>(roundoff_clamps)};
    amrex::ParallelDescriptor::ReduceRealSum(global.interface_fraction);
    amrex::ParallelDescriptor::ReduceRealSum(global.active_volume);
    amrex::ParallelDescriptor::ReduceRealSum(global.active_d_basis);
    amrex::ParallelDescriptor::ReduceRealSum(global.requested_p);
    amrex::ParallelDescriptor::ReduceRealSum(global.accepted_p);
    amrex::ParallelDescriptor::ReduceRealSum(global.rejected_p);
    amrex::ParallelDescriptor::ReduceRealSum(global.exported_p);
    amrex::ParallelDescriptor::ReduceRealSum(global.reward_a);
    for (auto& counter : global_counters) {
      amrex::ParallelDescriptor::ReduceLongSum(counter);
    }
    int status = static_cast<int>(global.status);
    amrex::ParallelDescriptor::ReduceIntMax(status);
    global.status = static_cast<StepStatus>(status);
    if (global.status != StepStatus::ok) {
      amrex::Abort("P14 transaction reported a non-ok step status");
    }
    if (!nearLocal(global.requested_p,
                   global.accepted_p + global.rejected_p) ||
        !nearLocal(global.accepted_p, global.exported_p) ||
        global.reward_a != reward_molar_multiplier * global.accepted_p) {
      amrex::Abort("P14 step violates export or exact reward algebra");
    }

    export_ledger.requested_p += global.requested_p;
    export_ledger.accepted_p += global.accepted_p;
    export_ledger.rejected_p += global.rejected_p;
    export_ledger.exported_p += global.exported_p;
    export_ledger.exchange_derived_a += global.reward_a;
    export_ledger.active_volume += global.active_volume;
    export_ledger.active_d_basis += global.active_d_basis;
    if (export_ledger.updates ==
        std::numeric_limits<std::uint64_t>::max()) {
      amrex::Abort("P14 cumulative update counter overflow");
    }
    ++export_ledger.updates;
    addCounter(export_ledger.particles_evaluated, global_counters[0],
               "particles_evaluated");
    addCounter(export_ledger.eligible_particles, global_counters[1],
               "eligible_particles");
    addCounter(export_ledger.true_crossings, global_counters[2],
               "true_crossings");
    addCounter(export_ledger.solid_contacts, global_counters[3],
               "solid_contacts");
    addCounter(export_ledger.accepted_export_events, global_counters[4],
               "accepted_export_events");
    addCounter(export_ledger.donor_capped_events, global_counters[5],
               "donor_capped_events");
    addCounter(export_ledger.roundoff_clamps, global_counters[6],
               "roundoff_clamps");
    export_ledger.last_update_id = update_id;
    validateLedgerAlgebra(export_ledger, "cumulative ledger");
    BMXPhosphorus::creditExportedP(global.exported_p);

    amrex::Print() << std::setprecision(17)
                   << "P14_STEP update_id=" << update_id
                   << " interface_fraction_sum="
                   << global.interface_fraction
                   << " active_volume=" << global.active_volume
                   << " active_d_basis=" << global.active_d_basis
                   << " requested_p=" << global.requested_p
                   << " accepted_p=" << global.accepted_p
                   << " rejected_p=" << global.rejected_p
                   << " exported_p=" << global.exported_p
                   << " exchange_derived_a=" << global.reward_a
                   << " bootstrap_a_credit=0"
                   << " particles=" << global_counters[0]
                   << " eligible=" << global_counters[1]
                   << " true_crossings=" << global_counters[2]
                   << " solid_contacts=" << global_counters[3]
                   << " accepted_events=" << global_counters[4]
                   << " donor_capped_events=" << global_counters[5]
                   << " cumulative_exported_p="
                   << export_ledger.exported_p
                   << " cumulative_exchange_derived_a="
                   << export_ledger.exchange_derived_a << '\n';
  }
}
