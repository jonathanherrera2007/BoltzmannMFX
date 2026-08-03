//
//     Copyright (c) 2013 Battelle Memorial Institute
//     Licensed under modified BSD License. A copy of this license can be found
//     in the LICENSE file in the top level directory of this distribution.
//
#include "bmx_checkpoint_schema.H"

#include <AMReX.H>

#include <bmx_pc_phosphorus.H>
#include <bmx_phosphorus_export_K.H>
#include <bmx_phosphorus_geometry_K.H>
#include <bmx_phosphorus_reactions_K.H>
#include <bmx_phosphorus_uptake_K.H>
#include <bmx_p15_stage0_K.H>

#include <cmath>
#include <cstdint>
#include <iomanip>
#include <limits>
#include <sstream>
#include <type_traits>

namespace
{
  [[noreturn]] void reject (const std::string& reason)
  {
    amrex::Abort(
        "P09 checkpoint rejected before particle deserialization: " + reason);
  }

  std::string readLine (std::istream& stream, const char* description)
  {
    std::string line;
    if (!std::getline(stream, line)) {
      reject(std::string("missing ") + description);
    }
    return line;
  }

  template <typename T>
  T readValue (std::istream& stream, const char* expected_key)
  {
    const std::string line = readLine(stream, expected_key);
    std::istringstream values(line);
    std::string key;
    T value{};
    if (!(values >> key) || key != expected_key || !(values >> value)) {
      reject(std::string("malformed or missing field ") + expected_key);
    }
    values >> std::ws;
    if (!values.eof()) {
      reject(std::string("unexpected trailing data in field ") + expected_key);
    }
    return value;
  }

  std::uint64_t readUnsignedValue (std::istream& stream,
                                   const char* expected_key)
  {
    const std::string token = readValue<std::string>(stream, expected_key);
    if (token.empty()) {
      reject(std::string("malformed unsigned field ") + expected_key);
    }
    std::uint64_t value = 0;
    for (const char character : token) {
      if (character < '0' || character > '9') {
        reject(std::string("malformed unsigned field ") + expected_key);
      }
      const std::uint64_t digit =
          static_cast<std::uint64_t>(character - '0');
      if (value > (std::numeric_limits<std::uint64_t>::max() - digit) / 10) {
        reject(std::string("unsigned field out of range ") + expected_key);
      }
      value = value * 10 + digit;
    }
    return value;
  }

  void requireToken (std::istream& stream,
                     const char* key,
                     const std::string& expected)
  {
    const std::string actual = readValue<std::string>(stream, key);
    if (actual != expected) {
      reject(std::string(key) + " mismatch: expected " + expected +
             ", found " + actual);
    }
  }

  std::vector<std::string> particleNames (
      BMXChemLayout::MeshMode mode,
      const std::vector<std::string>& mesh_names)
  {
    std::vector<std::string> result;
    result.reserve(BMXChemLayout::particle_components);
    if (mode == BMXChemLayout::MeshMode::enabled ||
        mode == BMXChemLayout::MeshMode::disabled) {
      for (int component = 0;
           component < BMXChemLayout::particle_components;
           ++component) {
        result.emplace_back(BMXChemLayout::particleName(mode, component));
      }
      return result;
    }
    for (int component = 0;
         component < BMXChemLayout::particle_components;
         ++component) {
      if (component < static_cast<int>(mesh_names.size())) {
        result.push_back(mesh_names[component]);
      } else {
        result.push_back("reserved_component_" + std::to_string(component));
      }
    }
    return result;
  }

  void writeNames (std::ostream& stream,
                   const char* key,
                   const std::vector<std::string>& names)
  {
    stream << key;
    for (const auto& name : names) stream << ' ' << name;
    stream << '\n';
  }

  void readNames (std::istream& stream,
                  const char* key,
                  const std::vector<std::string>& expected)
  {
    const std::string line = readLine(stream, key);
    std::istringstream values(line);
    std::string actual_key;
    if (!(values >> actual_key) || actual_key != key) {
      reject(std::string("malformed or missing field ") + key);
    }
    for (const auto& expected_name : expected) {
      std::string actual_name;
      if (!(values >> actual_name) || actual_name != expected_name) {
        reject(std::string(key) + " mismatch");
      }
    }
    values >> std::ws;
    if (!values.eof()) reject(std::string(key) + " has extra components");
  }

  void validateMode (BMXChemLayout::MeshMode mode)
  {
    if (mode == BMXChemLayout::MeshMode::invalid) {
      reject("runtime mesh layout is invalid");
    }
    if (!BMXChemLayout::checkpoint_schema_ready) {
      reject("compiled checkpoint schema is not ready");
    }
  }
}

namespace BMXCheckpointSchema
{
  void validateVersionLine (const std::string& line)
  {
    if (line != version_line) {
      reject(std::string("expected '") + version_line + "', found '" + line + "'");
    }
  }

  void writeMetadata (std::ostream& stream,
                      BMXChemLayout::MeshMode mode,
                      const std::vector<std::string>& mesh_names,
                      const amrex::Geometry& geometry)
  {
    validateMode(mode);
    const auto particle_names = particleNames(mode, mesh_names);
    const auto& ledger = BMXPhosphorus::cumulativeLedger();
    const auto geometry_binding =
        BMXPhosphorusGeometry::readInputBinding();
    const auto geometry_config =
        BMXPhosphorusGeometry::loadAndValidate(geometry, mesh_names);

    stream << "BMX_SCHEMA_V8_BEGIN\n";
    stream << "mesh_mode " << BMXChemLayout::modeName(mode) << '\n';
    stream << "mesh_component_count " << mesh_names.size() << '\n';
    writeNames(stream, "mesh_component_names", mesh_names);
    stream << "particle_component_count "
           << BMXChemLayout::particle_components << '\n';
    writeNames(stream, "particle_component_names", particle_names);
    stream << "particle_block_count " << BMXChemLayout::particle_blocks << '\n';
    stream << "layout_id " << BMXChemLayout::layout_id << '\n';
    stream << "layout_hash_sha256 " << BMXChemLayout::layout_hash_sha256 << '\n';
    stream << "operator_order_id " << BMXChemLayout::operator_order_id << '\n';
    stream << "operator_order_contract_sha256 "
           << BMXChemLayout::operator_order_contract_sha256 << '\n';
    stream << "topology_event_contract_id "
           << BMXChemLayout::topology_event_contract_id << '\n';
    stream << "topology_event_contract_sha256 "
           << BMXChemLayout::topology_event_contract_sha256 << '\n';
    stream << "units_contract_id " << BMXChemLayout::units_contract_id << '\n';
    stream << "units_decision_source_sha256 "
           << BMXChemLayout::units_decision_source_sha256 << '\n';
    stream << "decision_contract_id "
           << BMXChemLayout::decision_contract_id << '\n';
    stream << "decision_contract_sha256 "
           << BMXChemLayout::decision_contract_sha256 << '\n';
    stream << "global_ledger_schema_id "
           << BMXChemLayout::global_ledger_schema_id << '\n';
    stream << "global_ledger_schema_sha256 "
           << BMXChemLayout::global_ledger_schema_sha256 << '\n';
    stream << std::setprecision(17);
    stream << "p11_geometry_enabled "
           << (geometry_binding.enabled ? 1 : 0) << '\n';
    stream << "p11_geometry_schema_version "
           << (geometry_binding.enabled ? geometry_binding.version : 0) << '\n';
    stream << "p11_geometry_contract_id "
           << (geometry_binding.enabled
                   ? geometry_binding.contract
                   : std::string("DISABLED")) << '\n';
    stream << "p11_geometry_contract_sha256 "
           << (geometry_binding.enabled
                   ? BMXPhosphorusGeometry::contract_sha256
                   : "DISABLED") << '\n';
    stream << "p11_geometry_stage "
           << (geometry_binding.enabled
                   ? geometry_binding.stage
                   : std::string("DISABLED")) << '\n';
    static const char* const direction_names[AMREX_SPACEDIM] =
        {"x", "y", "z"};
    for (int direction = 0; direction < AMREX_SPACEDIM; ++direction) {
      stream << "p11_geometry_prob_lo_" << direction_names[direction]
             << ' ' << geometry_config.prob_lo[direction] << '\n';
      stream << "p11_geometry_prob_hi_" << direction_names[direction]
             << ' ' << geometry_config.prob_hi[direction] << '\n';
      stream << "p11_geometry_periodic_" << direction_names[direction]
             << ' ' << geometry.isPeriodic(direction) << '\n';
    }
    const auto& uptake_config = BMXPhosphorusUptake::config();
    const auto& uptake_ledger = BMXPhosphorusUptake::cumulativeLedger();
    stream << "p12_uptake_enabled " << (uptake_config.enabled ? 1 : 0) << '\n';
    stream << "p12_uptake_schema_version "
           << (uptake_config.enabled ? BMXPhosphorusUptake::schema_version : 0)
           << '\n';
    stream << "p12_uptake_contract_id "
           << (uptake_config.enabled ? uptake_config.bound_contract_id
                                     : "DISABLED") << '\n';
    stream << "p12_uptake_contract_sha256 "
           << (uptake_config.enabled ? uptake_config.bound_contract_sha256
                                      : "DISABLED") << '\n';
    stream << "p12_numerical_contract_id "
           << (uptake_config.enabled
                    ? uptake_config.bound_numerical_contract_id
                   : "DISABLED") << '\n';
    stream << "p12_numerical_contract_sha256 "
           << (uptake_config.enabled
                    ? uptake_config.bound_numerical_contract_sha256
                   : "DISABLED") << '\n';
    stream << "p12_uptake_stage "
           << (uptake_config.enabled ? uptake_config.bound_stage_id
                                     : "DISABLED") << '\n';
    stream << "p12_uptake_network_sha256 "
           << (uptake_config.enabled ? uptake_config.bound_network_sha256
                                     : "DISABLED") << '\n';
    stream << "p12_uptake_j_max " << uptake_config.j_max << '\n';
    stream << "p12_uptake_k_m " << uptake_config.k_m << '\n';
    stream << "p12_uptake_area_mode "
           << static_cast<int>(uptake_config.area_mode) << '\n';
    stream << "p12_uptake_area_multiplier "
           << uptake_config.area_multiplier << '\n';
    stream << "p12_uptake_mesh_d_diffusivity "
           << uptake_config.mesh_d_diffusivity << '\n';
    stream << "p12_uptake_solver_rtol " << uptake_config.solver_rtol << '\n';
    stream << "p12_uptake_solver_atol " << uptake_config.solver_atol << '\n';
    stream << "p12_uptake_cumulative_requested "
           << uptake_ledger.requested << '\n';
    stream << "p12_uptake_cumulative_accepted "
           << uptake_ledger.accepted << '\n';
    stream << "p12_uptake_cumulative_rejected "
           << uptake_ledger.rejected << '\n';
    stream << "p12_uptake_cumulative_area_time "
           << uptake_ledger.area_time << '\n';
    stream << "p12_uptake_run_minimum_donor_scale "
           << uptake_ledger.minimum_donor_scale << '\n';
    stream << "p12_uptake_run_maximum_donor_eta "
           << uptake_ledger.maximum_donor_eta << '\n';
    stream << "p12_uptake_updates " << uptake_ledger.updates << '\n';
    stream << "p12_uptake_positive_request_updates "
           << uptake_ledger.positive_request_updates << '\n';
    stream << "p12_uptake_zero_inventory_positive_request_updates "
           << uptake_ledger.zero_inventory_positive_request_updates << '\n';
    const auto& reaction_config = BMXPhosphorusReactions::config();
    const auto& reaction_ledger =
        BMXPhosphorusReactions::cumulativeLedger();
    stream << "p13_enabled " << (reaction_config.enabled ? 1 : 0) << '\n';
    stream << "p13_schema_version "
           << (reaction_config.enabled
                   ? BMXPhosphorusReactions::schema_version
                   : 0) << '\n';
    stream << "p13_contract_id "
           << (reaction_config.enabled
                   ? BMXPhosphorusReactions::contract_id
                   : "DISABLED") << '\n';
    stream << "p13_contract_sha256 "
           << (reaction_config.enabled
                   ? BMXPhosphorusReactions::contract_sha256
                   : "DISABLED") << '\n';
    stream << "p13_operator_fit_id "
           << (reaction_config.enabled
                   ? BMXPhosphorusReactions::operator_fit_id
                   : "DISABLED") << '\n';
    stream << "p13_operator_fit_sha256 "
           << (reaction_config.enabled
                   ? BMXPhosphorusReactions::operator_fit_sha256
                   : "DISABLED") << '\n';
    stream << "p13_stage "
           << (reaction_config.enabled
                    ? reaction_config.bound_stage_id
                   : "DISABLED") << '\n';
    stream << "p13_reactions_enabled "
           << (reaction_config.reactions_enabled ? 1 : 0) << '\n';
    stream << "p13_growth_enabled "
           << (reaction_config.growth_enabled ? 1 : 0) << '\n';
    stream << "p13_k_de " << reaction_config.k_de << '\n';
    stream << "p13_k_ed " << reaction_config.k_ed << '\n';
    stream << "p13_q_p " << reaction_config.q_p << '\n';
    stream << "p13_k_gP_over_k_gB "
           << reaction_config.k_gp_over_k_gb << '\n';
    stream << "p13_cumulative_reaction_forward "
           << reaction_ledger.reaction_forward << '\n';
    stream << "p13_cumulative_reaction_reverse "
           << reaction_ledger.reaction_reverse << '\n';
    stream << "p13_cumulative_carbon_supported_growth "
           << reaction_ledger.carbon_supported_growth << '\n';
    stream << "p13_cumulative_phosphorus_supported_growth "
           << reaction_ledger.phosphorus_supported_growth << '\n';
    stream << "p13_cumulative_requested_growth "
           << reaction_ledger.requested_growth << '\n';
    stream << "p13_cumulative_accepted_growth "
           << reaction_ledger.accepted_growth << '\n';
    stream << "p13_cumulative_rejected_growth "
           << reaction_ledger.rejected_growth << '\n';
    stream << "p13_cumulative_b_debit "
           << reaction_ledger.b_debit << '\n';
    stream << "p13_cumulative_e_debit "
           << reaction_ledger.e_debit << '\n';
    stream << "p13_cumulative_structuralized_p "
           << reaction_ledger.structuralized_p << '\n';
    stream << "p13_updates " << reaction_ledger.updates << '\n';
    stream << "p13_particles_evaluated "
           << reaction_ledger.particles_evaluated << '\n';
    stream << "p13_accepted_growth_events "
           << reaction_ledger.accepted_growth_events << '\n';
    stream << "p13_roundoff_clamps "
           << reaction_ledger.roundoff_clamps << '\n';
    const auto& export_config = BMXPhosphorusExport::config();
    const auto& export_ledger = BMXPhosphorusExport::cumulativeLedger();
    stream << "p14_enabled " << (export_config.enabled ? 1 : 0) << '\n';
    stream << "p14_schema_version "
           << (export_config.enabled ? BMXPhosphorusExport::schema_version : 0)
           << '\n';
    stream << "p14_contract_id "
           << (export_config.enabled ? BMXPhosphorusExport::contract_id
                                     : "DISABLED") << '\n';
    stream << "p14_contract_sha256 "
           << (export_config.enabled ? BMXPhosphorusExport::contract_sha256
                                     : "DISABLED") << '\n';
    stream << "p14_operator_fit_id "
           << (export_config.enabled ? BMXPhosphorusExport::operator_fit_id
                                     : "DISABLED") << '\n';
    stream << "p14_operator_fit_sha256 "
           << (export_config.enabled
                   ? BMXPhosphorusExport::operator_fit_sha256
                   : "DISABLED") << '\n';
    stream << "p14_stage "
           << (export_config.enabled ? export_config.bound_stage_id
                                     : "DISABLED") << '\n';
    stream << "p14_interface_fraction "
           << (export_config.enabled
                   ? BMXPhosphorusExport::interface_fraction_id
                   : "DISABLED") << '\n';
    stream << "p14_reward_molar_multiplier "
           << (export_config.enabled
                   ? BMXPhosphorusExport::reward_molar_multiplier
                   : 0.0) << '\n';
    stream << "p14_k_export " << export_config.k_export << '\n';
    stream << "p14_cumulative_requested_p "
           << export_ledger.requested_p << '\n';
    stream << "p14_cumulative_accepted_p "
           << export_ledger.accepted_p << '\n';
    stream << "p14_cumulative_rejected_p "
           << export_ledger.rejected_p << '\n';
    stream << "p14_cumulative_exported_p "
           << export_ledger.exported_p << '\n';
    stream << "p14_cumulative_exchange_derived_a "
           << export_ledger.exchange_derived_a << '\n';
    stream << "p14_cumulative_bootstrap_a_credit "
           << export_ledger.bootstrap_a_credit << '\n';
    stream << "p14_cumulative_active_volume "
           << export_ledger.active_volume << '\n';
    stream << "p14_cumulative_active_d_basis "
           << export_ledger.active_d_basis << '\n';
    stream << "p14_updates " << export_ledger.updates << '\n';
    stream << "p14_particles_evaluated "
           << export_ledger.particles_evaluated << '\n';
    stream << "p14_eligible_particles "
           << export_ledger.eligible_particles << '\n';
    stream << "p14_true_crossings " << export_ledger.true_crossings << '\n';
    stream << "p14_solid_contacts " << export_ledger.solid_contacts << '\n';
    stream << "p14_accepted_export_events "
           << export_ledger.accepted_export_events << '\n';
    stream << "p14_donor_capped_events "
           << export_ledger.donor_capped_events << '\n';
    stream << "p14_roundoff_clamps "
           << export_ledger.roundoff_clamps << '\n';
    stream << "p14_last_update_id " << export_ledger.last_update_id << '\n';
    const auto& p15_config = BMXP15Stage0::config();
    const auto& p15_area_match = BMXP15Stage0::areaMatchState();
    const auto& p15_terminal = BMXP15Stage0::terminalLedger();
    const auto& p15_bonded = BMXP15Stage0::bondedLedger();
    stream << "p15_enabled " << (p15_config.enabled ? 1 : 0) << '\n';
    stream << "p15_schema_version "
           << (p15_config.enabled ? BMXP15Stage0::schema_version : 0) << '\n';
    stream << "p15_binding_contract_id "
           << (p15_config.enabled ? BMXP15Stage0::binding_contract_id
                                  : "DISABLED") << '\n';
    stream << "p15_binding_contract_sha256 "
           << (p15_config.enabled ? BMXP15Stage0::binding_contract_sha256
                                  : "DISABLED") << '\n';
    stream << "p15_bonded_contract_id "
           << (p15_config.enabled ? BMXP15Stage0::bonded_contract_id
                                  : "DISABLED") << '\n';
    stream << "p15_bonded_contract_sha256 "
           << (p15_config.enabled ? BMXP15Stage0::bonded_contract_sha256
                                  : "DISABLED") << '\n';
    stream << "p15_numerical_contract_id "
           << (p15_config.enabled ? BMXP15Stage0::numerical_contract_id
                                  : "DISABLED") << '\n';
    stream << "p15_numerical_contract_sha256 "
           << (p15_config.enabled ? BMXP15Stage0::numerical_contract_sha256
                                  : "DISABLED") << '\n';
    stream << "p15_terminal_contract_id "
           << (p15_config.enabled ? BMXP15Stage0::terminal_contract_id
                                  : "DISABLED") << '\n';
    stream << "p15_terminal_contract_sha256 "
           << (p15_config.enabled ? BMXP15Stage0::terminal_contract_sha256
                                  : "DISABLED") << '\n';
    stream << "p15_operator_fit_id "
           << (p15_config.enabled ? BMXP15Stage0::operator_fit_id
                                  : "DISABLED") << '\n';
    stream << "p15_operator_fit_sha256 "
           << (p15_config.enabled ? BMXP15Stage0::operator_fit_sha256
                                  : "DISABLED") << '\n';
    stream << "p15_stage "
           << (p15_config.enabled ? BMXP15Stage0::stage_id : "DISABLED")
           << '\n';
    stream << "p15_authority_source_sha256 "
           << (p15_config.enabled ? BMXP15Stage0::authority_source_sha256
                                  : "DISABLED") << '\n';
    stream << "p15_global_order_id "
           << (p15_config.enabled ? BMXP15Stage0::global_order_id
                                  : "DISABLED") << '\n';
    stream << "p15_global_order_sha256 "
           << (p15_config.enabled ? BMXP15Stage0::global_order_sha256
                                  : "DISABLED") << '\n';
    stream << "p15_bonded_d_diffusivity "
           << p15_config.bonded_d_diffusivity << '\n';
    stream << "p15_cap_fault_injection "
           << (p15_config.cap_fault_injection ? 1 : 0) << '\n';
    stream << "p15_qualification_outcomes_enabled "
           << (p15_config.qualification_outcomes_enabled ? 1 : 0) << '\n';
    stream << "p15_initial_network_sha256 "
           << (p15_config.enabled ? p15_config.initial_network_sha256
                                  : "DISABLED") << '\n';
    stream << "p15_generated_configuration_sha256 "
           << (p15_config.enabled
                   ? p15_config.generated_configuration_sha256
                   : "DISABLED") << '\n';
    stream << "p15_independent_review_status "
           << (p15_config.enabled ? p15_config.independent_review_status
                                  : "DISABLED") << '\n';
    stream << "p15_independent_review_sha256 "
           << (p15_config.enabled ? p15_config.independent_review_sha256
                                  : "DISABLED") << '\n';
    stream << "p15_reviewed_source_commit "
           << (p15_config.enabled ? p15_config.reviewed_source_commit
                                  : "DISABLED") << '\n';
    stream << "p15_expected_area_match_multiplier "
           << p15_config.expected_area_match_multiplier << '\n';
    stream << "p15_expected_initial_full_area "
           << p15_config.expected_initial_full_area << '\n';
    stream << "p15_expected_initial_tip010_area "
           << p15_config.expected_initial_tip010_area << '\n';
    stream << "p15_area_match_bound " << p15_area_match.bound << '\n';
    stream << "p15_area_match_multiplier "
           << p15_area_match.multiplier << '\n';
    stream << "p15_area_match_initial_full_area "
           << p15_area_match.initial_full_area << '\n';
    stream << "p15_area_match_initial_tip010_area "
           << p15_area_match.initial_tip010_area << '\n';
    stream << "p15_terminal_current_full_area "
           << p15_terminal.current_full_area << '\n';
    stream << "p15_terminal_current_tip005_area "
           << p15_terminal.current_tip_005_area << '\n';
    stream << "p15_terminal_current_tip010_area "
           << p15_terminal.current_tip_010_area << '\n';
    stream << "p15_terminal_current_tip020_area "
           << p15_terminal.current_tip_020_area << '\n';
    stream << "p15_terminal_current_effective_area "
           << p15_terminal.current_effective_area << '\n';
    stream << "p15_terminal_updates " << p15_terminal.updates << '\n';
    stream << "p15_terminal_segments " << p15_terminal.segments << '\n';
    stream << "p15_terminal_live_terminal_origins "
           << p15_terminal.live_terminal_origins << '\n';
    stream << "p15_bonded_cumulative_requested "
           << p15_bonded.requested << '\n';
    stream << "p15_bonded_cumulative_accepted "
           << p15_bonded.accepted << '\n';
    stream << "p15_bonded_cumulative_rejected "
           << p15_bonded.rejected << '\n';
    stream << "p15_bonded_cumulative_gross_absolute_accepted "
           << p15_bonded.gross_absolute_accepted << '\n';
    stream << "p15_bonded_maximum_diagonal_rate "
           << p15_bonded.maximum_diagonal_rate << '\n';
    stream << "p15_bonded_minimum_donor_scale "
           << p15_bonded.minimum_donor_scale << '\n';
    stream << "p15_bonded_updates " << p15_bonded.updates << '\n';
    stream << "p15_bonded_internal_substeps "
           << p15_bonded.internal_substeps << '\n';
    stream << "p15_bonded_virtual_pairs "
           << p15_bonded.virtual_pairs << '\n';
    stream << "p15_bonded_material_cap_activations "
           << p15_bonded.material_cap_activations << '\n';
    stream << "ledger_reference_bound " << (ledger.reference_bound ? 1 : 0) << '\n';
    stream << "ledger_reference_total_p " << ledger.reference_total_p << '\n';
    stream << "ledger_structural_p " << ledger.structural_p << '\n';
    stream << "ledger_exported_p " << ledger.exported_p << '\n';
    stream << "ledger_other_exit_d " << ledger.other_exits.d << '\n';
    stream << "ledger_other_exit_e " << ledger.other_exits.e << '\n';
    stream << "ledger_other_exit_f " << ledger.other_exits.f << '\n';
    stream << "ledger_other_exit_events " << ledger.other_exit_events << '\n';
    stream << "BMX_SCHEMA_V8_END\n";
  }

  GeometryMetadata readValidateAndRestoreMetadata (
      std::istream& stream,
      BMXChemLayout::MeshMode expected_mode,
      const std::vector<std::string>& expected_mesh_names,
      const amrex::Geometry& runtime_geometry)
  {
    validateMode(expected_mode);
    if (readLine(stream, "BMX schema begin marker") != "BMX_SCHEMA_V8_BEGIN") {
      reject("missing BMX_SCHEMA_V8_BEGIN marker");
    }
    requireToken(stream, "mesh_mode", BMXChemLayout::modeName(expected_mode));
    const auto mesh_count =
        readUnsignedValue(stream, "mesh_component_count");
    if (mesh_count != expected_mesh_names.size()) {
      reject("mesh_component_count mismatch");
    }
    readNames(stream, "mesh_component_names", expected_mesh_names);
    const auto particle_count =
        readUnsignedValue(stream, "particle_component_count");
    if (particle_count != BMXChemLayout::particle_components) {
      reject("particle_component_count mismatch");
    }
    readNames(stream, "particle_component_names",
              particleNames(expected_mode, expected_mesh_names));
    const auto block_count =
        readUnsignedValue(stream, "particle_block_count");
    if (block_count != BMXChemLayout::particle_blocks) {
      reject("particle_block_count mismatch");
    }
    requireToken(stream, "layout_id", BMXChemLayout::layout_id);
    requireToken(stream, "layout_hash_sha256",
                 BMXChemLayout::layout_hash_sha256);
    requireToken(stream, "operator_order_id",
                 BMXChemLayout::operator_order_id);
    requireToken(stream, "operator_order_contract_sha256",
                 BMXChemLayout::operator_order_contract_sha256);
    requireToken(stream, "topology_event_contract_id",
                 BMXChemLayout::topology_event_contract_id);
    requireToken(stream, "topology_event_contract_sha256",
                 BMXChemLayout::topology_event_contract_sha256);
    requireToken(stream, "units_contract_id",
                 BMXChemLayout::units_contract_id);
    requireToken(stream, "units_decision_source_sha256",
                 BMXChemLayout::units_decision_source_sha256);
    requireToken(stream, "decision_contract_id",
                 BMXChemLayout::decision_contract_id);
    requireToken(stream, "decision_contract_sha256",
                 BMXChemLayout::decision_contract_sha256);
    requireToken(stream, "global_ledger_schema_id",
                 BMXChemLayout::global_ledger_schema_id);
    requireToken(stream, "global_ledger_schema_sha256",
                 BMXChemLayout::global_ledger_schema_sha256);

    const auto runtime_binding =
        BMXPhosphorusGeometry::readInputBinding();
    const auto runtime_config =
        BMXPhosphorusGeometry::loadAndValidate(
            runtime_geometry, expected_mesh_names);
    GeometryMetadata geometry_metadata;
    geometry_metadata.enabled =
        readValue<int>(stream, "p11_geometry_enabled");
    if (geometry_metadata.enabled != 0 && geometry_metadata.enabled != 1) {
      reject("p11_geometry_enabled must be 0 or 1");
    }
    if ((geometry_metadata.enabled == 1) != runtime_binding.enabled) {
      reject("p11 geometry enabled state mismatch");
    }
    geometry_metadata.schema =
        readValue<int>(stream, "p11_geometry_schema_version");
    geometry_metadata.contract_id =
        readValue<std::string>(stream, "p11_geometry_contract_id");
    geometry_metadata.contract_sha256 =
        readValue<std::string>(stream, "p11_geometry_contract_sha256");
    geometry_metadata.stage =
        readValue<std::string>(stream, "p11_geometry_stage");
    if (runtime_binding.enabled) {
      if (geometry_metadata.schema != BMXPhosphorusGeometry::schema_version ||
          geometry_metadata.contract_id != BMXPhosphorusGeometry::contract_id ||
          geometry_metadata.contract_sha256 !=
              BMXPhosphorusGeometry::contract_sha256 ||
          geometry_metadata.stage != BMXPhosphorusGeometry::stage_id) {
        reject("P11 geometry contract identity mismatch");
      }
    } else if (geometry_metadata.schema != 0 ||
               geometry_metadata.contract_id != "DISABLED" ||
               geometry_metadata.contract_sha256 != "DISABLED" ||
               geometry_metadata.stage != "DISABLED") {
      reject("disabled P11 geometry metadata is not canonical");
    }
    static const char* const direction_names[AMREX_SPACEDIM] =
        {"x", "y", "z"};
    for (int direction = 0; direction < AMREX_SPACEDIM; ++direction) {
      const std::string suffix = direction_names[direction];
      geometry_metadata.prob_lo[direction] =
          readValue<amrex::Real>(
              stream, ("p11_geometry_prob_lo_" + suffix).c_str());
      geometry_metadata.prob_hi[direction] =
          readValue<amrex::Real>(
              stream, ("p11_geometry_prob_hi_" + suffix).c_str());
      geometry_metadata.periodic[direction] =
          readValue<int>(
              stream, ("p11_geometry_periodic_" + suffix).c_str());
      if (!std::isfinite(geometry_metadata.prob_lo[direction]) ||
          !std::isfinite(geometry_metadata.prob_hi[direction]) ||
          geometry_metadata.prob_lo[direction] !=
              runtime_config.prob_lo[direction] ||
          geometry_metadata.prob_hi[direction] !=
              runtime_config.prob_hi[direction] ||
          geometry_metadata.periodic[direction] !=
              runtime_geometry.isPeriodic(direction)) {
        reject("P11 geometry domain or periodicity mismatch");
      }
    }

    const auto& runtime_uptake = BMXPhosphorusUptake::config();
    const int uptake_enabled = readValue<int>(stream, "p12_uptake_enabled");
    if (uptake_enabled != 0 && uptake_enabled != 1) {
      reject("p12_uptake_enabled must be 0 or 1");
    }
    if ((uptake_enabled == 1) != runtime_uptake.enabled) {
      reject("P12 uptake enabled state mismatch");
    }
    const int uptake_schema =
        readValue<int>(stream, "p12_uptake_schema_version");
    const auto uptake_contract =
        readValue<std::string>(stream, "p12_uptake_contract_id");
    const auto uptake_hash =
        readValue<std::string>(stream, "p12_uptake_contract_sha256");
    const auto uptake_numerical_contract =
        readValue<std::string>(stream, "p12_numerical_contract_id");
    const auto uptake_numerical_hash =
        readValue<std::string>(stream, "p12_numerical_contract_sha256");
    const auto uptake_stage =
        readValue<std::string>(stream, "p12_uptake_stage");
    const auto uptake_network_hash =
        readValue<std::string>(stream, "p12_uptake_network_sha256");
    const auto uptake_j_max =
        readValue<amrex::Real>(stream, "p12_uptake_j_max");
    const auto uptake_k_m =
        readValue<amrex::Real>(stream, "p12_uptake_k_m");
    const int uptake_area_mode =
        readValue<int>(stream, "p12_uptake_area_mode");
    const auto uptake_area_multiplier =
        readValue<amrex::Real>(stream, "p12_uptake_area_multiplier");
    const auto uptake_mesh_d_diffusivity = readValue<amrex::Real>(
        stream, "p12_uptake_mesh_d_diffusivity");
    const auto uptake_solver_rtol =
        readValue<amrex::Real>(stream, "p12_uptake_solver_rtol");
    const auto uptake_solver_atol =
        readValue<amrex::Real>(stream, "p12_uptake_solver_atol");
    if (runtime_uptake.enabled) {
      if (uptake_schema != BMXPhosphorusUptake::schema_version ||
          uptake_contract != runtime_uptake.bound_contract_id ||
          uptake_hash != runtime_uptake.bound_contract_sha256 ||
          uptake_numerical_contract !=
              runtime_uptake.bound_numerical_contract_id ||
          uptake_numerical_hash !=
              runtime_uptake.bound_numerical_contract_sha256 ||
          uptake_stage != runtime_uptake.bound_stage_id ||
          uptake_network_hash != runtime_uptake.bound_network_sha256 ||
          uptake_j_max != runtime_uptake.j_max ||
          uptake_k_m != runtime_uptake.k_m ||
          uptake_area_mode != static_cast<int>(runtime_uptake.area_mode) ||
          uptake_area_multiplier != runtime_uptake.area_multiplier ||
          uptake_mesh_d_diffusivity != runtime_uptake.mesh_d_diffusivity ||
          uptake_solver_rtol != runtime_uptake.solver_rtol ||
          uptake_solver_atol != runtime_uptake.solver_atol) {
        reject("P12 uptake contract or parameter identity mismatch");
      }
    } else if (uptake_schema != 0 || uptake_contract != "DISABLED" ||
               uptake_hash != "DISABLED" ||
               uptake_numerical_contract != "DISABLED" ||
               uptake_numerical_hash != "DISABLED" ||
               uptake_stage != "DISABLED" ||
               uptake_network_hash != "DISABLED" ||
               uptake_j_max != 0.0 || uptake_k_m != 0.0 ||
               uptake_area_mode != 0 || uptake_area_multiplier != 1.0 ||
               uptake_mesh_d_diffusivity != 0.0 ||
               uptake_solver_rtol != 0.0 || uptake_solver_atol != 0.0) {
      reject("disabled P12 uptake metadata is not canonical");
    }
    BMXPhosphorusUptake::CumulativeLedger uptake_ledger;
    uptake_ledger.requested = readValue<amrex::Real>(
        stream, "p12_uptake_cumulative_requested");
    uptake_ledger.accepted = readValue<amrex::Real>(
        stream, "p12_uptake_cumulative_accepted");
    uptake_ledger.rejected = readValue<amrex::Real>(
        stream, "p12_uptake_cumulative_rejected");
    uptake_ledger.area_time = readValue<amrex::Real>(
        stream, "p12_uptake_cumulative_area_time");
    uptake_ledger.minimum_donor_scale = readValue<amrex::Real>(
        stream, "p12_uptake_run_minimum_donor_scale");
    uptake_ledger.maximum_donor_eta = readValue<amrex::Real>(
        stream, "p12_uptake_run_maximum_donor_eta");
    uptake_ledger.updates = readUnsignedValue(stream, "p12_uptake_updates");
    uptake_ledger.positive_request_updates = readUnsignedValue(
        stream, "p12_uptake_positive_request_updates");
    uptake_ledger.zero_inventory_positive_request_updates =
        readUnsignedValue(
            stream, "p12_uptake_zero_inventory_positive_request_updates");
    if (!runtime_uptake.enabled &&
        (uptake_ledger.requested != 0.0 || uptake_ledger.accepted != 0.0 ||
          uptake_ledger.rejected != 0.0 || uptake_ledger.area_time != 0.0 ||
          uptake_ledger.minimum_donor_scale != 1.0 ||
          uptake_ledger.maximum_donor_eta != 0.0 ||
          uptake_ledger.updates != 0 ||
          uptake_ledger.positive_request_updates != 0 ||
          uptake_ledger.zero_inventory_positive_request_updates != 0)) {
      reject("disabled P12 cumulative uptake ledger is not canonical zero");
    }
    BMXPhosphorusUptake::restoreCumulativeLedger(uptake_ledger);

    const auto& runtime_reaction = BMXPhosphorusReactions::config();
    const int reaction_enabled = readValue<int>(stream, "p13_enabled");
    if (reaction_enabled != 0 && reaction_enabled != 1) {
      reject("p13_enabled must be 0 or 1");
    }
    if ((reaction_enabled == 1) != runtime_reaction.enabled) {
      reject("P13 enabled state mismatch");
    }
    const int reaction_schema =
        readValue<int>(stream, "p13_schema_version");
    const auto reaction_contract =
        readValue<std::string>(stream, "p13_contract_id");
    const auto reaction_contract_hash =
        readValue<std::string>(stream, "p13_contract_sha256");
    const auto reaction_operator_fit =
        readValue<std::string>(stream, "p13_operator_fit_id");
    const auto reaction_operator_fit_hash =
        readValue<std::string>(stream, "p13_operator_fit_sha256");
    const auto reaction_stage =
        readValue<std::string>(stream, "p13_stage");
    const int reactions_active =
        readValue<int>(stream, "p13_reactions_enabled");
    const int growth_active =
        readValue<int>(stream, "p13_growth_enabled");
    const auto reaction_k_de = readValue<amrex::Real>(stream, "p13_k_de");
    const auto reaction_k_ed = readValue<amrex::Real>(stream, "p13_k_ed");
    const auto reaction_q_p = readValue<amrex::Real>(stream, "p13_q_p");
    const auto reaction_growth_ratio =
        readValue<amrex::Real>(stream, "p13_k_gP_over_k_gB");
    if (runtime_reaction.enabled) {
      if (reaction_schema != BMXPhosphorusReactions::schema_version ||
          reaction_contract != BMXPhosphorusReactions::contract_id ||
          reaction_contract_hash !=
              BMXPhosphorusReactions::contract_sha256 ||
          reaction_operator_fit !=
              BMXPhosphorusReactions::operator_fit_id ||
          reaction_operator_fit_hash !=
              BMXPhosphorusReactions::operator_fit_sha256 ||
          reaction_stage != runtime_reaction.bound_stage_id ||
          reactions_active !=
              (runtime_reaction.reactions_enabled ? 1 : 0) ||
          growth_active != (runtime_reaction.growth_enabled ? 1 : 0) ||
          reaction_k_de != runtime_reaction.k_de ||
          reaction_k_ed != runtime_reaction.k_ed ||
          reaction_q_p != runtime_reaction.q_p ||
          reaction_growth_ratio != runtime_reaction.k_gp_over_k_gb) {
        reject("P13 contract, O02 fit, or parameter identity mismatch");
      }
    } else if (reaction_schema != 0 ||
               reaction_contract != "DISABLED" ||
               reaction_contract_hash != "DISABLED" ||
               reaction_operator_fit != "DISABLED" ||
               reaction_operator_fit_hash != "DISABLED" ||
               reaction_stage != "DISABLED" || reactions_active != 0 ||
               growth_active != 0 || reaction_k_de != 0.0 ||
               reaction_k_ed != 0.0 || reaction_q_p != 0.0 ||
               reaction_growth_ratio != 0.0) {
      reject("disabled P13 metadata is not canonical");
    }
    BMXPhosphorusReactions::CumulativeLedger reaction_ledger;
    reaction_ledger.reaction_forward = readValue<amrex::Real>(
        stream, "p13_cumulative_reaction_forward");
    reaction_ledger.reaction_reverse = readValue<amrex::Real>(
        stream, "p13_cumulative_reaction_reverse");
    reaction_ledger.carbon_supported_growth = readValue<amrex::Real>(
        stream, "p13_cumulative_carbon_supported_growth");
    reaction_ledger.phosphorus_supported_growth = readValue<amrex::Real>(
        stream, "p13_cumulative_phosphorus_supported_growth");
    reaction_ledger.requested_growth = readValue<amrex::Real>(
        stream, "p13_cumulative_requested_growth");
    reaction_ledger.accepted_growth = readValue<amrex::Real>(
        stream, "p13_cumulative_accepted_growth");
    reaction_ledger.rejected_growth = readValue<amrex::Real>(
        stream, "p13_cumulative_rejected_growth");
    reaction_ledger.b_debit = readValue<amrex::Real>(
        stream, "p13_cumulative_b_debit");
    reaction_ledger.e_debit = readValue<amrex::Real>(
        stream, "p13_cumulative_e_debit");
    reaction_ledger.structuralized_p = readValue<amrex::Real>(
        stream, "p13_cumulative_structuralized_p");
    reaction_ledger.updates = readUnsignedValue(stream, "p13_updates");
    reaction_ledger.particles_evaluated =
        readUnsignedValue(stream, "p13_particles_evaluated");
    reaction_ledger.accepted_growth_events =
        readUnsignedValue(stream, "p13_accepted_growth_events");
    reaction_ledger.roundoff_clamps =
        readUnsignedValue(stream, "p13_roundoff_clamps");
    if (!runtime_reaction.enabled &&
        (reaction_ledger.reaction_forward != 0.0 ||
         reaction_ledger.reaction_reverse != 0.0 ||
         reaction_ledger.carbon_supported_growth != 0.0 ||
         reaction_ledger.phosphorus_supported_growth != 0.0 ||
         reaction_ledger.requested_growth != 0.0 ||
         reaction_ledger.accepted_growth != 0.0 ||
         reaction_ledger.rejected_growth != 0.0 ||
         reaction_ledger.b_debit != 0.0 ||
         reaction_ledger.e_debit != 0.0 ||
         reaction_ledger.structuralized_p != 0.0 ||
         reaction_ledger.updates != 0 ||
         reaction_ledger.particles_evaluated != 0 ||
         reaction_ledger.accepted_growth_events != 0 ||
         reaction_ledger.roundoff_clamps != 0)) {
      reject("disabled P13 cumulative ledger is not canonical zero");
    }
    BMXPhosphorusReactions::restoreCumulativeLedger(reaction_ledger);

    const auto& runtime_export = BMXPhosphorusExport::config();
    const int export_enabled = readValue<int>(stream, "p14_enabled");
    if (export_enabled != 0 && export_enabled != 1) {
      reject("p14_enabled must be 0 or 1");
    }
    if ((export_enabled == 1) != runtime_export.enabled) {
      reject("P14 enabled state mismatch");
    }
    const int export_schema =
        readValue<int>(stream, "p14_schema_version");
    const auto export_contract =
        readValue<std::string>(stream, "p14_contract_id");
    const auto export_contract_hash =
        readValue<std::string>(stream, "p14_contract_sha256");
    const auto export_operator_fit =
        readValue<std::string>(stream, "p14_operator_fit_id");
    const auto export_operator_fit_hash =
        readValue<std::string>(stream, "p14_operator_fit_sha256");
    const auto export_stage =
        readValue<std::string>(stream, "p14_stage");
    const auto export_interface =
        readValue<std::string>(stream, "p14_interface_fraction");
    const auto export_multiplier =
        readValue<amrex::Real>(stream, "p14_reward_molar_multiplier");
    const auto export_rate =
        readValue<amrex::Real>(stream, "p14_k_export");
    if (runtime_export.enabled) {
      if (export_schema != BMXPhosphorusExport::schema_version ||
          export_contract != BMXPhosphorusExport::contract_id ||
          export_contract_hash != BMXPhosphorusExport::contract_sha256 ||
          export_operator_fit != BMXPhosphorusExport::operator_fit_id ||
          export_operator_fit_hash !=
              BMXPhosphorusExport::operator_fit_sha256 ||
          export_stage != runtime_export.bound_stage_id ||
          export_interface != BMXPhosphorusExport::interface_fraction_id ||
          export_multiplier != BMXPhosphorusExport::reward_molar_multiplier ||
          export_rate != runtime_export.k_export) {
        reject("P14 contract, O09 fit, interface, reward, or parameter identity mismatch");
      }
    } else if (export_schema != 0 || export_contract != "DISABLED" ||
               export_contract_hash != "DISABLED" ||
               export_operator_fit != "DISABLED" ||
               export_operator_fit_hash != "DISABLED" ||
               export_stage != "DISABLED" ||
               export_interface != "DISABLED" || export_multiplier != 0.0 ||
               export_rate != 0.0) {
      reject("disabled P14 metadata is not canonical");
    }
    BMXPhosphorusExport::CumulativeLedger export_ledger;
    export_ledger.requested_p = readValue<amrex::Real>(
        stream, "p14_cumulative_requested_p");
    export_ledger.accepted_p = readValue<amrex::Real>(
        stream, "p14_cumulative_accepted_p");
    export_ledger.rejected_p = readValue<amrex::Real>(
        stream, "p14_cumulative_rejected_p");
    export_ledger.exported_p = readValue<amrex::Real>(
        stream, "p14_cumulative_exported_p");
    export_ledger.exchange_derived_a = readValue<amrex::Real>(
        stream, "p14_cumulative_exchange_derived_a");
    export_ledger.bootstrap_a_credit = readValue<amrex::Real>(
        stream, "p14_cumulative_bootstrap_a_credit");
    export_ledger.active_volume = readValue<amrex::Real>(
        stream, "p14_cumulative_active_volume");
    export_ledger.active_d_basis = readValue<amrex::Real>(
        stream, "p14_cumulative_active_d_basis");
    export_ledger.updates = readUnsignedValue(stream, "p14_updates");
    export_ledger.particles_evaluated =
        readUnsignedValue(stream, "p14_particles_evaluated");
    export_ledger.eligible_particles =
        readUnsignedValue(stream, "p14_eligible_particles");
    export_ledger.true_crossings =
        readUnsignedValue(stream, "p14_true_crossings");
    export_ledger.solid_contacts =
        readUnsignedValue(stream, "p14_solid_contacts");
    export_ledger.accepted_export_events =
        readUnsignedValue(stream, "p14_accepted_export_events");
    export_ledger.donor_capped_events =
        readUnsignedValue(stream, "p14_donor_capped_events");
    export_ledger.roundoff_clamps =
        readUnsignedValue(stream, "p14_roundoff_clamps");
    export_ledger.last_update_id =
        readValue<std::int64_t>(stream, "p14_last_update_id");
    if (!runtime_export.enabled &&
        (export_ledger.requested_p != 0.0 ||
         export_ledger.accepted_p != 0.0 ||
         export_ledger.rejected_p != 0.0 ||
         export_ledger.exported_p != 0.0 ||
         export_ledger.exchange_derived_a != 0.0 ||
         export_ledger.bootstrap_a_credit != 0.0 ||
         export_ledger.active_volume != 0.0 ||
         export_ledger.active_d_basis != 0.0 ||
         export_ledger.updates != 0 ||
         export_ledger.particles_evaluated != 0 ||
         export_ledger.eligible_particles != 0 ||
         export_ledger.true_crossings != 0 ||
         export_ledger.solid_contacts != 0 ||
         export_ledger.accepted_export_events != 0 ||
         export_ledger.donor_capped_events != 0 ||
         export_ledger.roundoff_clamps != 0 ||
         export_ledger.last_update_id != -1)) {
      reject("disabled P14 cumulative ledger is not canonical zero");
    }
    BMXPhosphorusExport::restoreCumulativeLedger(export_ledger);

    const auto& runtime_p15 = BMXP15Stage0::config();
    const int p15_enabled = readValue<int>(stream, "p15_enabled");
    if (p15_enabled != 0 && p15_enabled != 1) {
      reject("p15_enabled must be 0 or 1");
    }
    if ((p15_enabled == 1) != runtime_p15.enabled) {
      reject("P15 enabled state mismatch");
    }
    const int p15_schema =
        readValue<int>(stream, "p15_schema_version");
    const auto p15_binding =
        readValue<std::string>(stream, "p15_binding_contract_id");
    const auto p15_binding_hash =
        readValue<std::string>(stream, "p15_binding_contract_sha256");
    const auto p15_bonded_contract =
        readValue<std::string>(stream, "p15_bonded_contract_id");
    const auto p15_bonded_contract_hash =
        readValue<std::string>(stream, "p15_bonded_contract_sha256");
    const auto p15_numerical =
        readValue<std::string>(stream, "p15_numerical_contract_id");
    const auto p15_numerical_hash =
        readValue<std::string>(stream, "p15_numerical_contract_sha256");
    const auto p15_terminal_contract =
        readValue<std::string>(stream, "p15_terminal_contract_id");
    const auto p15_terminal_contract_hash =
        readValue<std::string>(stream, "p15_terminal_contract_sha256");
    const auto p15_operator_fit =
        readValue<std::string>(stream, "p15_operator_fit_id");
    const auto p15_operator_fit_hash =
        readValue<std::string>(stream, "p15_operator_fit_sha256");
    const auto p15_stage =
        readValue<std::string>(stream, "p15_stage");
    const auto p15_authority_hash =
        readValue<std::string>(stream, "p15_authority_source_sha256");
    const auto p15_global_order =
        readValue<std::string>(stream, "p15_global_order_id");
    const auto p15_global_order_hash =
        readValue<std::string>(stream, "p15_global_order_sha256");
    const auto p15_diffusivity =
        readValue<amrex::Real>(stream, "p15_bonded_d_diffusivity");
    const int p15_cap_fault =
        readValue<int>(stream, "p15_cap_fault_injection");
    const int p15_outcomes =
        readValue<int>(stream, "p15_qualification_outcomes_enabled");
    if ((p15_cap_fault != 0 && p15_cap_fault != 1) ||
        (p15_outcomes != 0 && p15_outcomes != 1)) {
      reject("P15 Boolean checkpoint controls must be 0 or 1");
    }
    const auto p15_network_hash =
        readValue<std::string>(stream, "p15_initial_network_sha256");
    const auto p15_configuration_hash = readValue<std::string>(
        stream, "p15_generated_configuration_sha256");
    const auto p15_review_status = readValue<std::string>(
        stream, "p15_independent_review_status");
    const auto p15_review_hash = readValue<std::string>(
        stream, "p15_independent_review_sha256");
    const auto p15_reviewed_commit = readValue<std::string>(
        stream, "p15_reviewed_source_commit");
    const auto p15_expected_multiplier = readValue<amrex::Real>(
        stream, "p15_expected_area_match_multiplier");
    const auto p15_expected_full = readValue<amrex::Real>(
        stream, "p15_expected_initial_full_area");
    const auto p15_expected_tip010 = readValue<amrex::Real>(
        stream, "p15_expected_initial_tip010_area");
    if (runtime_p15.enabled) {
      if (p15_schema != BMXP15Stage0::schema_version ||
          p15_binding != BMXP15Stage0::binding_contract_id ||
          p15_binding_hash != BMXP15Stage0::binding_contract_sha256 ||
          p15_bonded_contract != BMXP15Stage0::bonded_contract_id ||
          p15_bonded_contract_hash !=
              BMXP15Stage0::bonded_contract_sha256 ||
          p15_numerical != BMXP15Stage0::numerical_contract_id ||
          p15_numerical_hash !=
              BMXP15Stage0::numerical_contract_sha256 ||
          p15_terminal_contract != BMXP15Stage0::terminal_contract_id ||
          p15_terminal_contract_hash !=
              BMXP15Stage0::terminal_contract_sha256 ||
          p15_operator_fit != BMXP15Stage0::operator_fit_id ||
          p15_operator_fit_hash != BMXP15Stage0::operator_fit_sha256 ||
          p15_stage != BMXP15Stage0::stage_id ||
          p15_authority_hash != BMXP15Stage0::authority_source_sha256 ||
          p15_global_order != BMXP15Stage0::global_order_id ||
          p15_global_order_hash != BMXP15Stage0::global_order_sha256 ||
          p15_diffusivity != runtime_p15.bonded_d_diffusivity ||
          p15_cap_fault != (runtime_p15.cap_fault_injection ? 1 : 0) ||
          p15_outcomes !=
              (runtime_p15.qualification_outcomes_enabled ? 1 : 0) ||
          p15_network_hash != runtime_p15.initial_network_sha256 ||
          p15_configuration_hash !=
              runtime_p15.generated_configuration_sha256 ||
          p15_review_status != runtime_p15.independent_review_status ||
          p15_review_hash != runtime_p15.independent_review_sha256 ||
          p15_reviewed_commit != runtime_p15.reviewed_source_commit ||
          p15_expected_multiplier !=
              runtime_p15.expected_area_match_multiplier ||
          p15_expected_full != runtime_p15.expected_initial_full_area ||
          p15_expected_tip010 !=
              runtime_p15.expected_initial_tip010_area) {
        reject("P15 contract, review, configuration, or parameter identity mismatch");
      }
    } else if (p15_schema != 0 || p15_binding != "DISABLED" ||
               p15_binding_hash != "DISABLED" ||
               p15_bonded_contract != "DISABLED" ||
               p15_bonded_contract_hash != "DISABLED" ||
               p15_numerical != "DISABLED" ||
               p15_numerical_hash != "DISABLED" ||
               p15_terminal_contract != "DISABLED" ||
               p15_terminal_contract_hash != "DISABLED" ||
               p15_operator_fit != "DISABLED" ||
               p15_operator_fit_hash != "DISABLED" ||
               p15_stage != "DISABLED" ||
               p15_authority_hash != "DISABLED" ||
               p15_global_order != "DISABLED" ||
               p15_global_order_hash != "DISABLED" ||
               p15_diffusivity != 0.0 || p15_cap_fault != 0 ||
               p15_outcomes != 0 || p15_network_hash != "DISABLED" ||
               p15_configuration_hash != "DISABLED" ||
               p15_review_status != "DISABLED" ||
               p15_review_hash != "DISABLED" ||
               p15_reviewed_commit != "DISABLED" ||
               p15_expected_multiplier != 0.0 ||
               p15_expected_full != 0.0 ||
               p15_expected_tip010 != 0.0) {
      reject("disabled P15 metadata is not canonical");
    }

    BMXP15Stage0::AreaMatchState p15_area_match;
    p15_area_match.bound = readValue<int>(stream, "p15_area_match_bound");
    p15_area_match.multiplier = readValue<amrex::Real>(
        stream, "p15_area_match_multiplier");
    p15_area_match.initial_full_area = readValue<amrex::Real>(
        stream, "p15_area_match_initial_full_area");
    p15_area_match.initial_tip010_area = readValue<amrex::Real>(
        stream, "p15_area_match_initial_tip010_area");
    BMXP15Stage0::TerminalLedger p15_terminal;
    p15_terminal.current_full_area = readValue<amrex::Real>(
        stream, "p15_terminal_current_full_area");
    p15_terminal.current_tip_005_area = readValue<amrex::Real>(
        stream, "p15_terminal_current_tip005_area");
    p15_terminal.current_tip_010_area = readValue<amrex::Real>(
        stream, "p15_terminal_current_tip010_area");
    p15_terminal.current_tip_020_area = readValue<amrex::Real>(
        stream, "p15_terminal_current_tip020_area");
    p15_terminal.current_effective_area = readValue<amrex::Real>(
        stream, "p15_terminal_current_effective_area");
    p15_terminal.updates =
        readUnsignedValue(stream, "p15_terminal_updates");
    p15_terminal.segments =
        readUnsignedValue(stream, "p15_terminal_segments");
    p15_terminal.live_terminal_origins = readUnsignedValue(
        stream, "p15_terminal_live_terminal_origins");
    BMXP15Stage0::BondedLedger p15_bonded;
    p15_bonded.requested = readValue<amrex::Real>(
        stream, "p15_bonded_cumulative_requested");
    p15_bonded.accepted = readValue<amrex::Real>(
        stream, "p15_bonded_cumulative_accepted");
    p15_bonded.rejected = readValue<amrex::Real>(
        stream, "p15_bonded_cumulative_rejected");
    p15_bonded.gross_absolute_accepted = readValue<amrex::Real>(
        stream, "p15_bonded_cumulative_gross_absolute_accepted");
    p15_bonded.maximum_diagonal_rate = readValue<amrex::Real>(
        stream, "p15_bonded_maximum_diagonal_rate");
    p15_bonded.minimum_donor_scale = readValue<amrex::Real>(
        stream, "p15_bonded_minimum_donor_scale");
    p15_bonded.updates =
        readUnsignedValue(stream, "p15_bonded_updates");
    p15_bonded.internal_substeps =
        readUnsignedValue(stream, "p15_bonded_internal_substeps");
    p15_bonded.virtual_pairs =
        readUnsignedValue(stream, "p15_bonded_virtual_pairs");
    p15_bonded.material_cap_activations = readUnsignedValue(
        stream, "p15_bonded_material_cap_activations");
    if (!runtime_p15.enabled &&
        (p15_area_match.bound != 0 || p15_area_match.multiplier != 0.0 ||
         p15_area_match.initial_full_area != 0.0 ||
         p15_area_match.initial_tip010_area != 0.0 ||
         p15_terminal.current_full_area != 0.0 ||
         p15_terminal.current_tip_005_area != 0.0 ||
         p15_terminal.current_tip_010_area != 0.0 ||
         p15_terminal.current_tip_020_area != 0.0 ||
         p15_terminal.current_effective_area != 0.0 ||
         p15_terminal.updates != 0 || p15_terminal.segments != 0 ||
         p15_terminal.live_terminal_origins != 0 ||
         p15_bonded.requested != 0.0 || p15_bonded.accepted != 0.0 ||
         p15_bonded.rejected != 0.0 ||
         p15_bonded.gross_absolute_accepted != 0.0 ||
         p15_bonded.maximum_diagonal_rate != 0.0 ||
         p15_bonded.minimum_donor_scale != 1.0 ||
         p15_bonded.updates != 0 || p15_bonded.internal_substeps != 0 ||
         p15_bonded.virtual_pairs != 0 ||
         p15_bonded.material_cap_activations != 0)) {
      reject("disabled P15 runtime state is not canonical zero");
    }
    BMXP15Stage0::restoreRuntimeState(
        p15_area_match, p15_terminal, p15_bonded);

    BMXPhosphorus::CumulativeLedger ledger;
    const int reference_bound =
        readValue<int>(stream, "ledger_reference_bound");
    if (reference_bound != 0 && reference_bound != 1) {
      reject("ledger_reference_bound must be 0 or 1");
    }
    ledger.reference_bound = reference_bound == 1;
    ledger.reference_total_p =
        readValue<amrex::Real>(stream, "ledger_reference_total_p");
    ledger.structural_p =
        readValue<amrex::Real>(stream, "ledger_structural_p");
    ledger.exported_p =
        readValue<amrex::Real>(stream, "ledger_exported_p");
    ledger.other_exits.d =
        readValue<amrex::Real>(stream, "ledger_other_exit_d");
    ledger.other_exits.e =
        readValue<amrex::Real>(stream, "ledger_other_exit_e");
    ledger.other_exits.f =
        readValue<amrex::Real>(stream, "ledger_other_exit_f");
    ledger.other_exit_events =
        readUnsignedValue(stream, "ledger_other_exit_events");
    const amrex::Real structural_scale =
        std::abs(ledger.structural_p) +
        std::abs(reaction_ledger.structuralized_p);
    if (std::abs(ledger.structural_p -
                 reaction_ledger.structuralized_p) >
        BMXPhosphorus::localTolerance(structural_scale)) {
      reject("P13 structuralized ledger differs from global structural P");
    }
    const amrex::Real export_scale =
        std::abs(ledger.exported_p) + std::abs(export_ledger.exported_p);
    if (std::abs(ledger.exported_p - export_ledger.exported_p) >
        BMXPhosphorus::localTolerance(export_scale)) {
      reject("P14 export ledger differs from global exported P");
    }
    if (readLine(stream, "BMX schema end marker") != "BMX_SCHEMA_V8_END") {
      reject("missing BMX_SCHEMA_V8_END marker");
    }
    BMXPhosphorus::restoreCumulativeLedger(ledger);
    return geometry_metadata;
  }

  void validateGeometryLines (const GeometryMetadata& metadata,
                              const amrex::Real* prob_lo,
                              const amrex::Real* prob_hi)
  {
    for (int direction = 0; direction < AMREX_SPACEDIM; ++direction) {
      if (!std::isfinite(prob_lo[direction]) ||
          !std::isfinite(prob_hi[direction]) ||
          prob_lo[direction] != metadata.prob_lo[direction] ||
          prob_hi[direction] != metadata.prob_hi[direction]) {
        reject("checkpoint geometry lines differ from serialized P11 identity");
      }
    }
  }
}
